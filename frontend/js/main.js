/* ════════════════════════════════════════════════════════
   main.js — Index page logic
   ════════════════════════════════════════════════════════ */

// Local development: http://localhost:5000
// Production (Render): https://codearena-r5yq.onrender.com
const API_BASE = "https://codearena-r5yq.onrender.com";

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

// ── Google Sign-In event listener ─────────────────────────
// Show welcome toast when user signs in
window.addEventListener("codearena:signin", (e) => {
  showToast("success", `Hello, ${e.detail.name}! 👋`, "You're signed in with Google.");
});

// ── Questions ──────────────────────────────────────────────
let allQuestions = [];

async function loadQuestions() {
  const grid = document.getElementById("question-grid");
  try {
    const res = await fetch(`${API_BASE}/questions`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    // Attach permanent problem number based on original list order
    allQuestions = data.map((q, idx) => ({ ...q, _num: idx + 1 }));
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

  grid.innerHTML = questions.map((q) => {
    const isMcq = q.type === "mcq";
    const typeBadge = isMcq ? `<span class="badge" style="background:rgba(197,134,192,0.15);color:var(--purple)">MCQ</span>` : `<span class="badge" style="background:rgba(86,156,214,0.15);color:var(--accent)">Coding</span>`;
    const metaInfo = isMcq ? `<span>🔘 MCQ Quiz</span>` : `<span>🧪 ${q.test_case_count ?? 0} test cases</span>`;
    const numDisplay = q._num || 1;

    return `
    <a class="question-card" href="editor.html?id=${q.id}" id="qcard-${q.id}">
      <div class="question-card-header">
        <span class="question-number">#${numDisplay}</span>
        <div style="display:flex;gap:6px">
          ${typeBadge}
          <span class="badge ${difficultyBadgeClass(q.difficulty)}">${q.difficulty}</span>
        </div>
      </div>
      <div class="question-title">${escHtml(q.title)}</div>
      <div class="question-card-desc">${escHtml(truncate(q.description, 120))}</div>
      <div class="question-meta">
        ${metaInfo}
        ${q.time_limit ? `<span>⏱ ${formatTime(q.time_limit)}</span>` : ""}
      </div>
    </a>`;
  }).join("");
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
  const query = document.getElementById("search-input").value.trim().toLowerCase();
  const cleanQuery = query.replace(/^#/, "");

  const filtered = allQuestions.filter((q, index) => {
    const matchDiff = activeFilter === "All" || q.difficulty === activeFilter;
    
    if (!query) return matchDiff;

    const problemNumber = String(index + 1);
    const matchNumber = problemNumber === cleanQuery || `#${problemNumber}` === query;
    const matchTitle = q.title.toLowerCase().includes(query);
    const matchDesc = (q.description || "").toLowerCase().includes(query);
    const matchId = (q.id || "").toLowerCase().includes(cleanQuery);

    return matchDiff && (matchNumber || matchTitle || matchDesc || matchId);
  });
  renderGrid(filtered);
}

// ── User Rank & Progress Banner ────────────────────────────
async function loadUserRankProgress() {
  const banner = document.getElementById("user-rank-banner");
  if (!banner) return;

  // Retrieve user test history from localStorage or API
  let lastScore = localStorage.getItem("codearena_last_score");
  let lastRank = localStorage.getItem("codearena_last_rank");
  let attempts = localStorage.getItem("codearena_test_attempts") || "0";

  try {
    const res = await fetch(`${API_BASE}/questions/placement/leaderboard`);
    if (res.ok) {
      const data = await res.json();
      if (data.total_attempts) {
        attempts = data.total_attempts;
      }
    }
  } catch(e) {}

  if (lastScore !== null || attempts > 0) {
    banner.style.display = "block";
    document.getElementById("user-last-mark").textContent = `${lastScore ?? 0} pts`;
    document.getElementById("user-current-rank").textContent = `#${lastRank ?? 1}`;
    document.getElementById("user-test-attempts").textContent = attempts;
  }
}

// ── Init ───────────────────────────────────────────────────
loadQuestions();
loadUserRankProgress();
