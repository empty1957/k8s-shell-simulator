let session = null;
let tasks = [];
let selectedTaskId = null;
let terminal = null;
let fitAddon = null;
let socket = null;

const sessionMeta = document.getElementById("session-meta");
const tasksEl = document.getElementById("tasks");
const titleEl = document.getElementById("task-title");
const difficultyEl = document.getElementById("task-difficulty");
const descriptionEl = document.getElementById("task-description");
const resultEl = document.getElementById("result");
const checkBtn = document.getElementById("check-btn");
const resetBtn = document.getElementById("reset-btn");

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `HTTP ${response.status}`);
  }
  return response.json();
}

async function start() {
  setBusy(true, "Creating a kind cluster for your session...");
  try {
    session = await api("/api/sessions", { method: "POST" });
    tasks = await api("/api/tasks");
    sessionMeta.textContent = `Session: ${session.session_id} | Cluster: ${session.cluster_name}`;
    renderTasks();
    if (tasks.length > 0) {
      await selectTask(tasks[0].id);
    }
    connectTerminal();
  } catch (error) {
    showResult(false, error.message);
  } finally {
    setBusy(false);
  }
}

function setBusy(disabled, message = null) {
  checkBtn.disabled = disabled || !selectedTaskId;
  resetBtn.disabled = disabled || !session;
  if (message) {
    showResult(null, message);
  }
}

function renderTasks() {
  tasksEl.innerHTML = "";
  tasks.forEach((task) => {
    const button = document.createElement("button");
    const state = session.task_results?.[task.id];
    button.className = `task-item ${task.id === selectedTaskId ? "selected" : ""} ${state?.passed ? "passed" : ""}`;
    button.innerHTML = `<strong>${task.title}</strong><span>${task.id} · ${task.difficulty}${state ? ` · ${state.passed ? "passed" : "failed"}` : ""}</span>`;
    button.addEventListener("click", () => selectTask(task.id));
    tasksEl.appendChild(button);
  });
}

async function selectTask(taskId) {
  const task = await api(`/api/tasks/${taskId}`);
  selectedTaskId = task.id;
  titleEl.textContent = task.title;
  difficultyEl.textContent = task.difficulty;
  descriptionEl.textContent = task.description;
  const state = session.task_results?.[task.id];
  if (state) {
    showResult(state.passed, state.message);
  } else {
    showResult(null, "No check has been run for this task.");
  }
  if (task.setup?.manifests?.length) {
    await api(`/api/sessions/${session.session_id}/tasks/${task.id}/setup`, { method: "POST" });
  }
  renderTasks();
  setBusy(false);
}

function connectTerminal() {
  terminal = new Terminal({
    cursorBlink: true,
    fontFamily: "Menlo, Consolas, monospace",
    fontSize: 14,
    theme: { background: "#101318" },
  });
  fitAddon = new FitAddon.FitAddon();
  terminal.loadAddon(fitAddon);
  terminal.open(document.getElementById("terminal"));
  fitAddon.fit();

  const scheme = window.location.protocol === "https:" ? "wss" : "ws";
  socket = new WebSocket(`${scheme}://${window.location.host}/ws/terminal/${session.session_id}`);
  socket.addEventListener("message", (event) => terminal.write(event.data));
  socket.addEventListener("open", () => {
    sendResize();
    terminal.focus();
  });
  socket.addEventListener("close", () => terminal.write("\r\n[terminal disconnected]\r\n"));
  terminal.onData((data) => socket.readyState === WebSocket.OPEN && socket.send(JSON.stringify({ type: "input", data })));
  window.addEventListener("resize", () => {
    fitAddon.fit();
    sendResize();
  });
}

function sendResize() {
  if (socket?.readyState === WebSocket.OPEN && terminal) {
    socket.send(JSON.stringify({ type: "resize", cols: terminal.cols, rows: terminal.rows }));
  }
}

checkBtn.addEventListener("click", async () => {
  if (!session || !selectedTaskId) return;
  setBusy(true, "Running checker...");
  try {
    const result = await api(`/api/sessions/${session.session_id}/tasks/${selectedTaskId}/check`, { method: "POST" });
    session = await api(`/api/sessions/${session.session_id}`);
    showResult(result.passed, result.message);
    renderTasks();
  } catch (error) {
    showResult(false, error.message);
  } finally {
    setBusy(false);
  }
});

resetBtn.addEventListener("click", async () => {
  if (!session) return;
  setBusy(true, "Resetting kind cluster...");
  try {
    session = await api(`/api/sessions/${session.session_id}/reset`, { method: "POST" });
    sessionMeta.textContent = `Session: ${session.session_id} | Cluster: ${session.cluster_name}`;
    showResult(null, "Environment was reset.");
    renderTasks();
    if (socket) socket.close();
    document.getElementById("terminal").innerHTML = "";
    connectTerminal();
  } catch (error) {
    showResult(false, error.message);
  } finally {
    setBusy(false);
  }
});

function showResult(passed, message) {
  resultEl.className = `result ${passed === true ? "passed" : passed === false ? "failed" : "idle"}`;
  resultEl.textContent = message;
}

start();
