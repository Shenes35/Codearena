"""
questions.py — In-memory question store backed by questions.json
"""

import json
import os
import uuid
from datetime import datetime, timezone

QUESTIONS_FILE = os.path.join(os.path.dirname(__file__), "questions.json")

_questions: list[dict] = []


def _load():
    global _questions
    if os.path.exists(QUESTIONS_FILE):
        with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
            _questions = json.load(f)
    else:
        _questions = []


def _save():
    with open(QUESTIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(_questions, f, indent=2, ensure_ascii=False)


def get_all() -> list[dict]:
    """Return all questions (without test case expected outputs for security)."""
    result = []
    for q in _questions:
        safe = {k: v for k, v in q.items() if k != "test_cases"}
        safe["test_case_count"] = len(q.get("test_cases", []))
        result.append(safe)
    return result


def get_by_id(qid: str) -> dict | None:
    """Return a single question including test cases."""
    for q in _questions:
        if q["id"] == qid:
            return q
    return None


def add(data: dict) -> dict:
    """Add a new question and persist to disk."""
    question = {
        "id": str(uuid.uuid4())[:8],
        "title": data["title"],
        "description": data["description"],
        "input_format": data.get("input_format", ""),
        "output_format": data.get("output_format", ""),
        "examples": data.get("examples", []),
        "test_cases": data.get("test_cases", []),
        "difficulty": data.get("difficulty", "Medium"),
        "time_limit": int(data.get("time_limit", 1800)),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _questions.append(question)
    _save()
    return question


def delete(qid: str) -> bool:
    """Remove a question by ID."""
    global _questions
    before = len(_questions)
    _questions = [q for q in _questions if q["id"] != qid]
    if len(_questions) < before:
        _save()
        return True
    return False


# Load on import
_load()
