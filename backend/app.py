"""
app.py — Flask backend for the Mini Coding Platform
"""

import os
from datetime import datetime, timezone
from flask import Flask, request, jsonify, abort
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

import questions as qs
from judge0 import submit_code
from drive import create_submission_doc

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-me")
CORS(app, origins="*")  # Restrict in production

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")


# ─────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────

def _normalise(text: str) -> str:
    """Strip whitespace from each line and trailing newlines for fair comparison."""
    return "\n".join(line.rstrip() for line in text.strip().splitlines())


def _check_admin(req) -> bool:
    password = req.headers.get("X-Admin-Password") or (req.json or {}).get("admin_password", "")
    return password == ADMIN_PASSWORD


# ─────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────

@app.get("/")
def index():
    return jsonify({"status": "ok", "service": "Mini Coding Platform API"})


# ── Questions ──────────────────────────────────

@app.get("/questions")
def get_questions():
    """Return all questions (no test case answers)."""
    return jsonify(qs.get_all())


@app.get("/questions/<qid>")
def get_question(qid):
    """Return a single question (no test case answers)."""
    q = qs.get_by_id(qid)
    if q is None:
        return jsonify({"error": "Question not found"}), 404
    # Strip expected from test cases before sending to client
    safe = {k: v for k, v in q.items() if k != "test_cases"}
    safe["test_case_count"] = len(q.get("test_cases", []))
    safe["examples"] = q.get("examples", [])
    return jsonify(safe)


@app.post("/questions")
def add_question():
    """Admin: add a new question (Coding or MCQ)."""
    if not _check_admin(request):
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    q_type = data.get("type", "coding")

    required = ["title", "description"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400

    if q_type == "mcq":
        options = data.get("options", [])
        if not isinstance(options, list) or len(options) < 2:
            return jsonify({"error": "At least two options are required for an MCQ question"}), 400
        correct = data.get("correct_option")
        if correct is None or not (0 <= int(correct) < len(options)):
            return jsonify({"error": "Valid correct option index required"}), 400
    else:
        if not isinstance(data.get("test_cases"), list) or len(data.get("test_cases", [])) == 0:
            return jsonify({"error": "At least one test case required for coding questions"}), 400
        for i, tc in enumerate(data["test_cases"]):
            if "input" not in tc or "expected" not in tc:
                return jsonify({"error": f"Test case {i+1} missing 'input' or 'expected'"}), 400

    q = qs.add(data)
    return jsonify(q), 201


@app.post("/questions/<qid>/verify-mcq")
def verify_mcq(qid):
    """Verify an MCQ answer."""
    q = qs.get_by_id(qid)
    if not q or q.get("type") != "mcq":
        return jsonify({"error": "MCQ question not found"}), 404
    data = request.get_json(silent=True) or {}
    selected = data.get("selected_option")
    if selected is None:
        return jsonify({"error": "No option selected"}), 400
    
    correct = q.get("correct_option", 0)
    is_correct = int(selected) == int(correct)
    return jsonify({
        "correct": is_correct,
        "correct_option": correct
    })


@app.delete("/questions/<qid>")
def delete_question(qid):
    """Admin: delete a question."""
    if not _check_admin(request):
        return jsonify({"error": "Unauthorized"}), 401

    if qs.delete(qid):
        return jsonify({"message": "Deleted"}), 200
    return jsonify({"error": "Question not found"}), 404


# ── Code Execution ─────────────────────────────

@app.post("/run")
def run_code():
    """
    Run code against a user-supplied stdin.
    Body: { code, language, input }
    """
    data = request.get_json(silent=True) or {}
    code     = (data.get("code") or "").strip()
    language = (data.get("language") or "python").strip().lower()
    stdin    = data.get("input", "")

    if not code:
        return jsonify({"error": "No code provided"}), 400

    result = submit_code(code, language, stdin)
    return jsonify(result)


# ── Submit ─────────────────────────────────────

@app.post("/submit")
def submit():
    """
    Run code against all test cases. If all pass, create a Google Doc.
    Body: { username, question_id, code, language }
    """
    data        = request.get_json(silent=True) or {}
    username    = (data.get("username") or "anonymous").strip()
    question_id = data.get("question_id", "")
    code        = (data.get("code") or "").strip()
    language    = (data.get("language") or "python").strip().lower()

    if not code:
        return jsonify({"error": "No code provided"}), 400

    q = qs.get_by_id(question_id)
    if q is None:
        return jsonify({"error": "Question not found"}), 404

    test_cases = q.get("test_cases", [])
    if not test_cases:
        return jsonify({"error": "No test cases defined for this question"}), 400

    # Run all test cases
    test_results = []
    all_passed   = True

    for tc in test_cases:
        result = submit_code(code, language, tc["input"])

        if "error" in result:
            return jsonify({"error": result["error"]}), 502

        got      = _normalise(result.get("stdout", ""))
        expected = _normalise(tc["expected"])
        passed   = got == expected

        if not passed:
            all_passed = False

        test_results.append({
            "input":    tc["input"],
            "expected": expected,
            "got":      got,
            "passed":   passed,
            "stderr":   result.get("stderr", ""),
            "status":   result.get("status", ""),
            "time":     result.get("time"),
        })

    if not all_passed:
        return jsonify({
            "status":       "Wrong Answer",
            "all_passed":   False,
            "test_results": test_results,
        }), 200

    # All passed — create Google Doc
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    doc_result = create_submission_doc(
        username       = username,
        question_title = q["title"],
        language       = language,
        code           = code,
        test_results   = test_results,
        overall_status = "Correct ✅",
        timestamp      = timestamp,
    )

    response = {
        "status":       "Accepted",
        "all_passed":   True,
        "test_results": test_results,
        "timestamp":    timestamp,
    }

    if "error" in doc_result:
        # Submission is still correct — just warn about Drive
        response["drive_warning"] = doc_result["error"]
    else:
        response["doc_url"]       = doc_result.get("url")
        response["doc_file_name"] = doc_result.get("file_name")

    return jsonify(response), 200


# ─────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_ENV", "development") == "development"
    print(f"Starting Mini Coding Platform API on http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=debug)
