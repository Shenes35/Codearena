/**
 * exam.js — Placement Exam Engine & State Manager
 */

// Dynamic API_BASE detection (Local vs Production Render)
const API_BASE = window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1"
  ? "http://localhost:5000"
  : "https://codearena-r5yq.onrender.com";

let examData = {
  mcqs: [],
  coding: [],
  durationMinutes: 60
};

let userState = {
  activeTab: "mcq", // "mcq" or "coding"
  currentMcqIdx: 0,
  currentCodingIdx: 0,
  mcqAnswers: {}, // qid -> index
  mcqMarked: {},  // qid -> bool
  codingSolutions: {}, // qid -> string
  timeRemainingSeconds: 3600,
  timerInterval: null
};

let testMode = "full"; // "mcq", "coding", "resume", or "full"

document.addEventListener("DOMContentLoaded", () => {
  const urlParams = new URLSearchParams(window.location.search);
  testMode = urlParams.get("mode") || "full";
  initExam();
});

async function initExam() {
  setupEventListeners();
  await fetchPlacementQuestions();

  if (testMode === "mcq") {
    document.getElementById("tab-coding").style.display = "none";
    document.getElementById("coding-palette-container")?.style.setProperty("display", "none", "important");
    userState.timeRemainingSeconds = 40 * 60; // 40 mins for MCQ test
    switchTab("mcq");
  } else if (testMode === "resume") {
    document.getElementById("tab-coding").style.display = "none";
    document.getElementById("coding-palette-container")?.style.setProperty("display", "none", "important");
    userState.timeRemainingSeconds = 40 * 60; // 40 mins for Resume MCQ test (30 Qs)
    const tabMcqLabel = document.querySelector("#tab-mcq span:first-child");
    if (tabMcqLabel) tabMcqLabel.textContent = "📄 Section A: MCQs";
    switchTab("mcq");
  } else if (testMode === "coding") {
    document.getElementById("tab-mcq").style.display = "none";
    document.getElementById("mcq-palette-container")?.style.setProperty("display", "none", "important");
    userState.timeRemainingSeconds = 45 * 60; // 45 mins for Coding test
    switchTab("coding");
  } else {
    switchTab("mcq");
  }

  renderMcqPalette();
  renderCodingPalette();
  if (testMode !== "coding") renderCurrentMcq();
  else renderCurrentCoding();

  startTimer();
  setupProctoring();
}

async function fetchPlacementQuestions() {
  try {
    const res = await fetch(`${API_BASE}/questions/placement?mode=${testMode}`);
    if (!res.ok) throw new Error("Failed to fetch placement exam payload");
    const data = await res.json();
    
    examData.mcqs = data.mcq_questions || [];
    examData.coding = data.coding_questions || [];
    examData.durationMinutes = data.duration_minutes || (testMode === "coding" ? 45 : 40);
    userState.timeRemainingSeconds = examData.durationMinutes * 60;

    document.getElementById("mcq-badge-count").textContent = `${examData.mcqs.length} Qs`;
    document.getElementById("coding-badge-count").textContent = `${examData.coding.length} Qs`;
  } catch (err) {
    console.error("Exam payload fetch error:", err);
    if (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1") {
      alert("Backend connection issue. Make sure your local Flask server is running at http://localhost:5000");
    } else {
      alert("Connecting to backend server... If backend on Render was asleep, please wait 30 seconds and refresh the page.");
    }
  }
}

function setupEventListeners() {
  // Tabs
  document.getElementById("tab-mcq").addEventListener("click", () => switchTab("mcq"));
  document.getElementById("tab-coding").addEventListener("click", () => switchTab("coding"));

  // MCQ Controls
  document.getElementById("btn-mcq-next").addEventListener("click", () => {
    if (userState.currentMcqIdx < examData.mcqs.length - 1) {
      userState.currentMcqIdx++;
      renderCurrentMcq();
      renderMcqPalette();
    }
  });

  document.getElementById("btn-mcq-prev").addEventListener("click", () => {
    if (userState.currentMcqIdx > 0) {
      userState.currentMcqIdx--;
      renderCurrentMcq();
      renderMcqPalette();
    }
  });

  document.getElementById("btn-mcq-clear").addEventListener("click", () => {
    const q = examData.mcqs[userState.currentMcqIdx];
    if (q) {
      delete userState.mcqAnswers[q.id];
      renderCurrentMcq();
      renderMcqPalette();
    }
  });

  document.getElementById("btn-mcq-review").addEventListener("click", () => {
    const q = examData.mcqs[userState.currentMcqIdx];
    if (q) {
      userState.mcqMarked[q.id] = !userState.mcqMarked[q.id];
      renderMcqPalette();
    }
  });

  // Coding Controls
  document.getElementById("btn-coding-next").addEventListener("click", () => {
    saveCodingCurrentSolution();
    if (userState.currentCodingIdx < examData.coding.length - 1) {
      userState.currentCodingIdx++;
      renderCurrentCoding();
      renderCodingPalette();
    }
  });

  document.getElementById("btn-coding-prev").addEventListener("click", () => {
    saveCodingCurrentSolution();
    if (userState.currentCodingIdx > 0) {
      userState.currentCodingIdx--;
      renderCurrentCoding();
      renderCodingPalette();
    }
  });

  document.getElementById("btn-submit-exam").addEventListener("click", () => {
    if (confirm("Are you sure you want to finish and submit your Placement Exam?")) {
      submitExam();
    }
  });
}

function switchTab(tab) {
  userState.activeTab = tab;
  document.getElementById("tab-mcq").classList.toggle("active", tab === "mcq");
  document.getElementById("tab-coding").classList.toggle("active", tab === "coding");

  document.getElementById("mcq-container").style.display = tab === "mcq" ? "flex" : "none";
  document.getElementById("coding-container").style.display = tab === "coding" ? "flex" : "none";

  if (tab === "mcq") renderCurrentMcq();
  else renderCurrentCoding();
}

let isReviewMode = false;
let examResultDetails = null;

function formatMcqCodeBlocks(text) {
  if (!text) return "";
  
  // Normalize triple backticks formatting:
  // E.g., ```text Begin ... ``` -> convert into clean line breaks
  let cleanText = text
    .replace(/```([a-z]*)\s*/gi, "\n\n```$1\n")
    .replace(/```/g, "\n```\n");

  // Fix single line pseudocode / C / Java statements inside code block
  cleanText = cleanText.replace(/```([a-z]*)\n([\s\S]*?)\n```/gi, (match, lang, code) => {
    let formattedCode = code
      .replace(/\s*Set\s+/g, '\nSet ')
      .replace(/\s*Print\s+/g, '\nPrint ')
      .replace(/\s*Begin\s+/g, 'Begin\n')
      .replace(/\s*End\b/g, '\nEnd')
      .replace(/;\s*/g, ';\n')
      .replace(/\{\s*/g, '{\n')
      .replace(/\}\s*/g, '\n}\n')
      .split('\n')
      .map(l => l.trim())
      .filter(l => l.length > 0)
      .join('\n');

    return `\n\n\`\`\`${lang || 'c'}\n${formattedCode}\n\`\`\`\n\n`;
  });

  return cleanText;
}

function parseMarkdownToHtml(markdownText) {
  if (!markdownText) return "";
  
  let html = markdownText;

  // 1. Detect if the text contains code (either with backticks or raw single-line statements)
  // Match backtick blocks: e.g. ```text ... ``` or ```python ... ``` or raw statements
  const hasBackticks = /[`\u2018\u2019\u201C\u201D]{2,}/.test(html);
  
  if (hasBackticks) {
    // Extract everything between the backtick markers:
    html = html.replace(/[`\u2018\u2019\u201C\u201D]{2,}\s*([a-zA-Z]*)([\s\S]*?)[`\u2018\u2019\u201C\u201D]{2,}/gi, (match, lang, code) => {
      let codeText = code.trim();

      // Format code into multiline statements
      let formattedCode = codeText
        .replace(/\s*Integer\s+/gi, '\nInteger ')
        .replace(/\s*Set\s+/gi, '\nSet ')
        .replace(/\s*Print\s+/gi, '\nPrint ')
        .replace(/\s*Begin\b/gi, 'Begin\n')
        .replace(/\s*End\b/gi, '\nEnd')
        .replace(/\s*def\s+/gi, '\ndef ')
        .replace(/\s*return\s+/gi, '\n  return ')
        .replace(/\s*print\s*\(/gi, '\nprint(')
        .replace(/;\s*/g, ';\n')
        .replace(/\{\s*/g, '{\n')
        .replace(/\}\s*/g, '\n}\n')
        .split('\n')
        .map(l => l.trim())
        .filter(l => l.length > 0)
        .join('\n  ');

      const escCode = formattedCode
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");

      return `<div style="margin:16px 0;border:1px solid rgba(99,102,241,0.4);border-radius:8px;overflow:hidden"><div style="background:#1e293b;padding:6px 14px;font-size:11px;font-weight:700;color:#a5b4fc;text-transform:uppercase;letter-spacing:1px;border-bottom:1px solid rgba(99,102,241,0.3)">💻 CODE SNIPPET</div><pre style="background:#0f172a;padding:14px 18px;margin:0;font-family:'Fira Code',monospace;font-size:14px;color:#e2e8f0;line-height:1.6;overflow-x:auto"><code>${escCode}</code></pre></div>`;
    });
  }

  // Fallback for code without backticks
  if (!html.includes('CODE SNIPPET') && /(def func|int main|public class|Begin|Set A =)/i.test(html)) {
    html = html.replace(/(def func[\s\S]*|int main\s*\([^)]*\)[\s\S]*\}|public class[\s\S]*\}|Begin[\s\S]*End)/i, (codeMatch) => {
      let formattedCode = codeMatch
        .replace(/\s*Integer\s+/gi, '\nInteger ')
        .replace(/\s*Set\s+/gi, '\nSet ')
        .replace(/\s*Print\s+/gi, '\nPrint ')
        .replace(/\s*Begin\b/gi, 'Begin\n')
        .replace(/\s*End\b/gi, '\nEnd')
        .replace(/\s*def\s+/gi, '\ndef ')
        .replace(/\s*return\s+/gi, '\n  return ')
        .replace(/\s*print\s*\(/gi, '\nprint(')
        .replace(/;\s*/g, ';\n')
        .replace(/\{\s*/g, '{\n')
        .replace(/\}\s*/g, '\n}\n')
        .split('\n')
        .map(l => l.trim())
        .filter(l => l.length > 0)
        .join('\n  ');

      const escCode = formattedCode
        .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

      return `<div style="margin:16px 0;border:1px solid rgba(99,102,241,0.4);border-radius:8px;overflow:hidden"><div style="background:#1e293b;padding:6px 14px;font-size:11px;font-weight:700;color:#a5b4fc;text-transform:uppercase;letter-spacing:1px;border-bottom:1px solid rgba(99,102,241,0.3)">💻 CODE SNIPPET</div><pre style="background:#0f172a;padding:14px 18px;margin:0;font-family:'Fira Code',monospace;font-size:14px;color:#e2e8f0;line-height:1.6;overflow-x:auto"><code>${escCode}</code></pre></div>`;
    });
  }

  // Strip out any unhandled triple backticks or weird ``` text remnants
  html = html
    .replace(/```[a-z]*/gi, "")
    .replace(/```/g, "")
    .replace(/### Question/gi, '<div style="font-weight:700;color:var(--exam-accent);margin-top:10px">Problem:</div>')
    .replace(/\*\*(.*?)\*\*/g, '<strong style="color:#fff">$1</strong>')
    .replace(/\n\n/g, '<br/>');

  return html;
}

function renderCurrentMcq() {
  if (!examData.mcqs.length) return;
  const q = examData.mcqs[userState.currentMcqIdx];

  document.getElementById("mcq-num-display").textContent = `Question ${userState.currentMcqIdx + 1} of ${examData.mcqs.length}`;
  document.getElementById("mcq-diff-display").textContent = q.difficulty || "Medium";
  
  const titleElem = document.getElementById("mcq-title-display");
  const rawText = `**${q.title}**\n\n${q.description}`;
  const formattedText = formatMcqCodeBlocks(rawText);
  titleElem.innerHTML = parseMarkdownToHtml(formattedText);

  const wrapper = document.getElementById("mcq-options-wrapper");
  wrapper.innerHTML = "";

  const savedAns = userState.mcqAnswers[q.id];
  const selectedOpt = (typeof savedAns === "object") ? savedAns.selected : savedAns;
  const correctIdx = (q.active_correct_index !== undefined) ? q.active_correct_index : (q.correct_option || 0);

  (q.options || []).forEach((optText, idx) => {
    const label = document.createElement("label");
    let choiceClass = "";

    if (isReviewMode) {
      if (idx === correctIdx) {
        choiceClass = "correct-choice";
      } else if (selectedOpt === idx && selectedOpt !== correctIdx) {
        choiceClass = "wrong-choice";
      }
    } else if (selectedOpt === idx) {
      choiceClass = "selected";
    }

    label.className = `mcq-option-label ${choiceClass}`;
    
    const radio = document.createElement("input");
    radio.type = "radio";
    radio.name = `opt_${q.id}`;
    radio.className = "mcq-option-radio";
    radio.checked = selectedOpt === idx;
    radio.disabled = isReviewMode;

    if (!isReviewMode) {
      radio.addEventListener("change", () => {
        userState.mcqAnswers[q.id] = {
          selected: idx,
          correct_idx: correctIdx
        };
        renderCurrentMcq();
        renderMcqPalette();
      });
    }

    const span = document.createElement("span");
    span.textContent = optText;

    if (isReviewMode) {
      if (idx === correctIdx) {
        span.innerHTML = `${optText} <strong style="color:var(--exam-green);margin-left:8px">✓ (Correct Answer)</strong>`;
      } else if (selectedOpt === idx) {
        span.innerHTML = `${optText} <strong style="color:#ef4444;margin-left:8px">✗ (Your Answer - Wrong)</strong>`;
      }
    }

    label.appendChild(radio);
    label.appendChild(span);
    wrapper.appendChild(label);
  });

  // Explanation box during review
  const expBox = document.getElementById("mcq-explanation-box");
  const expText = document.getElementById("mcq-explanation-text");

  if (isReviewMode && expBox && expText) {
    expBox.style.display = "block";
    const detail = (examResultDetails?.mcq_details || []).find(d => d.id === q.id);
    expText.textContent = detail?.explanation || q.description || "The correct choice is indicated above.";
  } else if (expBox) {
    expBox.style.display = "none";
  }
}

function renderCurrentCoding() {
  if (!examData.coding.length) return;
  const q = examData.coding[userState.currentCodingIdx];

  document.getElementById("coding-num-display").textContent = `Coding Question ${userState.currentCodingIdx + 1} of ${examData.coding.length}`;
  document.getElementById("coding-diff-display").textContent = q.difficulty || "Easy";
  document.getElementById("coding-title-display").textContent = q.title;
  document.getElementById("coding-desc-display").textContent = q.description;
  document.getElementById("coding-input-fmt").textContent = q.input_format || "Standard input";

  const editor = document.getElementById("coding-editor-input");
  editor.value = userState.codingSolutions[q.id] || "";
  if (isReviewMode) editor.readOnly = true;
}

function saveCodingCurrentSolution() {
  if (isReviewMode || !examData.coding.length) return;
  const q = examData.coding[userState.currentCodingIdx];
  const code = document.getElementById("coding-editor-input").value;
  if (code.trim()) {
    userState.codingSolutions[q.id] = code;
  }
}

function renderMcqPalette() {
  const grid = document.getElementById("mcq-palette-grid");
  grid.innerHTML = "";

  examData.mcqs.forEach((q, idx) => {
    const btn = document.createElement("button");
    btn.className = "palette-btn";
    btn.textContent = idx + 1;

    const savedAns = userState.mcqAnswers[q.id];
    const selectedOpt = (typeof savedAns === "object") ? savedAns.selected : savedAns;
    const isAnswered = selectedOpt !== undefined && selectedOpt !== -1;
    const isMarked = userState.mcqMarked[q.id];
    const isCurrent = userState.activeTab === "mcq" && userState.currentMcqIdx === idx;

    if (isReviewMode && examResultDetails) {
      const detail = (examResultDetails.mcq_details || []).find(d => d.id === q.id);
      if (detail) {
        if (detail.status === "correct") btn.style.background = "var(--exam-green)";
        else if (detail.status === "wrong") btn.style.background = "#ef4444";
        else btn.style.background = "var(--exam-card)";
      }
    } else {
      if (isAnswered) btn.classList.add("answered");
      if (isMarked) btn.classList.add("review");
    }

    if (isCurrent) btn.classList.add("current");

    btn.addEventListener("click", () => {
      userState.currentMcqIdx = idx;
      switchTab("mcq");
      renderMcqPalette();
    });

    grid.appendChild(btn);
  });
}

function renderCodingPalette() {
  const grid = document.getElementById("coding-palette-grid");
  grid.innerHTML = "";

  examData.coding.forEach((q, idx) => {
    const btn = document.createElement("button");
    btn.className = "palette-btn";
    btn.textContent = `C${idx + 1}`;

    const isAnswered = !!userState.codingSolutions[q.id];
    const isCurrent = userState.activeTab === "coding" && userState.currentCodingIdx === idx;

    if (isAnswered) btn.classList.add("answered");
    if (isCurrent) btn.classList.add("current");

    btn.addEventListener("click", () => {
      saveCodingCurrentSolution();
      userState.currentCodingIdx = idx;
      switchTab("coding");
      renderCodingPalette();
    });

    grid.appendChild(btn);
  });
}

function startTimer() {
  const display = document.getElementById("timer-display");
  
  userState.timerInterval = setInterval(() => {
    if (isReviewMode) {
      display.textContent = "REVIEW MODE";
      clearInterval(userState.timerInterval);
      return;
    }
    userState.timeRemainingSeconds--;
    if (userState.timeRemainingSeconds <= 0) {
      clearInterval(userState.timerInterval);
      alert("⏳ Time's up! Submitting your Placement Exam now.");
      submitExam();
      return;
    }
    const mins = Math.floor(userState.timeRemainingSeconds / 60);
    const secs = userState.timeRemainingSeconds % 60;
    display.textContent = `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  }, 1000);
}

function setupProctoring() {
  document.addEventListener("visibilitychange", () => {
    if (document.hidden && !isReviewMode) {
      console.warn("⚠️ Tab switch detected during placement exam.");
    }
  });
}

async function submitExam() {
  saveCodingCurrentSolution();
  clearInterval(userState.timerInterval);

  let userEmail = "Guest";
  try {
    const stored = localStorage.getItem("codearena_user");
    if (stored) {
      const u = JSON.parse(stored);
      if (u.email) userEmail = u.email;
    }
  } catch(e){}

  const payload = {
    user_email: userEmail,
    mcq_answers: userState.mcqAnswers,
    coding_submissions: userState.codingSolutions
  };

  try {
    const res = await fetch(`${API_BASE}/questions/placement/submit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const result = await res.json();
    examResultDetails = result;
    showResultModal(result);
  } catch (e) {
    console.error("Submission error:", e);
    // Fallback scoring logic: +3 for correct, -1 for wrong, 0 for unattempted
    let correct = 0;
    let wrong = 0;
    let unattempted = 0;
    let score = 0;

    examData.mcqs.forEach(q => {
      const ansInfo = userState.mcqAnswers[q.id];
      const selected = (typeof ansInfo === "object") ? ansInfo.selected : ansInfo;
      const correctIdx = (q.active_correct_index !== undefined) ? q.active_correct_index : (q.correct_option || 0);

      if (selected === undefined || selected === -1) {
        unattempted++;
      } else if (selected === correctIdx) {
        correct++;
        score += 3;
      } else {
        wrong++;
        score -= 1;
      }
    });

    examResultDetails = {
      score,
      max_possible_score: examData.mcqs.length * 3,
      mcq_correct: correct,
      mcq_wrong: wrong,
      mcq_unattempted: unattempted,
      mcq_total: examData.mcqs.length,
      mcq_details: examData.mcqs.map(q => ({
        id: q.id,
        explanation: q.description
      })),
      coding_submitted: Object.keys(userState.codingSolutions).length
    };

    showResultModal(examResultDetails);
  }
}

function showResultModal(res) {
  document.getElementById("result-modal").style.display = "flex";
  
  const score = res.score ?? 0;
  const maxScore = res.max_possible_score ?? (res.mcq_total * 3);
  const rank = res.rank ?? 1;

  // Persist student progress to localStorage for front page display
  localStorage.setItem("codearena_last_score", score);
  localStorage.setItem("codearena_last_rank", rank);
  let prevAttempts = parseInt(localStorage.getItem("codearena_test_attempts") || "0", 10);
  localStorage.setItem("codearena_test_attempts", prevAttempts + 1);

  document.getElementById("score-percentage-circle").innerHTML = `${score}<span>Points</span>`;
  document.getElementById("res-total-marks").textContent = `${score} / ${maxScore} Points (Rank #${rank})`;
  document.getElementById("res-correct-count").textContent = `${res.mcq_correct || 0} (+${(res.mcq_correct || 0) * 3} pts)`;
  document.getElementById("res-wrong-count").textContent = `${res.mcq_wrong || 0} (-${res.mcq_wrong || 0} pts)`;
  document.getElementById("res-unattempted-count").textContent = `${res.mcq_unattempted || 0} (0 pts)`;
  document.getElementById("res-coding-score").textContent = `${res.coding_submitted || 0} / ${examData.coding.length || 3}`;

  document.getElementById("btn-review-answers").onclick = () => {
    document.getElementById("result-modal").style.display = "none";
    enterReviewMode();
  };
}

function enterReviewMode() {
  isReviewMode = true;
  document.getElementById("timer-display").textContent = "REVIEW MODE";
  
  // Disable exam action buttons
  document.getElementById("btn-mcq-clear").style.display = "none";
  document.getElementById("btn-mcq-review").style.display = "none";
  document.getElementById("btn-submit-exam").style.display = "none";

  renderCurrentMcq();
  renderMcqPalette();
  renderCodingPalette();
}
