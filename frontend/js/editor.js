/* ════════════════════════════════════════════════════════
   editor.js — Code editor page logic
   Monaco Editor + Judge0 + Submit to backend
   ════════════════════════════════════════════════════════ */

// Local development: http://localhost:5000
// Production (Render): https://codearena-r5yq.onrender.com
const API_BASE = "https://codearena-r5yq.onrender.com";

// ── Utils ──────────────────────────────────────────────────
// Get display name/email from Google Sign-In (auth.js) or fallback to "Guest"
function getUsername() {
  if (window.CA_Auth) {
    const user = CA_Auth.getUser();
    if (user && user.email) return `${user.name} (${user.email})`;
    if (user && user.name) return user.name;
  }
  try {
    const stored = localStorage.getItem("codearena_user");
    if (stored) {
      const u = JSON.parse(stored);
      if (u.email) return `${u.name || 'User'} (${u.email})`;
    }
  } catch(e){}
  return "Guest";
}

function escHtml(str) {
  return String(str).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}

function showToast(type, title, body = "", duration = 5000) {
  const container = document.getElementById("toast-container");
  const icons = { success: "✅", error: "❌", info: "ℹ️", warn: "⚠️" };
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

// ── State ──────────────────────────────────────────────────
let questionData = null;
let monacoEditor = null;
let timerInterval = null;
let timeRemaining = 0;
let allTestsPassed = false;

// ── URL Params ─────────────────────────────────────────────
const params = new URLSearchParams(window.location.search);
const questionId = params.get("id");

if (!questionId) {
  window.location.href = "index.html";
}

// ── Language templates ─────────────────────────────────────
const TEMPLATES = {
  python: `# Write your Python solution here
import sys
input_data = sys.stdin.read().strip()

# Your code below
`,
  javascript: `// Write your JavaScript solution here
const readline = require('readline');
const rl = readline.createInterface({ input: process.stdin });
const lines = [];
rl.on('line', l => lines.push(l));
rl.on('close', () => {
  // Your code below
  
});
`,
  cpp: `#include <bits/stdc++.h>
using namespace std;

int main() {
  // Your code below
  
  return 0;
}
`,
  java: `import java.util.*;
import java.io.*;

public class Main {
  public static void main(String[] args) throws IOException {
    BufferedReader br = new BufferedReader(new InputStreamReader(System.in));
    // Your code below
    
  }
}
`,
  c: `#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main() {
  // Your code below
  
  return 0;
}
`,
};

const MONACO_LANG_MAP = {
  python: "python", javascript: "javascript", cpp: "cpp", java: "java", c: "c",
};

// ── Init Monaco ────────────────────────────────────────────
function initMonaco(language = "python") {
  require(["vs/editor/editor.main"], function () {
    // Define CodeArena dark theme
    monaco.editor.defineTheme("codearena-dark", {
      base: "vs-dark",
      inherit: true,
      rules: [
        { token: "comment", foreground: "6a9955" },
        { token: "keyword", foreground: "569cd6", fontStyle: "bold" },
        { token: "string", foreground: "ce9178" },
        { token: "number", foreground: "b5cea8" },
      ],
      colors: {
        "editor.background":           "#1e1e1e",
        "editor.foreground":           "#d4d4d4",
        "editorLineNumber.foreground": "#5a6472",
        "editor.lineHighlightBackground": "#2a2d2e",
        "editorCursor.foreground":     "#569cd6",
        "editor.selectionBackground":  "#264f78",
        "editorSuggestWidget.background": "#252526",
        "editorSuggestWidget.border":  "#454545",
      },
    });

    monacoEditor = monaco.editor.create(document.getElementById("monaco-editor"), {
      value:        TEMPLATES[language] || TEMPLATES.python,
      language:     MONACO_LANG_MAP[language] || "python",
      theme:        "codearena-dark",
      fontSize:     14,
      fontFamily:   "'JetBrains Mono', 'Fira Code', Consolas, monospace",
      fontLigatures: true,
      minimap:       { enabled: false },
      scrollBeyondLastLine: false,
      automaticLayout: true,
      tabSize:       4,
      wordWrap:      "on",
      lineNumbers:   "on",
      renderLineHighlight: "line",
      suggestOnTriggerCharacters: true,
      quickSuggestions: true,
    });
  });
}

// ── Auth chip updated by auth.js automatically ─────────────
// (no manual username-badge needed — auth.js populates #auth-chip)

// ── Problem Panel Tabs ─────────────────────────────────────
document.querySelectorAll(".panel-tab").forEach(tab => {
  tab.addEventListener("click", () => {
    const tabName = tab.dataset.tab;
    document.querySelectorAll(".panel-tab").forEach(t => t.classList.remove("active"));
    tab.classList.add("active");
    document.getElementById("tab-description").classList.add("hidden");
    document.getElementById("tab-examples").classList.add("hidden");
    document.getElementById("tab-submissions").classList.add("hidden");
    document.getElementById(`tab-${tabName}`).classList.remove("hidden");
  });
});

// ── Console Tabs ───────────────────────────────────────────
document.querySelectorAll(".console-tab").forEach(tab => {
  tab.addEventListener("click", () => {
    const ctab = tab.dataset.ctab;
    document.querySelectorAll(".console-tab").forEach(t => t.classList.remove("active"));
    tab.classList.add("active");
    document.getElementById("ctab-output").classList.add("hidden");
    document.getElementById("ctab-testcases").classList.add("hidden");
    document.getElementById("ctab-stdin").classList.add("hidden");
    document.getElementById(`ctab-${ctab}`).classList.remove("hidden");

    // Fix flex display for test results
    const tcEl = document.getElementById("ctab-testcases");
    if (ctab === "testcases") tcEl.classList.remove("hidden");
  });
});

// ── Language Change ────────────────────────────────────────
document.getElementById("language-select").addEventListener("change", e => {
  const lang = e.target.value;
  if (monacoEditor) {
    monaco.editor.setModelLanguage(monacoEditor.getModel(), MONACO_LANG_MAP[lang] || lang);
    // Only reset if editor still has a template
    const current = monacoEditor.getValue();
    const isTemplate = Object.values(TEMPLATES).includes(current.trimEnd() + "\n") || Object.values(TEMPLATES).includes(current);
    if (isTemplate) monacoEditor.setValue(TEMPLATES[lang] || "");
  }
});

// ── Reset Button ──────────────────────────────────────────
document.getElementById("btn-reset").addEventListener("click", () => {
  const lang = document.getElementById("language-select").value;
  if (monacoEditor) monacoEditor.setValue(TEMPLATES[lang] || "");
});

// ── Clear Console ─────────────────────────────────────────
document.getElementById("btn-clear-console").addEventListener("click", () => {
  document.getElementById("ctab-output").innerHTML = '<span class="console-placeholder">Console cleared.</span>';
  document.getElementById("run-status-badge").textContent = "";
});

// ── Resize Panel ──────────────────────────────────────────
(function setupResize() {
  const handle = document.getElementById("resize-handle");
  const panel  = document.getElementById("problem-panel");
  let dragging = false;
  let startX, startWidth;

  handle.addEventListener("mousedown", e => {
    dragging = true;
    startX = e.clientX;
    startWidth = panel.getBoundingClientRect().width;
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
  });

  window.addEventListener("mousemove", e => {
    if (!dragging) return;
    const newWidth = Math.min(700, Math.max(240, startWidth + e.clientX - startX));
    panel.style.width = newWidth + "px";
    if (monacoEditor) monacoEditor.layout();
  });

  window.addEventListener("mouseup", () => {
    dragging = false;
    document.body.style.cursor = "";
    document.body.style.userSelect = "";
  });
})();

// ── Timer ─────────────────────────────────────────────────
function startTimer(seconds) {
  timeRemaining = seconds;
  const widget = document.getElementById("timer-widget");
  const display = document.getElementById("timer-display");

  function tick() {
    if (timeRemaining <= 0) {
      clearInterval(timerInterval);
      display.textContent = "00:00";
      widget.className = "timer-widget danger";
      showToast("error", "⏱ Time's up!", "You can still submit but time has expired.");
      return;
    }
    const m = Math.floor(timeRemaining / 60).toString().padStart(2, "0");
    const s = (timeRemaining % 60).toString().padStart(2, "0");
    display.textContent = `${m}:${s}`;

    if (timeRemaining <= 60)       widget.className = "timer-widget danger";
    else if (timeRemaining <= 300) widget.className = "timer-widget warning";
    else                            widget.className = "timer-widget";

    timeRemaining--;
  }

  tick();
  timerInterval = setInterval(tick, 1000);
}

// ── Load Question ──────────────────────────────────────────
async function loadQuestion() {
  try {
    const res = await fetch(`${API_BASE}/questions/${questionId}`);
    if (!res.ok) throw new Error("Question not found");
    questionData = await res.json();

    // Navbar title
    document.getElementById("nav-problem-title").textContent = questionData.title;
    document.title = `CodeArena — ${questionData.title}`;

    // Problem panel
    document.getElementById("problem-loading").style.display = "none";
    document.getElementById("problem-content").classList.remove("hidden");
    document.getElementById("problem-title").textContent = questionData.title;

    const diffEl = document.getElementById("problem-difficulty");
    diffEl.textContent = questionData.difficulty || "Medium";
    diffEl.className = `badge badge-${(questionData.difficulty || "medium").toLowerCase()}`;

    const isMcq = questionData.type === "mcq";

    document.getElementById("problem-tc-count").textContent = isMcq ? "MCQ Quiz" : `${questionData.test_case_count || 0} test cases`;
    document.getElementById("problem-description").textContent = questionData.description || "";
    
    if (isMcq) {
      document.getElementById("lbl-input-format").style.display = "none";
      document.getElementById("problem-input-format").style.display = "none";
      document.getElementById("lbl-output-format").style.display = "none";
      document.getElementById("problem-output-format").style.display = "none";

      // Render MCQ Options in right panel editor
      const editorPanel = document.querySelector(".editor-panel");
      if (editorPanel) {
        editorPanel.innerHTML = `
          <div style="padding:32px;max-width:640px;margin:0 auto;width:100%;display:flex;flex-direction:column;gap:20px">
            <h2 style="font-size:18px;font-weight:700;color:var(--text-bright)">Select your answer:</h2>
            <div id="mcq-options-group" style="display:flex;flex-direction:column;gap:12px">
              ${(questionData.options || []).map((opt, idx) => `
                <label style="display:flex;align-items:center;gap:12px;padding:14px 18px;background:var(--bg-card);border:1px solid var(--border);border-radius:var(--radius);cursor:pointer;transition:all 0.2s ease" class="mcq-opt-label">
                  <input type="radio" name="user_mcq_answer" value="${idx}" style="width:18px;height:18px;cursor:pointer" />
                  <span style="font-size:14px;color:var(--text-primary)">${escHtml(opt)}</span>
                </label>
              `).join("")}
            </div>
            <div style="display:flex;gap:12px;margin-top:12px">
              <button class="btn btn-primary btn-lg" id="btn-submit-mcq" style="flex:1">Submit Answer</button>
            </div>
            <div id="mcq-result" class="hidden" style="padding:16px;border-radius:var(--radius);font-weight:600;font-size:14px"></div>
          </div>
        `;

        document.getElementById("btn-submit-mcq")?.addEventListener("click", async () => {
          const selected = document.querySelector('input[name="user_mcq_answer"]:checked')?.value;
          if (selected === undefined) {
            showToast("warn", "Please select an answer!");
            return;
          }
          try {
            const res = await fetch(`${API_BASE}/questions/${questionId}/verify-mcq`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ selected_option: parseInt(selected) }),
            });
            const ans = await res.json();
            const resDiv = document.getElementById("mcq-result");
            resDiv.classList.remove("hidden");
            if (ans.correct) {
              resDiv.style.background = "rgba(78,201,176,0.15)";
              resDiv.style.color = "var(--green)";
              resDiv.style.border = "1px solid var(--green)";
              resDiv.textContent = "✅ Correct Answer! Great job.";
              showToast("success", "Correct! 🎉");
            } else {
              resDiv.style.background = "rgba(244,71,71,0.15)";
              resDiv.style.color = "var(--red)";
              resDiv.style.border = "1px solid var(--red)";
              resDiv.textContent = `❌ Incorrect. Correct option was: ${questionData.options[ans.correct_option] || 'Option ' + (ans.correct_option + 1)}`;
              showToast("error", "Wrong Answer ❌");
            }
          } catch(err) {
            showToast("error", "Network error", err.message);
          }
        });
      }
    } else {
      document.getElementById("problem-input-format").textContent = questionData.input_format || "—";
      document.getElementById("problem-output-format").textContent = questionData.output_format || "—";
    }

    // Examples tab
    const examples = questionData.examples || [];
    const examplesContainer = document.getElementById("examples-container");
    if (examples.length === 0) {
      examplesContainer.innerHTML = `<p style="color:var(--text-dim);font-size:13px">No examples provided.</p>`;
    } else {
      examplesContainer.innerHTML = examples.map((ex, i) => `
        <div style="margin-bottom:16px">
          <div class="problem-section-label">Example ${i + 1}</div>
          <div class="example-block">
            <div class="example-label">Input</div>
            <div class="example-io">${escHtml(ex.input)}</div>
            <div class="example-label" style="margin-top:8px">Output</div>
            <div class="example-io">${escHtml(ex.output)}</div>
          </div>
        </div>`).join("");
    }

    // Start timer
    if (questionData.time_limit) startTimer(questionData.time_limit);
    else document.getElementById("timer-widget").style.display = "none";

    // Init Monaco (if coding)
    if (!isMcq) {
      const lang = document.getElementById("language-select").value;
      initMonaco(lang);
    }

  } catch (err) {
    document.getElementById("problem-loading").innerHTML = `
      <div style="text-align:center;padding:32px 0;color:var(--text-secondary)">
        <div style="font-size:36px;margin-bottom:12px">😕</div>
        <div style="font-weight:600;color:var(--text-primary)">${err.message}</div>
        <a href="index.html" class="btn btn-ghost btn-sm" style="margin-top:12px">← Back</a>
      </div>`;
  }
}

// ── Set Output ─────────────────────────────────────────────
function setOutputText(text, cls = "") {
  const el = document.getElementById("ctab-output");
  el.innerHTML = cls ? `<span class="${cls}">${escHtml(text)}</span>` : escHtml(text);
}

function setRunStatus(text, color = "var(--text-secondary)") {
  const el = document.getElementById("run-status-badge");
  el.textContent = text;
  el.style.color = color;
}

function setButtonLoading(btnId, loading, originalText) {
  const btn = document.getElementById(btnId);
  if (loading) {
    btn.disabled = true;
    btn.innerHTML = `<div class="spinner"></div> ${originalText}`;
  } else {
    btn.innerHTML = originalText;
    btn.disabled = false;
  }
}

// ── Run Code ───────────────────────────────────────────────
document.getElementById("btn-run").addEventListener("click", async () => {
  if (!monacoEditor) return;
  const code     = monacoEditor.getValue();
  const language = document.getElementById("language-select").value;
  const stdin    = document.getElementById("custom-stdin").value;

  if (!code.trim()) { showToast("warn", "No code to run!"); return; }

  // Switch to output tab
  document.querySelectorAll(".console-tab").forEach(t => t.classList.remove("active"));
  document.querySelector('[data-ctab="output"]').classList.add("active");
  document.getElementById("ctab-output").classList.remove("hidden");
  document.getElementById("ctab-testcases").classList.add("hidden");
  document.getElementById("ctab-stdin").classList.add("hidden");

  setButtonLoading("btn-run", true, "▶ Run");
  setOutputText("⏳ Running…", "output-info");
  setRunStatus("Running…");

  try {
    const res = await fetch(`${API_BASE}/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code, language, input: stdin }),
    });
    const data = await res.json();

    if (data.error) {
      setOutputText(`❌ Error: ${data.error}`, "output-error");
      setRunStatus("Error", "var(--red)");
    } else {
      let output = "";
      if (data.compile_output) output += `[Compilation]\n${data.compile_output}\n\n`;
      if (data.stderr)         output += `[Stderr]\n${data.stderr}\n\n`;
      if (data.stdout !== undefined) output += data.stdout || "(no output)";

      const isError = data.status_id >= 4;
      setOutputText(output.trim(), isError ? "output-error" : "output-success");
      setRunStatus(data.status, isError ? "var(--red)" : "var(--green)");
    }
  } catch (err) {
    setOutputText(`❌ Network error: ${err.message}`, "output-error");
    setRunStatus("Error", "var(--red)");
  } finally {
    setButtonLoading("btn-run", false, "▶ Run");
  }
});

// ── Submit ─────────────────────────────────────────────────
document.getElementById("btn-submit").addEventListener("click", async () => {
  if (!monacoEditor || !questionData) return;
  const code     = monacoEditor.getValue();
  const language = document.getElementById("language-select").value;
  const username = getUsername();

  if (!code.trim()) { showToast("warn", "Nothing to submit!"); return; }

  // Switch to test results tab
  document.querySelectorAll(".console-tab").forEach(t => t.classList.remove("active"));
  document.querySelector('[data-ctab="testcases"]').classList.add("active");
  document.getElementById("ctab-output").classList.add("hidden");
  document.getElementById("ctab-testcases").classList.remove("hidden");
  document.getElementById("ctab-stdin").classList.add("hidden");

  // Disable submit + show spinner
  const submitBtn = document.getElementById("btn-submit");
  submitBtn.disabled = true;
  submitBtn.innerHTML = `<div class="spinner"></div> Judging…`;

  const tcEl = document.getElementById("ctab-testcases");
  tcEl.innerHTML = `<div style="display:flex;align-items:center;gap:10px;padding:16px;color:var(--accent);font-size:13px">
    <div class="spinner" style="border-top-color:var(--accent)"></div>
    Running all test cases against your code…
  </div>`;

  try {
    const res = await fetch(`${API_BASE}/submit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, question_id: questionId, code, language }),
    });
    const data = await res.json();

    if (data.error) {
      tcEl.innerHTML = `<div style="color:var(--red);padding:16px">❌ ${escHtml(data.error)}</div>`;
      submitBtn.innerHTML = "✓ Submit";
      submitBtn.disabled = false;
      showToast("error", "Submission Error", data.error);
      return;
    }

    // Render test case results
    renderTestResults(data.test_results || []);

    if (data.all_passed) {
      allTestsPassed = true;
      submitBtn.innerHTML = "✓ Submit";
      submitBtn.disabled = false; // keep enabled so they can re-see overlay
      showSuccessOverlay(data);
      updateSubmissionTab(data);
    } else {
      showToast("error", "Wrong Answer", "Some test cases failed. Fix your code and try again.");
      submitBtn.innerHTML = "✓ Submit";
      submitBtn.disabled = false;
    }

  } catch (err) {
    tcEl.innerHTML = `<div style="color:var(--red);padding:16px">❌ Network error: ${escHtml(err.message)}</div>`;
    submitBtn.innerHTML = "✓ Submit";
    submitBtn.disabled = false;
    showToast("error", "Network error", err.message);
  }
});

// ── Render Test Results ────────────────────────────────────
function renderTestResults(results) {
  const tcEl = document.getElementById("ctab-testcases");
  if (!results || results.length === 0) {
    tcEl.innerHTML = `<p style="color:var(--text-dim);font-size:13px;padding:16px">No test results.</p>`;
    return;
  }

  tcEl.innerHTML = results.map((tc, i) => {
    const cls = tc.passed ? "pass" : "fail";
    const statusText = tc.passed ? "✅ Passed" : "❌ Failed";
    return `
      <div class="test-case-item">
        <div class="test-case-header ${cls}" onclick="this.nextElementSibling.classList.toggle('hidden')">
          <span>Test Case ${i + 1}</span>
          <span class="test-case-status ${cls}">${statusText}</span>
        </div>
        <div class="test-case-body">
          <div class="tc-row"><span class="tc-label">Input</span><span class="tc-val">${escHtml(tc.input || "")}</span></div>
          <div class="tc-row"><span class="tc-label">Expected</span><span class="tc-val" style="color:var(--green)">${escHtml(tc.expected || "")}</span></div>
          <div class="tc-row"><span class="tc-label">Got</span><span class="tc-val" style="color:${tc.passed ? "var(--green)" : "var(--red)"}">${escHtml(tc.got || "(no output)")}</span></div>
          ${tc.stderr ? `<div class="tc-row"><span class="tc-label">Stderr</span><span class="tc-val" style="color:var(--yellow)">${escHtml(tc.stderr)}</span></div>` : ""}
          ${tc.time ? `<div class="tc-row"><span class="tc-label">Time</span><span class="tc-val">${tc.time}s</span></div>` : ""}
        </div>
      </div>`;
  }).join("");
}

// ── Success Overlay ────────────────────────────────────────
function showSuccessOverlay(data) {
  const overlay = document.getElementById("success-overlay");
  overlay.classList.remove("hidden");

  const passed = (data.test_results || []).filter(t => t.passed).length;
  const total  = (data.test_results || []).length;
  document.getElementById("success-subtitle").textContent =
    `${passed}/${total} test cases passed.${data.doc_url ? " Submission saved to Google Drive." : ""}`;

  const viewDocBtn = document.getElementById("btn-view-doc");
  if (data.doc_url) {
    viewDocBtn.href = data.doc_url;
    viewDocBtn.classList.remove("hidden");
  } else {
    viewDocBtn.classList.add("hidden");
  }

  if (data.drive_warning) {
    showToast("warn", "Drive Warning", data.drive_warning, 8000);
  }

  // Stop timer
  clearInterval(timerInterval);
}

document.getElementById("btn-close-overlay").addEventListener("click", () => {
  document.getElementById("success-overlay").classList.add("hidden");
});

// ── Update Submission Tab ─────────────────────────────────
function updateSubmissionTab(data) {
  const el = document.getElementById("submission-info");
  const ts = data.timestamp || new Date().toISOString();
  el.innerHTML = `
    <div class="problem-section-label">Last Submission</div>
    <div style="background:var(--bg-editor);border:1px solid var(--green);border-radius:var(--radius);padding:14px 16px;margin-top:8px">
      <div style="color:var(--green);font-weight:700;margin-bottom:8px">✅ Accepted</div>
      <div style="font-size:12px;color:var(--text-secondary);line-height:2">
        <div>Time: ${ts}</div>
        <div>User: ${escHtml(getUsername())}</div>
        ${data.doc_url ? `<div><a href="${data.doc_url}" target="_blank" style="color:var(--accent)">📄 View Google Doc</a></div>` : ""}
      </div>
    </div>`;
}

// ── Init ───────────────────────────────────────────────────
loadQuestion();
