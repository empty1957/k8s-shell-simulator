import asyncio
import json
import logging
import os
import shutil
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

SESSIONS_DIR = Path(os.getenv("SESSIONS_DIR", "/workspaces/sessions"))
SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", "7200"))
CLEANUP_INTERVAL_SECONDS = int(os.getenv("CLEANUP_INTERVAL_SECONDS", "300"))
SCRIPT_DIR = Path(__file__).resolve().parent.parent / "scripts"
TASKS_DIR = Path(__file__).resolve().parent.parent / "tasks"


class SessionError(RuntimeError):
    pass


@dataclass
class TaskProgress:
    passed: bool
    message: str
    checked_at: str


@dataclass
class Session:
    id: str
    cluster_name: str
    directory: Path
    kubeconfig: Path
    created_at: datetime
    updated_at: datetime
    task_results: dict[str, TaskProgress] = field(default_factory=dict)

    @property
    def expires_at(self) -> datetime:
        return self.created_at + timedelta(seconds=SESSION_TTL_SECONDS)

    def to_public_dict(self) -> dict:
        return {
            "session_id": self.id,
            "cluster_name": self.cluster_name,
            "kubeconfig": str(self.kubeconfig),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "task_results": {
                task_id: {
                    "passed": progress.passed,
                    "message": progress.message,
                    "checked_at": progress.checked_at,
                }
                for task_id, progress in self.task_results.items()
            },
        }


class SessionManager:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._lock = asyncio.Lock()
        self._cleanup_task: asyncio.Task | None = None

    def start_cleanup_worker(self) -> None:
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        if not self._cleanup_task:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    def stop_cleanup_worker(self) -> None:
        if self._cleanup_task:
            self._cleanup_task.cancel()
            self._cleanup_task = None

    def get_session(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    async def create_session(self) -> Session:
        session_id = uuid.uuid4().hex[:12]
        cluster_name = f"k8s-sim-{session_id}"
        directory = SESSIONS_DIR / session_id
        kubeconfig = directory / "kubeconfig"
        session = Session(
            id=session_id,
            cluster_name=cluster_name,
            directory=directory,
            kubeconfig=kubeconfig,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        async with self._lock:
            logger.info("Creating session %s", session_id)
            directory.mkdir(parents=True, exist_ok=True)
            await self._create_cluster(session)
            self._sessions[session_id] = session
            self._write_metadata(session)
            return session

    async def reset_session(self, session_id: str) -> Session:
        async with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                raise KeyError(session_id)
            logger.info("Resetting session %s", session_id)
            await self._delete_cluster(session, ignore_errors=True)
            session.directory.mkdir(parents=True, exist_ok=True)
            session.task_results.clear()
            session.updated_at = datetime.now(timezone.utc)
            await self._create_cluster(session)
            self._write_metadata(session)
            return session

    async def delete_session(self, session_id: str) -> None:
        async with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                raise KeyError(session_id)
            await self._delete_cluster(session, ignore_errors=True)
            shutil.rmtree(session.directory, ignore_errors=True)
            del self._sessions[session_id]
            logger.info("Deleted session %s", session_id)

    def record_task_result(self, session_id: str, task_id: str, passed: bool, message: str) -> None:
        session = self._sessions[session_id]
        session.task_results[task_id] = TaskProgress(
            passed=passed,
            message=message,
            checked_at=datetime.now(timezone.utc).isoformat(),
        )
        session.updated_at = datetime.now(timezone.utc)
        self._write_metadata(session)

    async def apply_task_setup(self, session: Session, manifests: list[str]) -> None:
        for manifest in manifests:
            manifest_path = (TASKS_DIR / manifest).resolve()
            if not str(manifest_path).startswith(str(TASKS_DIR.resolve())):
                raise SessionError(f"Invalid setup manifest path: {manifest}")
            if not manifest_path.exists():
                raise SessionError(f"Setup manifest was not found: {manifest}")
            result = await self._run(
                ["kubectl", "apply", "-f", str(manifest_path)],
                env={"KUBECONFIG": str(session.kubeconfig)},
            )
            if result.returncode != 0:
                raise SessionError(result.stderr.strip() or result.stdout.strip())

    async def _create_cluster(self, session: Session) -> None:
        logger.info("Creating kind cluster %s", session.cluster_name)
        result = await self._run(
            [
                str(SCRIPT_DIR / "create-kind-cluster.sh"),
                session.cluster_name,
                str(session.kubeconfig),
            ],
            env={"KUBECONFIG": str(session.kubeconfig)},
        )
        if result.returncode != 0:
            message = (result.stderr or result.stdout).strip()
            logger.error("Failed to create kind cluster %s: %s", session.cluster_name, message)
            raise SessionError(f"Failed to create kind cluster '{session.cluster_name}': {message}")

    async def _delete_cluster(self, session: Session, ignore_errors: bool = False) -> None:
        logger.info("Deleting kind cluster %s", session.cluster_name)
        result = await self._run([str(SCRIPT_DIR / "delete-kind-cluster.sh"), session.cluster_name])
        if result.returncode != 0 and not ignore_errors:
            message = (result.stderr or result.stdout).strip()
            raise SessionError(f"Failed to delete kind cluster '{session.cluster_name}': {message}")

    async def _cleanup_loop(self) -> None:
        while True:
            await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
            await self.cleanup_expired_sessions()

    async def cleanup_expired_sessions(self) -> None:
        now = datetime.now(timezone.utc)
        expired = [
            session_id
            for session_id, session in self._sessions.items()
            if session.expires_at <= now
        ]
        for session_id in expired:
            logger.info("Cleaning up expired session %s", session_id)
            try:
                await self.delete_session(session_id)
            except Exception:
                logger.exception("Failed to clean up expired session %s", session_id)

    async def _run(self, cmd: list[str], env: dict[str, str] | None = None) -> "CommandResult":
        run_env = os.environ.copy()
        if env:
            run_env.update(env)
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=run_env,
        )
        stdout, stderr = await proc.communicate()
        return CommandResult(
            proc.returncode,
            stdout.decode(errors="replace"),
            stderr.decode(errors="replace"),
        )

    def _write_metadata(self, session: Session) -> None:
        session.directory.mkdir(parents=True, exist_ok=True)
        (session.directory / "session.json").write_text(
            json.dumps(session.to_public_dict(), indent=2),
            encoding="utf-8",
        )


@dataclass
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


session_manager = SessionManager()
