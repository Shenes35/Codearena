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

let testMode = "full"; // "mcq", "coding", or "full"

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
    const res = await fetch(`${API_BASE}/questions/placement`);
    if (!res.ok) throw new Error("Failed to fetch placement exam payload");
    const data = await res.json();
    
    examData.mcqs = data.mcq_questions || [];
    examData.coding = data.coding_questions || [];
    examData.durationMinutes = data.duration_minutes || 60;

    if (testMode === "full") userState.timeRemainingSeconds = examData.durationMinutes * 60;

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

function renderCurrentMcq() {
  if (!examData.mcqs.length) return;
  const q = examData.mcqs[userState.currentMcqIdx];

  document.getElementById("mcq-num-display").textContent = `Question ${userState.currentMcqIdx + 1} of ${examData.mcqs.length}`;
  document.getElementById("mcq-diff-display").textContent = q.difficulty || "Medium";
  document.getElementById("mcq-title-display").textContent = `${q.title}: ${q.description}`;

  const wrapper = document.getElementById("mcq-options-wrapper");
  wrapper.innerHTML = "";

  const selectedOpt = userState.mcqAnswers[q.id];

  (q.options || []).forEach((optText, idx) => {
    const label = document.createElement("label");
    label.className = `mcq-option-label ${selectedOpt === idx ? "selected" : ""}`;
    
    const radio = document.createElement("input");
    radio.type = "radio";
    radio.name = `opt_${q.id}`;
    radio.className = "mcq-option-radio";
    radio.checked = selectedOpt === idx;
    radio.addEventListener("change", () => {
      userState.mcqAnswers[q.id] = idx;
      renderCurrentMcq();
      renderMcqPalette();
    });

    const span = document.createElement("span");
    span.textContent = optText;

    label.appendChild(radio);
    label.appendChild(span);
    wrapper.appendChild(label);
  });
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
}

function saveCodingCurrentSolution() {
  if (!examData.coding.length) return;
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

    const isAnswered = userState.mcqAnswers[q.id] !== undefined;
    const isMarked = userState.mcqMarked[q.id];
    const isCurrent = userState.activeTab === "mcq" && userState.currentMcqIdx === idx;

    if (isAnswered) btn.classList.add("answered");
    if (isMarked) btn.classList.add("review");
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
    if (document.hidden) {
      console.warn("⚠️ Tab switch detected during placement exam.");
    }
  });
}

async function submitExam() {
  saveCodingCurrentSolution();
  clearInterval(userState.timerInterval);

  const payload = {
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
    showResultModal(result);
  } catch (e) {
    console.error("Submission error:", e);
    showResultModal({
      mcq_correct: Object.keys(userState.mcqAnswers).length,
      mcq_total: examData.mcqs.length || 30,
      mcq_percentage: Math.round((Object.keys(userState.mcqAnswers).length / 30) * 100),
      coding_submitted: Object.keys(userState.codingSolutions).length
    });
  }
}

function showResultModal(res) {
  document.getElementById("result-modal").style.display = "flex";
  
  const scorePercent = res.mcq_percentage || 0;
  document.getElementById("score-percentage-circle").innerHTML = `${scorePercent}%<span>Score</span>`;
  document.getElementById("res-mcq-score").textContent = `${res.mcq_correct || 0} / ${res.mcq_total || 30}`;
  document.getElementById("res-coding-score").textContent = `${res.coding_submitted || 0} / ${examData.coding.length || 3}`;

  const statusElem = document.getElementById("res-status");
  if (scorePercent >= 60) {
    statusElem.textContent = "QUALIFIED ✅";
    statusElem.style.color = "#10b981";
  } else {
    statusElem.textContent = "NEEDS IMPROVEMENT";
    statusElem.style.color = "#ef4444";
  }
}
