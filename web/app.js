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
const supervisionEl = document.querySelector("#supervision");
const capturesEl = document.querySelector("#captures");
const refreshBtn = document.querySelector("#refreshBtn");

function addLog(message) {
  const row = document.createElement("div");
  row.className = "log";
  row.textContent = `[${new Date().toLocaleTimeString()}] ${repairText(message)}`;
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

async function refreshCaptures() {
  const data = await fetch("/captures?limit=6").then((response) => response.json());
  renderCaptures(data.captures || []);
}

function renderStatus(status) {
  statusEl.textContent = status.running ? "running" : "stopped";
  if (status.paused) statusEl.textContent = "paused";
  progressEl.textContent = status.progress || "idle";
  if (status.goal && !goalInput.value) {
    goalInput.value = status.goal;
  }
  if (status.current_action) {
    actionEl.textContent = JSON.stringify(repairText(status.current_action), null, 2);
  }
  if (status.mission) renderMission(status.mission);
  if (status.monitoring) renderMonitoring(status.monitoring);
}

function renderMission(mission) {
  const subtasks = mission.subtasks || [];
  if (!subtasks.length) {
    missionEl.textContent = "Aucune sous-tache";
    return;
  }
  missionEl.innerHTML = "";
  const summary = document.createElement("div");
  summary.textContent = repairText(`${mission.status} - ${mission.completed || 0}/${mission.total || subtasks.length}`);
  missionEl.appendChild(summary);
  for (const subtask of subtasks) {
    const row = document.createElement("div");
    row.className = "subtask";
    const status = document.createElement("strong");
    status.textContent = subtask.status;
    row.appendChild(status);
    row.append(` - ${repairText(subtask.text)}`);
    missionEl.appendChild(row);
  }
}

function renderMonitoring(monitoring) {
  const plannerUsage = monitoring.planner?.usage || {};
  const visionUsage = monitoring.vision_model?.usage || {};
  const totalTokens = (plannerUsage.total_tokens || 0) + (visionUsage.total_tokens || 0);
  const next = repairText(monitoring.next_subtask?.text || "Aucune");
  const plan = repairText(monitoring.next_plan || "En attente");
  const visionSummary = repairText(monitoring.vision_analysis?.summary || monitoring.vision_analysis?.suggested_next_action || "Desactive");
  const rows = [
    ["Temps ecoule", formatDuration(monitoring.elapsed_seconds || 0)],
    ["Etape", `${monitoring.current_step || 0}/${monitoring.max_steps || 0}`],
    ["Prochaine tache", next],
    ["Prochain plan", trimText(plan, 160)],
    ["Stagnation", `${monitoring.stagnant_observations || 0}`],
    ["Appels Mistral", `${monitoring.planner?.calls || 0} texte / ${monitoring.vision_model?.calls || 0} vision`],
    ["Rate limits", `${monitoring.planner?.rate_limits || 0} texte / ${monitoring.vision_model?.rate_limits || 0} vision`],
    ["Usage API", `${totalTokens} tokens`],
    ["Vision", trimText(visionSummary, 160)],
  ];
  supervisionEl.innerHTML = "";
  for (const [label, value] of rows) {
    const row = document.createElement("div");
    row.className = "metric";
    const name = document.createElement("span");
    name.textContent = label;
    const data = document.createElement("strong");
    data.textContent = repairText(value);
    row.append(name, data);
    supervisionEl.appendChild(row);
  }
}

function renderCaptures(captures) {
  if (!captures.length) {
    capturesEl.textContent = "Aucune capture";
    return;
  }
  capturesEl.innerHTML = "";
  for (const capture of captures.slice().reverse()) {
    const row = document.createElement("div");
    row.className = "capture-row";
    const title = document.createElement("strong");
    title.textContent = `Etape ${capture.step} - ${capture.backend || "capture"}`;
    const detail = document.createElement("span");
    detail.textContent = `${capture.reason || "important"} - ${capture.signature || ""}`;
    row.append(title, detail);
    capturesEl.appendChild(row);
  }
}

function formatDuration(seconds) {
  const total = Math.max(0, Number(seconds) || 0);
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const rest = total % 60;
  if (hours) return `${hours}h ${String(minutes).padStart(2, "0")}m ${String(rest).padStart(2, "0")}s`;
  return `${minutes}m ${String(rest).padStart(2, "0")}s`;
}

function trimText(value, size) {
  const text = String(value || "");
  return text.length > size ? `${text.slice(0, size - 1)}...` : text;
}

function repairText(value) {
  if (Array.isArray(value)) return value.map((item) => repairText(item));
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, repairText(item)]));
  }
  if (typeof value !== "string") return value;
  const replacements = {
    "\u000e0": "à",
    "\u000e2": "â",
    "\u000e7": "ç",
    "\u000e8": "è",
    "\u000e9": "é",
    "\u000ea": "ê",
    "\u000eb": "ë",
    "\u000ee": "î",
    "\u000ef": "ï",
    "\u000f4": "ô",
    "\u000f9": "ù",
    "\u000fb": "û",
    "\u000fc": "ü",
    "\u000c0": "À",
    "\u000c7": "Ç",
    "\u000c8": "È",
    "\u000c9": "É",
    "\u000ca": "Ê",
    "\u000d4": "Ô",
  };
  let text = value;
  for (const [broken, fixed] of Object.entries(replacements)) {
    text = text.replaceAll(broken, fixed);
  }
  return text.replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f]/g, "");
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

refreshBtn.addEventListener("click", async () => {
  try {
    await refreshStatus();
    await refreshCaptures();
    await refreshScreenshot();
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
    if (payload.action) actionEl.textContent = JSON.stringify(repairText(payload.action), null, 2);
    if (payload.mission) renderMission(payload.mission);
    if (payload.monitoring) renderMonitoring(payload.monitoring);
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
refreshCaptures().catch(() => {});
connectWebSocket();
