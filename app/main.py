import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.checker import run_checker
from app.sessions import SessionError, session_manager
from app.tasks import TaskNotFoundError, task_store
from app.terminal import terminal_ws

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    session_manager.start_cleanup_worker()
    try:
        yield
    finally:
        session_manager.stop_cleanup_worker()


app = FastAPI(title="k8s-shell-simulator", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/healthz")
async def healthz():
    return {"ok": True}


@app.post("/api/sessions")
async def create_session():
    try:
        session = await session_manager.create_session()
        return session.to_public_dict()
    except SessionError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' was not found.")
    return session.to_public_dict()


@app.post("/api/sessions/{session_id}/reset")
async def reset_session(session_id: str):
    try:
        session = await session_manager.reset_session(session_id)
        return session.to_public_dict()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' was not found.") from exc
    except SessionError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    try:
        await session_manager.delete_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' was not found.") from exc
    return {"deleted": True, "session_id": session_id}


@app.get("/api/tasks")
async def list_tasks():
    return [task.to_public_dict(include_description=False) for task in task_store.list_tasks()]


@app.get("/api/tasks/{task_id}")
async def get_task(task_id: str):
    try:
        return task_store.get_task(task_id).to_public_dict()
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/sessions/{session_id}/tasks/{task_id}/check")
async def check_task(session_id: str, task_id: str):
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' was not found.")
    try:
        task = task_store.get_task(task_id)
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    result = await run_checker(session, task)
    session_manager.record_task_result(session_id, task_id, result.passed, result.message)
    return result.model_dump()


@app.post("/api/sessions/{session_id}/tasks/{task_id}/setup")
async def setup_task(session_id: str, task_id: str):
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' was not found.")
    try:
        task = task_store.get_task(task_id)
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    try:
        await session_manager.apply_task_setup(session, task.setup_manifests)
    except SessionError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"applied": True, "manifests": task.setup_manifests}


@app.websocket("/ws/terminal/{session_id}")
async def websocket_terminal(websocket: WebSocket, session_id: str):
    session = session_manager.get_session(session_id)
    if not session:
        await websocket.close(code=4404, reason="Session was not found.")
        return
    await terminal_ws(websocket, session)
