"""
questions.py — MongoDB Atlas–backed question store
Replaces the old questions.json file-based storage.
"""

import os
import uuid
from datetime import datetime, timezone

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

MONGODB_URI = os.getenv("MONGODB_URI", "")
DB_NAME     = os.getenv("MONGODB_DB", "codearena")

_client = None
_col    = None


def _get_col():
    global _client, _col
    if _col is not None:
        return _col
    if not MONGODB_URI:
        raise RuntimeError(
            "MONGODB_URI is not set. Add it to your .env file.\n"
            "Get it from: https://cloud.mongodb.com → Connect → Drivers → Python"
        )
    _client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    _client.admin.command("ping")          # fail fast if unreachable
    db   = _client[DB_NAME]
    _col = db["questions"]
    _seed_if_empty(_col)
    return _col


# ── Seed existing questions on first run ────────────────────

SEED_QUESTIONS = [
    {
        "id": "q1",
        "title": "Two Sum",
        "description": (
            "Given an array of integers `nums` and an integer `target`, "
            "return the indices of the two numbers such that they add up to `target`.\n\n"
            "You may assume that each input would have exactly one solution, "
            "and you may not use the same element twice.\n\n"
            "Return the answer in ascending order."
        ),
        "input_format": "Line 1: Space-separated integers (the array)\nLine 2: The target integer",
        "output_format": "Two space-separated indices (ascending order)",
        "examples": [
            {"input": "2 7 11 15\n9", "output": "0 1"},
            {"input": "3 2 4\n6",     "output": "1 2"},
        ],
        "test_cases": [
            {"input": "2 7 11 15\n9", "expected": "0 1"},
            {"input": "3 2 4\n6",     "expected": "1 2"},
            {"input": "3 3\n6",       "expected": "0 1"},
        ],
        "difficulty": "Easy",
        "time_limit": 1800,
        "created_at": "2026-08-10T11:00:00Z",
    },
    {
        "id": "q2",
        "title": "Reverse String",
        "description": (
            "Write a program that reads a string and prints it reversed.\n\n"
            "Do not use any built-in reverse functions."
        ),
        "input_format": "A single line containing a string (no spaces)",
        "output_format": "The reversed string on a single line",
        "examples": [
            {"input": "hello", "output": "olleh"},
            {"input": "world", "output": "dlrow"},
        ],
        "test_cases": [
            {"input": "hello",  "expected": "olleh"},
            {"input": "world",  "expected": "dlrow"},
            {"input": "abcdef", "expected": "fedcba"},
        ],
        "difficulty": "Easy",
        "time_limit": 1200,
        "created_at": "2026-08-10T11:00:00Z",
    },
    {
        "id": "q3",
        "title": "Fibonacci Sequence",
        "description": (
            "Given a number N, print the first N terms of the Fibonacci sequence.\n\n"
            "The sequence starts with 0 and 1. Each subsequent term is the sum "
            "of the two preceding ones.\n\n"
            "Print all terms space-separated on a single line."
        ),
        "input_format": "A single integer N (1 ≤ N ≤ 20)",
        "output_format": "N space-separated Fibonacci numbers",
        "examples": [
            {"input": "5", "output": "0 1 1 2 3"},
            {"input": "1", "output": "0"},
        ],
        "test_cases": [
            {"input": "5", "expected": "0 1 1 2 3"},
            {"input": "1", "expected": "0"},
            {"input": "7", "expected": "0 1 1 2 3 5 8"},
        ],
        "difficulty": "Medium",
        "time_limit": 1500,
        "created_at": "2026-08-10T11:00:00Z",
    },
]


def _seed_if_empty(col):
    if col.count_documents({}) == 0:
        col.insert_many(SEED_QUESTIONS)
        print(f"[questions] Seeded {len(SEED_QUESTIONS)} questions into MongoDB.")


# ── Public API ──────────────────────────────────────────────

def _strip(doc: dict) -> dict:
    """Remove MongoDB _id from a document."""
    doc.pop("_id", None)
    return doc


def get_all() -> list[dict]:
    """Return all questions (without test case expected outputs or MCQ correct options for security)."""
    col = _get_col()
    result = []
    for q in col.find({}, {"_id": 0}):
        safe = {k: v for k, v in q.items() if k not in ("test_cases", "correct_option")}
        safe["test_case_count"] = len(q.get("test_cases", []))
        result.append(safe)
    return result


def get_by_id(qid: str) -> dict | None:
    """Return a single question including test cases."""
    col = _get_col()
    doc = col.find_one({"id": qid}, {"_id": 0})
    return doc


def add(data: dict) -> dict:
    """Add a new question (Coding or MCQ) and persist to MongoDB."""
    col = _get_col()
    q_type = data.get("type", "coding")

    question = {
        "id":            str(uuid.uuid4())[:8],
        "type":          q_type,
        "title":         data["title"],
        "description":   data["description"],
        "difficulty":    data.get("difficulty", "Medium"),
        "time_limit":    int(data.get("time_limit", 1800)),
        "created_at":    datetime.now(timezone.utc).isoformat(),
    }

    if q_type == "mcq":
        question["options"] = data.get("options", [])
        question["correct_option"] = int(data.get("correct_option", 0))
    else:
        question["input_format"]  = data.get("input_format", "")
        question["output_format"] = data.get("output_format", "")
        question["examples"]      = data.get("examples", [])
        question["test_cases"]    = data.get("test_cases", [])

    col.insert_one(question)
    question.pop("_id", None)
    return question


def delete(qid: str) -> bool:
    """Remove a question by ID."""
    col = _get_col()
    result = col.delete_one({"id": qid})
    return result.deleted_count > 0
