const goalInput = document.querySelector("#goal");
const goalBtn = document.querySelector("#goalBtn");
const startBtn = document.querySelector("#startBtn");
const pauseBtn = document.querySelector("#pauseBtn");
const resumeBtn = document.querySelector("#resumeBtn");
const stopBtn = document.querySelector("#stopBtn");
const statusEl = document.querySelector("#status");
const progressEl = document.querySelector("#progress");
const actionEl = document.querySelector("#action");
const logsEl = document.querySelector("#logs");
const screenEl = document.querySelector("#screen");
const screenPlaceholder = document.querySelector("#screenPlaceholder");
const missionEl = document.querySelector("#mission");

function addLog(message) {
  const row = document.createElement("div");
  row.className = "log";
  row.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
  logsEl.prepend(row);
}

function renderScreenshot(src) {
  screenEl.src = src;
  screenEl.hidden = false;
  screenPlaceholder.hidden = true;
}

async function post(path, body) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json();
}

async function refreshStatus() {
  const status = await fetch("/status").then((response) => response.json());
  renderStatus(status);
}

async function refreshScreenshot() {
  const response = await fetch(`/screenshot?t=${Date.now()}`);
  if (!response.ok) return;
  renderScreenshot(response.url);
}

function renderStatus(status) {
  statusEl.textContent = status.running ? "running" : "stopped";
  if (status.paused) statusEl.textContent = "paused";
  progressEl.textContent = status.progress || "idle";
  if (status.goal && !goalInput.value) {
    goalInput.value = status.goal;
  }
  if (status.current_action) {
    actionEl.textContent = JSON.stringify(status.current_action, null, 2);
  }
  if (status.mission) renderMission(status.mission);
}

function renderMission(mission) {
  const subtasks = mission.subtasks || [];
  if (!subtasks.length) {
    missionEl.textContent = "Aucune sous-tache";
    return;
  }
  missionEl.innerHTML = "";
  const summary = document.createElement("div");
  summary.textContent = `${mission.status} - ${mission.completed || 0}/${mission.total || subtasks.length}`;
  missionEl.appendChild(summary);
  for (const subtask of subtasks) {
    const row = document.createElement("div");
    row.className = "subtask";
    const status = document.createElement("strong");
    status.textContent = subtask.status;
    row.appendChild(status);
    row.append(` - ${subtask.text}`);
    missionEl.appendChild(row);
  }
}

goalBtn.addEventListener("click", async () => {
  const goal = goalInput.value.trim();
  if (!goal) return;
  try {
    await post("/goal", { goal });
    addLog(`Objectif defini: ${goal}`);
    await refreshStatus();
  } catch (error) {
    addLog(`Erreur: ${error.message}`);
  }
});

startBtn.addEventListener("click", async () => {
  const goal = goalInput.value.trim();
  try {
    if (goal) {
      await post("/goal", { goal });
      addLog(`Objectif defini: ${goal}`);
    }
    const status = await post("/start");
    renderStatus(status);
    if (status.running) {
      addLog("Agent demarre");
    } else if (!status.goal && !goal) {
      addLog("Erreur: definis un objectif avant de demarrer");
    } else {
      addLog(`Agent non demarre: ${status.progress || "verifie les logs"}`);
    }
  } catch (error) {
    addLog(`Erreur: ${error.message}`);
  }
});

stopBtn.addEventListener("click", async () => {
  try {
    await post("/stop");
    addLog("Agent arrete");
    await refreshStatus();
  } catch (error) {
    addLog(`Erreur: ${error.message}`);
  }
});

pauseBtn.addEventListener("click", async () => {
  try {
    const status = await post("/pause");
    renderStatus(status);
    addLog("Agent en pause");
  } catch (error) {
    addLog(`Erreur: ${error.message}`);
  }
});

resumeBtn.addEventListener("click", async () => {
  try {
    const status = await post("/resume");
    renderStatus(status);
    addLog("Agent relance");
  } catch (error) {
    addLog(`Erreur: ${error.message}`);
  }
});

function connectWebSocket() {
  const protocol = location.protocol === "https:" ? "wss" : "ws";
  const socket = new WebSocket(`${protocol}://${location.host}/ws`);

  socket.addEventListener("message", (event) => {
    const data = JSON.parse(event.data);
    if (data.status) renderStatus(data.status);
    const payload = data.payload || {};
    if (payload.progress) progressEl.textContent = payload.progress;
    if (payload.screenshot) {
      renderScreenshot(payload.screenshot);
    }
    if (payload.screenshot_backend) addLog(`Capture: ${payload.screenshot_backend}`);
    if (payload.action) actionEl.textContent = JSON.stringify(payload.action, null, 2);
    if (payload.mission) renderMission(payload.mission);
    if (payload.ocr_error) addLog(`OCR: ${payload.ocr_error}`);
    if (data.type === "result") addLog(`${payload.action?.tool || "tool"} -> ${payload.result?.ok ? "ok" : "error"}`);
    if (data.type === "error") addLog(`Erreur: ${payload.message || payload.error || JSON.stringify(payload)}`);
    if (data.type === "done") addLog("Objectif termine");
  });

  socket.addEventListener("close", () => {
    addLog("WebSocket deconnecte, reconnexion...");
    setTimeout(connectWebSocket, 1500);
  });
}

refreshStatus().catch((error) => addLog(error.message));
refreshScreenshot().catch(() => {});
connectWebSocket();
