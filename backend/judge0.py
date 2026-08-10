"""
judge0.py — Judge0 CE API wrapper

Uses the FREE public Judge0 CE server (ce.judge0.com) by default.
If JUDGE0_API_KEY is set in .env, uses RapidAPI instead.

Public server docs: https://ce.judge0.com
"""

import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

JUDGE0_KEY = os.getenv("JUDGE0_API_KEY", "").strip()

# Use RapidAPI if a key is provided, otherwise use the free public server
if JUDGE0_KEY:
    JUDGE0_URL = os.getenv("JUDGE0_API_URL", "https://judge0-ce.p.rapidapi.com")
    USE_RAPIDAPI = True
else:
    JUDGE0_URL = "https://ce.judge0.com"
    USE_RAPIDAPI = False

# Judge0 language IDs
LANGUAGE_IDS = {
    "python":     71,   # Python 3.8.1
    "javascript": 63,   # Node.js 12.14.0
    "cpp":        54,   # C++ (GCC 9.2.0)
    "java":       62,   # Java (OpenJDK 13.0.1)
    "c":          50,   # C (GCC 9.2.0)
}

# Status IDs from Judge0
STATUS_NAMES = {
    1:  "In Queue",
    2:  "Processing",
    3:  "Accepted",
    4:  "Wrong Answer",
    5:  "Time Limit Exceeded",
    6:  "Compilation Error",
    7:  "Runtime Error (SIGSEGV)",
    8:  "Runtime Error (SIGXFSZ)",
    9:  "Runtime Error (SIGFPE)",
    10: "Runtime Error (SIGABRT)",
    11: "Runtime Error (NZEC)",
    12: "Runtime Error (Other)",
    13: "Internal Error",
    14: "Exec Format Error",
}


def _headers() -> dict:
    """Return appropriate headers based on which server we're using."""
    if USE_RAPIDAPI:
        return {
            "x-rapidapi-host": "judge0-ce.p.rapidapi.com",
            "x-rapidapi-key":  JUDGE0_KEY,
            "Content-Type":    "application/json",
        }
    else:
        # Public server — no auth needed
        return {
            "Content-Type": "application/json",
        }


def submit_code(code: str, language: str, stdin: str = "") -> dict:
    """
    Submit code to Judge0 and poll until a result is ready.
    Returns a dict with keys: stdout, stderr, status, time, memory, compile_output
    """
    lang_id = LANGUAGE_IDS.get(language.lower())
    if lang_id is None:
        return {"error": f"Unsupported language: {language}"}

    payload = {
        "source_code": code,
        "language_id": lang_id,
        "stdin":        stdin,
    }

    # --- Submit ---
    try:
        resp = requests.post(
            f"{JUDGE0_URL}/submissions?base64_encoded=false&wait=false",
            json=payload,
            headers=_headers(),
            timeout=15,
        )
        resp.raise_for_status()
        token = resp.json().get("token")
        if not token:
            return {"error": "No token returned from Judge0. The public server may be busy — try again."}
    except requests.RequestException as e:
        return {"error": f"Judge0 submission failed: {str(e)}"}

    # --- Poll for result ---
    for attempt in range(20):
        time.sleep(1.5)
        try:
            result = requests.get(
                f"{JUDGE0_URL}/submissions/{token}?base64_encoded=false",
                headers=_headers(),
                timeout=10,
            )
            result.raise_for_status()
            data = result.json()
        except requests.RequestException as e:
            return {"error": f"Judge0 polling failed: {str(e)}"}

        status_id = data.get("status", {}).get("id", 0)
        if status_id >= 3:  # Finished
            return {
                "stdout":         (data.get("stdout") or "").strip(),
                "stderr":         (data.get("stderr") or "").strip(),
                "compile_output": (data.get("compile_output") or "").strip(),
                "status_id":      status_id,
                "status":         STATUS_NAMES.get(status_id, "Unknown"),
                "time":           data.get("time"),
                "memory":         data.get("memory"),
            }

    return {"error": "Execution timed out after 30 seconds"}
