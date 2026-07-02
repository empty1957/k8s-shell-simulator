import asyncio
import json
import logging
import os
import pty
import shlex
import signal
import struct
import termios
import fcntl

from fastapi import WebSocket, WebSocketDisconnect

from app.sessions import Session

logger = logging.getLogger(__name__)


async def terminal_ws(websocket: WebSocket, session: Session) -> None:
    await websocket.accept()
    loop = asyncio.get_running_loop()
    master_fd, slave_fd = pty.openpty()
    env = os.environ.copy()
    env["KUBECONFIG"] = str(session.kubeconfig)
    env["TERM"] = "xterm-256color"
    env["SESSION_ID"] = session.id
    env["KIND_CLUSTER_NAME"] = session.cluster_name
    env["PS1"] = f"sim:{session.id[:6]} \\w $ "

    proc = await asyncio.create_subprocess_exec(
        "/bin/bash",
        "--login",
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        cwd=str(session.directory),
        env=env,
        preexec_fn=os.setsid,
    )
    os.close(slave_fd)
    reader_task = asyncio.create_task(_pty_to_websocket(loop, master_fd, websocket))

    try:
        await websocket.send_text(
            f"\r\nConnected to session {session.id}. KUBECONFIG={shlex.quote(str(session.kubeconfig))}\r\n"
        )
        while True:
            raw = await websocket.receive_text()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                os.write(master_fd, raw.encode())
                continue

            if payload.get("type") == "input":
                os.write(master_fd, payload.get("data", "").encode())
            elif payload.get("type") == "resize":
                _resize_pty(master_fd, int(payload.get("cols", 80)), int(payload.get("rows", 24)))
    except WebSocketDisconnect:
        logger.info("Terminal websocket disconnected session=%s", session.id)
    finally:
        reader_task.cancel()
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            os.close(master_fd)
        except OSError:
            pass
        await proc.wait()


async def _pty_to_websocket(loop: asyncio.AbstractEventLoop, master_fd: int, websocket: WebSocket) -> None:
    while True:
        data = await loop.run_in_executor(None, os.read, master_fd, 4096)
        if not data:
            break
        await websocket.send_text(data.decode(errors="replace"))


def _resize_pty(master_fd: int, cols: int, rows: int) -> None:
    packed = struct.pack("HHHH", rows, cols, 0, 0)
    fcntl.ioctl(master_fd, termios.TIOCSWINSZ, packed)
