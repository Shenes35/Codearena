/* ════════════════════════════════════════════════════════
   admin.js — Admin panel logic
   ════════════════════════════════════════════════════════ */

const API_BASE = "http://localhost:5000";
const ADMIN_PASS_KEY = "codearena_admin_pass";

// ── Toast ──────────────────────────────────────────────────
function showToast(type, title, body = "", duration = 4000) {
  const container = document.getElementById("toast-container");
  const icons = { success: "✅", error: "❌", info: "ℹ️" };
  const el = document.createElement("div");
  el.className = `toast toast-${type}`;
  el.innerHTML = `
    <div class="toast-icon">${icons[type] || "📌"}</div>
    <div>
      <div class="toast-title">${title}</div>
      ${body ? `<div class="toast-body">${body}</div>` : ""}
    </div>`;
  container.appendChild(el);
  setTimeout(() => { el.style.opacity="0"; el.style.transition="opacity 0.4s"; setTimeout(()=>el.remove(),400); }, duration);
}

// ── Auth ───────────────────────────────────────────────────
let adminPassword = sessionStorage.getItem(ADMIN_PASS_KEY) || "";

function showAdminPanel() {
  document.getElementById("auth-modal").style.display = "none";
  document.getElementById("admin-main").style.display = "block";
  loadQuestions();
}

// Restore session if already logged in
if (adminPassword) showAdminPanel();

document.getElementById("btn-admin-login").addEventListener("click", async () => {
  const pw = document.getElementById("admin-password-input").value;
  const err = document.getElementById("auth-error");
  err.classList.add("hidden");

  if (!pw) { document.getElementById("admin-password-input").focus(); return; }

  // Verify password against backend by making an admin-only request
  try {
    const res = await fetch(`${API_BASE}/questions`, { method: "GET" });
    // If fetch works, try a lightweight admin check via POST (add+delete)
    // We'll just trust the header-based auth on actual actions.
    // For now, validate by checking the password against backend's known value.
    // Simple approach: try to POST a dummy request and check 401
    const checkRes = await fetch(`${API_BASE}/questions`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Admin-Password": pw },
      body: JSON.stringify({ title: "__auth_check__", description: "x", test_cases: [{ input: "x", expected: "x" }] }),
    });

    if (checkRes.status === 401) {
      err.classList.remove("hidden");
      return;
    }

    // If we accidentally created a question, delete it
    if (checkRes.ok) {
      const q = await checkRes.json();
      if (q.id) {
        await fetch(`${API_BASE}/questions/${q.id}`, {
          method: "DELETE",
          headers: { "X-Admin-Password": pw },
        });
      }
    }

    adminPassword = pw;
    sessionStorage.setItem(ADMIN_PASS_KEY, pw);
    showAdminPanel();
  } catch (_) {
    // Backend unreachable – still allow local usage
    adminPassword = pw;
    sessionStorage.setItem(ADMIN_PASS_KEY, pw);
    showAdminPanel();
    showToast("warn", "Backend Unreachable", "Using cached credentials. Some features may not work.");
  }
});

document.getElementById("admin-password-input").addEventListener("keydown", e => {
  if (e.key === "Enter") document.getElementById("btn-admin-login").click();
});

document.getElementById("btn-logout").addEventListener("click", () => {
  adminPassword = "";
  sessionStorage.removeItem(ADMIN_PASS_KEY);
  location.reload();
});

// ── Test Cases ─────────────────────────────────────────────
let testCaseCount = 0;

function addTestCase(inputVal = "", expectedVal = "") {
  testCaseCount++;
  const id = `tc-${testCaseCount}`;
  const noMsg = document.getElementById("no-tc-msg");
  if (noMsg) noMsg.style.display = "none";

  const row = document.createElement("div");
  row.className = "test-case-row";
  row.id = id;
  row.innerHTML = `
    <textarea class="form-control" placeholder="stdin input…" rows="2" data-role="input">${escHtml(inputVal)}</textarea>
    <textarea class="form-control" placeholder="expected output…" rows="2" data-role="expected">${escHtml(expectedVal)}</textarea>
    <button class="btn btn-danger btn-sm" onclick="removeRow('${id}')" title="Remove">✕</button>`;

  document.getElementById("test-cases-list").appendChild(row);
}

// ── Examples ───────────────────────────────────────────────
let exampleCount = 0;

function addExample(inputVal = "", outputVal = "") {
  exampleCount++;
  const id = `ex-${exampleCount}`;
  const noMsg = document.getElementById("no-examples-msg");
  if (noMsg) noMsg.style.display = "none";

  const row = document.createElement("div");
  row.className = "test-case-row";
  row.id = id;
  row.innerHTML = `
    <textarea class="form-control" placeholder="example input…" rows="2" data-role="input">${escHtml(inputVal)}</textarea>
    <textarea class="form-control" placeholder="example output…" rows="2" data-role="output">${escHtml(outputVal)}</textarea>
    <button class="btn btn-danger btn-sm" onclick="removeRow('${id}')" title="Remove">✕</button>`;

  document.getElementById("examples-list").appendChild(row);
}

function removeRow(id) {
  const el = document.getElementById(id);
  if (el) el.remove();
}

document.getElementById("btn-add-tc").addEventListener("click", () => addTestCase());
document.getElementById("btn-add-example").addEventListener("click", () => addExample());

// Add one empty test case on load
addTestCase();
addExample();

// ── Collect Form Data ──────────────────────────────────────
function collectTestCases() {
  const rows = document.querySelectorAll("#test-cases-list .test-case-row");
  const tcs = [];
  rows.forEach(row => {
    const inp = row.querySelector("[data-role='input']")?.value?.trim() ?? "";
    const exp = row.querySelector("[data-role='expected']")?.value?.trim() ?? "";
    if (inp || exp) tcs.push({ input: inp, expected: exp });
  });
  return tcs;
}

function collectExamples() {
  const rows = document.querySelectorAll("#examples-list .test-case-row");
  const exs = [];
  rows.forEach(row => {
    const inp = row.querySelector("[data-role='input']")?.value?.trim() ?? "";
    const out = row.querySelector("[data-role='output']")?.value?.trim() ?? "";
    if (inp || out) exs.push({ input: inp, output: out });
  });
  return exs;
}

// ── Create Question ────────────────────────────────────────
document.getElementById("btn-create-question").addEventListener("click", async () => {
  const feedback = document.getElementById("form-feedback");
  feedback.classList.add("hidden");

  const title       = document.getElementById("q-title").value.trim();
  const description = document.getElementById("q-description").value.trim();
  const difficulty  = document.getElementById("q-difficulty").value;
  const timeLimit   = parseInt(document.getElementById("q-time-limit").value, 10) || 1800;
  const inputFmt    = document.getElementById("q-input-format").value.trim();
  const outputFmt   = document.getElementById("q-output-format").value.trim();
  const testCases   = collectTestCases();
  const examples    = collectExamples();

  // Validation
  if (!title) {
    showFeedback("error", "Title is required.");
    document.getElementById("q-title").focus();
    return;
  }
  if (!description) {
    showFeedback("error", "Description is required.");
    document.getElementById("q-description").focus();
    return;
  }
  if (testCases.length === 0) {
    showFeedback("error", "At least one test case is required.");
    return;
  }
  for (let i = 0; i < testCases.length; i++) {
    if (!testCases[i].expected) {
      showFeedback("error", `Test case ${i + 1} is missing expected output.`);
      return;
    }
  }

  const btn = document.getElementById("btn-create-question");
  btn.disabled = true;
  btn.innerHTML = `<div class="spinner"></div> Creating…`;

  try {
    const res = await fetch(`${API_BASE}/questions`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Admin-Password": adminPassword },
      body: JSON.stringify({
        title, description, difficulty,
        time_limit: timeLimit,
        input_format: inputFmt,
        output_format: outputFmt,
        test_cases: testCases,
        examples,
      }),
    });

    const data = await res.json();
    if (!res.ok) {
      showFeedback("error", data.error || "Failed to create question.");
    } else {
      showFeedback("success", `Question "${data.title}" created! (ID: ${data.id})`);
      showToast("success", "Question Created 🎉", data.title);
      resetForm();
      loadQuestions();
    }
  } catch (err) {
    showFeedback("error", `Network error: ${err.message}`);
  } finally {
    btn.disabled = false;
    btn.innerHTML = "🚀 Create Question";
  }
});

function showFeedback(type, msg) {
  const el = document.getElementById("form-feedback");
  el.classList.remove("hidden");
  el.style.background = type === "success" ? "rgba(78,201,176,0.12)" : "rgba(244,71,71,0.12)";
  el.style.color = type === "success" ? "var(--green)" : "var(--red)";
  el.style.border = `1px solid ${type === "success" ? "var(--green)" : "var(--red)"}`;
  el.textContent = msg;
  el.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function escHtml(str) {
  return String(str || "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}

// ── Reset Form ────────────────────────────────────────────
document.getElementById("btn-reset-form").addEventListener("click", resetForm);

function resetForm() {
  document.getElementById("q-title").value = "";
  document.getElementById("q-description").value = "";
  document.getElementById("q-input-format").value = "";
  document.getElementById("q-output-format").value = "";
  document.getElementById("q-difficulty").value = "Medium";
  document.getElementById("q-time-limit").value = "1800";
  document.getElementById("form-feedback").classList.add("hidden");

  document.getElementById("test-cases-list").innerHTML = "";
  document.getElementById("examples-list").innerHTML = "";
  testCaseCount = 0;
  exampleCount  = 0;
  document.getElementById("no-tc-msg").style.display = "";
  document.getElementById("no-examples-msg").style.display = "";
  addTestCase();
  addExample();
}

// ── Load Questions List ───────────────────────────────────
async function loadQuestions() {
  const list = document.getElementById("questions-list");
  list.innerHTML = `<div class="skeleton" style="height:48px"></div><div class="skeleton" style="height:48px;margin-top:8px"></div>`;

  try {
    const res = await fetch(`${API_BASE}/questions`);
    const questions = await res.json();

    if (questions.length === 0) {
      list.innerHTML = `<p style="color:var(--text-dim);font-size:13px;text-align:center;padding:16px">No questions yet. Create one above!</p>`;
      return;
    }

    const diffBadge = d => {
      const cls = { Easy: "badge-easy", Medium: "badge-medium", Hard: "badge-hard" }[d] || "badge-info";
      return `<span class="badge ${cls}">${d}</span>`;
    };

    list.innerHTML = questions.map(q => `
      <div class="question-list-item" id="qli-${q.id}">
        <div>
          <div class="question-list-title">${escHtml(q.title)}</div>
          <div style="font-size:11px;color:var(--text-dim);margin-top:2px">${q.test_case_count ?? 0} test cases</div>
        </div>
        <div style="display:flex;align-items:center;gap:8px">
          ${diffBadge(q.difficulty)}
          <a href="editor.html?id=${q.id}" target="_blank" class="btn btn-ghost btn-sm">Preview</a>
          <button class="btn btn-danger btn-sm" onclick="deleteQuestion('${q.id}','${escHtml(q.title)}')">Delete</button>
        </div>
      </div>`).join("");
  } catch (_) {
    list.innerHTML = `<p style="color:var(--red);font-size:13px">Failed to load questions.</p>`;
  }
}

// ── Delete Question ───────────────────────────────────────
async function deleteQuestion(id, title) {
  if (!confirm(`Delete "${title}"? This cannot be undone.`)) return;

  try {
    const res = await fetch(`${API_BASE}/questions/${id}`, {
      method: "DELETE",
      headers: { "X-Admin-Password": adminPassword },
    });
    const data = await res.json();
    if (res.ok) {
      showToast("success", "Deleted", title);
      loadQuestions();
    } else {
      showToast("error", "Error", data.error || "Delete failed.");
    }
  } catch (err) {
    showToast("error", "Network error", err.message);
  }
}
