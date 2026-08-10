/* ════════════════════════════════════════════════════════
   main.js — Index page logic
   ════════════════════════════════════════════════════════ */

// Change this to your Render URL when deployed, e.g:
// const API_BASE = "https://codearena-api.onrender.com";
const API_BASE = "http://localhost:5000";


// ── Toast utility ─────────────────────────────────────────
function showToast(type, title, body = "", duration = 4000) {
  const container = document.getElementById("toast-container");
  const icons = { success: "✅", error: "❌", info: "ℹ️" };
  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `
    <div class="toast-icon">${icons[type] || "📌"}</div>
    <div>
      <div class="toast-title">${title}</div>
      ${body ? `<div class="toast-body">${body}</div>` : ""}
    </div>`;
  container.appendChild(toast);
  setTimeout(() => { toast.style.opacity = "0"; toast.style.transition = "opacity 0.4s"; setTimeout(() => toast.remove(), 400); }, duration);
}

// ── Username logic ─────────────────────────────────────────
const USERNAME_KEY = "codearena_username";

function getUsername() {
  return localStorage.getItem(USERNAME_KEY) || "";
}

function setUsername(name) {
  localStorage.setItem(USERNAME_KEY, name.trim());
}

function updateUsernameDisplay() {
  const name = getUsername();
  const display = document.getElementById("username-display");
  if (display) display.textContent = name || "Set Username";
}

// ── Modal ──────────────────────────────────────────────────
const modal   = document.getElementById("username-modal");
const btnSet  = document.getElementById("btn-set-username");
const input   = document.getElementById("username-input");
const btnSave = document.getElementById("btn-save-username");

function openModal() {
  modal.classList.remove("hidden");
  input.value = getUsername();
  setTimeout(() => input.focus(), 100);
}

function closeModal() { modal.classList.add("hidden"); }

btnSet.addEventListener("click", openModal);

btnSave.addEventListener("click", () => {
  const name = input.value.trim();
  if (!name) { input.focus(); return; }
  setUsername(name);
  updateUsernameDisplay();
  closeModal();
  showToast("success", `Hello, ${name}! 👋`);
});

input.addEventListener("keydown", e => { if (e.key === "Enter") btnSave.click(); });
modal.addEventListener("click", e => { if (e.target === modal) closeModal(); });

// Show modal if no username set
if (!getUsername()) setTimeout(openModal, 600);
updateUsernameDisplay();

// ── Questions ──────────────────────────────────────────────
let allQuestions = [];

async function loadQuestions() {
  const grid = document.getElementById("question-grid");
  try {
    const res = await fetch(`${API_BASE}/questions`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    allQuestions = await res.json();
    updateStats(allQuestions);
    renderGrid(allQuestions);
  } catch (err) {
    grid.innerHTML = `
      <div style="grid-column:1/-1;text-align:center;padding:48px 0;color:var(--text-secondary)">
        <div style="font-size:40px;margin-bottom:12px">⚠️</div>
        <div style="font-weight:600;color:var(--text-primary);margin-bottom:6px">Backend not reachable</div>
        <div style="font-size:13px">Make sure the Flask server is running on <code style="color:var(--accent)">localhost:5000</code></div>
        <button class="btn btn-ghost btn-sm" onclick="loadQuestions()" style="margin-top:16px">Retry</button>
      </div>`;
  }
}

function updateStats(questions) {
  document.getElementById("stat-total").textContent  = questions.length;
  document.getElementById("stat-easy").textContent   = questions.filter(q => q.difficulty === "Easy").length;
  document.getElementById("stat-medium").textContent = questions.filter(q => q.difficulty === "Medium").length;
  document.getElementById("stat-hard").textContent   = questions.filter(q => q.difficulty === "Hard").length;
}

function difficultyBadgeClass(d) {
  return { Easy: "badge-easy", Medium: "badge-medium", Hard: "badge-hard" }[d] || "badge-info";
}

function formatTime(seconds) {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return m > 0 ? `${m}m` : `${s}s`;
}

function renderGrid(questions) {
  const grid = document.getElementById("question-grid");

  if (questions.length === 0) {
    grid.innerHTML = `
      <div style="grid-column:1/-1;text-align:center;padding:48px 0;color:var(--text-secondary)">
        <div style="font-size:40px;margin-bottom:12px">🔍</div>
        <div>No problems match your filter.</div>
      </div>`;
    return;
  }

  grid.innerHTML = questions.map((q, i) => `
    <a class="question-card" href="editor.html?id=${q.id}" id="qcard-${q.id}">
      <div class="question-card-header">
        <span class="question-number">#${i + 1}</span>
        <span class="badge ${difficultyBadgeClass(q.difficulty)}">${q.difficulty}</span>
      </div>
      <div class="question-title">${escHtml(q.title)}</div>
      <div class="question-card-desc">${escHtml(truncate(q.description, 120))}</div>
      <div class="question-meta">
        <span>🧪 ${q.test_case_count ?? 0} test cases</span>
        ${q.time_limit ? `<span>⏱ ${formatTime(q.time_limit)}</span>` : ""}
      </div>
    </a>`).join("");
}

function escHtml(str) {
  return String(str).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}

function truncate(str, len) {
  return str && str.length > len ? str.slice(0, len) + "…" : str;
}

// ── Filters & Search ──────────────────────────────────────
let activeFilter = "All";

document.querySelectorAll(".filter-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".filter-btn").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    activeFilter = btn.dataset.filter;
    applyFilters();
  });
});

document.getElementById("search-input").addEventListener("input", applyFilters);

function applyFilters() {
  const query = document.getElementById("search-input").value.toLowerCase();
  const filtered = allQuestions.filter(q => {
    const matchDiff = activeFilter === "All" || q.difficulty === activeFilter;
    const matchSearch = !query || q.title.toLowerCase().includes(query) || (q.description || "").toLowerCase().includes(query);
    return matchDiff && matchSearch;
  });
  renderGrid(filtered);
}

// ── Init ───────────────────────────────────────────────────
loadQuestions();
