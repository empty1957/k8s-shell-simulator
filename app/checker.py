import asyncio
import logging
import os
from pathlib import Path

from pydantic import BaseModel

from app.sessions import Session
from app.tasks import Task

logger = logging.getLogger(__name__)
ROOT_DIR = Path(__file__).resolve().parent.parent


class CheckResult(BaseModel):
    passed: bool
    message: str


async def run_checker(session: Session, task: Task) -> CheckResult:
    if task.check.type != "script":
        return CheckResult(passed=False, message=f"Unsupported checker type: {task.check.type}")

    script_path = (ROOT_DIR / task.check.script).resolve()
    if not str(script_path).startswith(str(ROOT_DIR.resolve())) or not script_path.exists():
        return CheckResult(passed=False, message=f"Checker script was not found: {task.check.script}")

    logger.info("Running checker task=%s session=%s", task.id, session.id)
    env = os.environ.copy()
    env["KUBECONFIG"] = str(session.kubeconfig)
    proc = await asyncio.create_subprocess_exec(
        str(script_path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(ROOT_DIR),
        env=env,
    )
    stdout, stderr = await proc.communicate()
    message = "\n".join(
        part.strip()
        for part in [stdout.decode(errors="replace"), stderr.decode(errors="replace")]
        if part.strip()
    )
    passed = proc.returncode == 0
    logger.info("Checker result task=%s session=%s passed=%s", task.id, session.id, passed)
    return CheckResult(passed=passed, message=message or ("PASS" if passed else "FAIL"))
