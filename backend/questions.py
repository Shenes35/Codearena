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
        "is_placement":  bool(data.get("is_placement", True)),
        "created_at":    datetime.now(timezone.utc).isoformat(),
    }

    if q_type == "mcq":
        question["options"] = data.get("options", [])
        question["correct_option"] = int(data.get("correct_option", 0))
        if "variation_sets" in data:
            question["variation_sets"] = data["variation_sets"]
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


def get_placement_exam() -> dict:
    """
    Get 30 MCQs and 3 Coding questions for placement exam.
    If database does not have 30 MCQs or 3 coding questions, auto-generate standard placement questions.
    """
    import random

    col = _get_col()
    
    # Fetch MCQs
    mcqs = list(col.find({"type": "mcq"}, {"_id": 0}))
    if len(mcqs) < 30:
        # Seed standard placement MCQs to reach 30 if needed
        needed = 30 - len(mcqs)
        _seed_placement_mcqs(needed)
        mcqs = list(col.find({"type": "mcq"}, {"_id": 0}))

    # Fetch Coding questions
    coding = list(col.find({"type": {"$ne": "mcq"}}, {"_id": 0}))
    if len(coding) < 3:
        needed = 3 - len(coding)
        _seed_placement_coding(needed)
        coding = list(col.find({"type": {"$ne": "mcq"}}, {"_id": 0}))

    selected_mcqs = mcqs[:30]
    selected_coding = coding[:3]

    # Prepare client-safe payload
    safe_mcqs = []
    for m in selected_mcqs:
        item = {k: v for k, v in m.items() if k not in ("correct_option", "variation_sets")}
        
        # If question has admin-provided variation sets with {} placeholders
        var_sets = m.get("variation_sets", [])
        if var_sets:
            # Pick one variation set randomly
            chosen_set = random.choice(var_sets)
            replacements = chosen_set.get("replacements", [])
            desc = m.get("description", "")

            # Substitute each {} with corresponding replacement value
            for val in replacements:
                desc = desc.replace("{}", str(val), 1)
            item["description"] = desc

            # Construct 4 options (1 correct answer + 3 wrong distractors)
            correct_ans = chosen_set.get("correct_answer", "")
            distractors = chosen_set.get("distractors", [])
            all_choices = [correct_ans] + distractors
            random.shuffle(all_choices)

            item["options"] = all_choices
            item["active_correct_index"] = all_choices.index(correct_ans)

        safe_mcqs.append(item)

    safe_coding = []
    for c in selected_coding:
        item = {k: v for k, v in c.items() if k != "test_cases"}
        item["test_case_count"] = len(c.get("test_cases", []))
        item["examples"] = c.get("examples", [])
        safe_coding.append(item)

    return {
        "mcq_questions": safe_mcqs,
        "coding_questions": safe_coding,
        "total_mcqs": len(safe_mcqs),
        "total_coding": len(safe_coding),
        "duration_minutes": 60
    }


def evaluate_placement_exam(submission: dict) -> dict:
    """
    Evaluate candidate placement exam submission.
    Scoring system: +3 for Correct Answer, 0 for Unattempted, -1 for Wrong Answer.
    """
    col = _get_col()
    mcq_answers = submission.get("mcq_answers", {})
    coding_submissions = submission.get("coding_submissions", {})

    # Evaluate MCQs
    mcq_correct_count = 0
    mcq_wrong_count = 0
    mcq_unattempted_count = 0
    total_score = 0
    mcq_results = []
    
    all_mcqs = {m["id"]: m for m in col.find({"type": "mcq"}, {"_id": 0})}

    for qid, q_data in all_mcqs.items():
        explanation = q_data.get("explanation") or q_data.get("description", "")
        
        if qid in mcq_answers:
            ans_info = mcq_answers[qid]
            if isinstance(ans_info, dict):
                user_ans = int(ans_info.get("selected", -1))
                correct_ans = int(ans_info.get("correct_idx", 0))
            else:
                user_ans = int(ans_info)
                correct_ans = int(q_data.get("correct_option", 0))

            if user_ans == -1:
                # Unattempted
                mcq_unattempted_count += 1
                score_change = 0
                status = "unattempted"
            elif user_ans == correct_ans:
                # Correct
                mcq_correct_count += 1
                score_change = 3
                status = "correct"
            else:
                # Wrong
                mcq_wrong_count += 1
                score_change = -1
                status = "wrong"

            total_score += score_change
            mcq_results.append({
                "id": qid,
                "title": q_data.get("title"),
                "user_answer": user_ans,
                "correct_answer": correct_ans,
                "status": status,
                "score_change": score_change,
                "explanation": explanation
            })

    total_mcqs = len(mcq_results) if len(mcq_results) > 0 else 30
    max_possible_score = total_mcqs * 3

    return {
        "score": total_score,
        "max_possible_score": max_possible_score,
        "mcq_correct": mcq_correct_count,
        "mcq_wrong": mcq_wrong_count,
        "mcq_unattempted": mcq_unattempted_count,
        "mcq_total": total_mcqs,
        "mcq_details": mcq_results,
        "coding_submitted": len(coding_submissions)
    }


def _seed_placement_mcqs(count: int):
    """Seed benchmark placement MCQs with user-provided 2025 Quantitative, Logical, and Verbal questions."""
    col = _get_col()
    
    # 30 MCQ Questions set exactly as requested
    user_mcqs = [
        # Quantitative Aptitude (18 questions)
        {
            "title": "Percentage Problem (2025)",
            "desc": "The price of a product increased by 20%. By what percentage should consumption be reduced to keep expenditure same?",
            "opts": ["16.67%", "20%", "15%", "18.5%"],
            "correct": 0
        },
        {
            "title": "Mixture Problem (2025)",
            "desc": "A mixture contains milk and water in ratio 3:2. If 10 liters of water is added, ratio becomes 2:3. Find initial quantity of mixture.",
            "opts": ["15 liters", "20 liters", "25 liters", "30 liters"],
            "correct": 1
        },
        {
            "title": "Profit & Loss - Successive Discounts (2025)",
            "desc": "A shopkeeper gives two successive discounts of 10% and 20% on an item. What is the effective discount percentage?",
            "opts": ["30%", "25%", "28%", "22%"],
            "correct": 2
        },
        {
            "title": "Time & Work - Efficiency (2025)",
            "desc": "A is twice as efficient as B. Together they complete a work in 12 days. In how many days will A alone complete it?",
            "opts": ["24 days", "18 days", "16 days", "36 days"],
            "correct": 1
        },
        {
            "title": "Simple Interest - Rate Calculation (2025)",
            "desc": "A sum of ₹8,000 amounts to ₹9,600 in 4 years at simple interest. Find the rate of interest per annum.",
            "opts": ["4%", "5%", "6%", "7.5%"],
            "correct": 1
        },
        {
            "title": "Compound Interest - Half Yearly (2025)",
            "desc": "Find compound interest on ₹5,000 for 1 year at 10% per annum, compounded half-yearly.",
            "opts": ["₹500", "₹525", "₹512.50", "₹550"],
            "correct": 2
        },
        {
            "title": "Speed & Distance - Relative Speed (2025)",
            "desc": "Two trains of lengths 100m and 150m are running in the same direction at speeds of 50 km/hr and 40 km/hr respectively. Find time taken by faster train to overtake slower train.",
            "opts": ["60 seconds", "90 seconds", "75 seconds", "120 seconds"],
            "correct": 1
        },
        {
            "title": "Speed & Distance - Average Speed (2025)",
            "desc": "A person travels first half of distance at 40 km/hr and second half at 60 km/hr. Find average speed.",
            "opts": ["50 km/hr", "48 km/hr", "52 km/hr", "45 km/hr"],
            "correct": 1
        },
        {
            "title": "Permutations - Arrangements (2025)",
            "desc": "In how many ways can 5 people be arranged in a row if two particular people must sit together?",
            "opts": ["120 ways", "24 ways", "48 ways", "60 ways"],
            "correct": 2
        },
        {
            "title": "Combinations - Selection (2025)",
            "desc": "In how many ways can 3 students be selected from a group of 8 students?",
            "opts": ["56 ways", "336 ways", "24 ways", "112 ways"],
            "correct": 0
        },
        {
            "title": "Pipes & Cisterns - Multiple Pipes (2025)",
            "desc": "Three pipes A, B, C can fill a tank in 12, 15, and 20 hours respectively. If all three are opened together, how long will it take to fill the tank?",
            "opts": ["4 hours", "5 hours", "6 hours", "8 hours"],
            "correct": 1
        },
        {
            "title": "Probability - Cards (2025)",
            "desc": "Two cards are drawn from a pack of 52 cards. What is the probability that both are aces?",
            "opts": ["1/221", "1/169", "1/13", "4/663"],
            "correct": 0
        },
        {
            "title": "Ratio & Proportion - Three Quantities (2025)",
            "desc": "If A:B = 2:3 and B:C = 4:5, find A:B:C.",
            "opts": ["2:3:5", "8:12:15", "6:12:15", "8:10:15"],
            "correct": 1
        },
        {
            "title": "Percentage - Successive Changes (2025)",
            "desc": "A number is first increased by 25% and then decreased by 20%. Find the net percentage change.",
            "opts": ["5% increase", "5% decrease", "0% (no change)", "10% increase"],
            "correct": 2
        },
        {
            "title": "Data Interpretation (2025)",
            "desc": "Product B sold 40,000 units. Product A sold 25% more than Product B. Find Product A's sales.",
            "opts": ["45,000 units", "50,000 units", "55,000 units", "60,000 units"],
            "correct": 1
        },
        {
            "title": "Ages Problem - Sum of Ages (2025)",
            "desc": "The sum of the ages of A and B is 60 years, and A is twice as old as B. What are their ages?",
            "opts": ["A: 30, B: 30", "A: 40, B: 20", "A: 45, B: 15", "A: 36, B: 24"],
            "correct": 1
        },
        {
            "title": "Number Series - Consecutive Even Differences (2025)",
            "desc": "Which of the following is the next term in the series: 2, 6, 12, 20, 30, ?",
            "opts": ["36", "40", "42", "48"],
            "correct": 2
        },
        {
            "title": "Vocabulary - Ephemeral Synonym (2025)",
            "desc": "Choose the correct synonym for 'Ephemeral':",
            "opts": ["a) Eternal", "b) Temporary", "c) Perpetual", "d) Endless"],
            "correct": 1
        },

        # Logical Reasoning (10 questions)
        {
            "title": "Number Series - Square Pattern (2025)",
            "desc": "Find next number: 1, 4, 9, 16, 25, ?",
            "opts": ["30", "36", "40", "49"],
            "correct": 1
        },
        {
            "title": "Number Series - Prime Pattern (2025)",
            "desc": "Find next number: 2, 3, 5, 7, 11, ?",
            "opts": ["12", "13", "15", "17"],
            "correct": 1
        },
        {
            "title": "Number Series - Fibonacci Variant (2025)",
            "desc": "Find next number: 1, 1, 2, 3, 5, 8, ?",
            "opts": ["11", "13", "15", "21"],
            "correct": 1
        },
        {
            "title": "Letter Series - Skip Pattern (2025)",
            "desc": "Find next letter: B, E, H, K, ?",
            "opts": ["M", "N", "O", "P"],
            "correct": 1
        },
        {
            "title": "Coding-Decoding - Reverse Pattern (2025)",
            "desc": "If 'ACCENTURE' is coded as 'ERUTNECCA', how is 'SYSTEM' coded?",
            "opts": ["METSYS", "SYSMET", "TEMSYS", "MEYSTS"],
            "correct": 0
        },
        {
            "title": "Syllogism - Three Statements (2025)",
            "desc": "Statements: 1. Some books are novels, 2. All novels are stories, 3. No story is a poem. Conclusions: I) Some books are stories, II) No novel is a poem, III) Some stories are books.",
            "opts": ["Only I follows", "Only II follows", "All I, II, and III follow", "None follows"],
            "correct": 2
        },
        {
            "title": "Blood Relations - Complex (2025)",
            "desc": "Pointing to a photograph, a man said, 'She is the daughter of my grandfather's only son.' How is the man related to the person in the photograph?",
            "opts": ["Father", "Brother", "Sister", "Cousin"],
            "correct": 2
        },
        {
            "title": "Direction Sense - Multiple Turns (2025)",
            "desc": "A person walks 10m north, then 5m east, then 10m south, then 5m west. Where is he from starting point?",
            "opts": ["10m North", "5m East", "At starting point", "10m South"],
            "correct": 2
        },
        {
            "title": "Seating Arrangement - Circular (2025)",
            "desc": "Six friends A, B, C, D, E, F sit around a circular table. A sits opposite D. B sits between A and C. E is not adjacent to A. Who sits opposite E?",
            "opts": ["A", "B", "C", "F"],
            "correct": 1
        },
        {
            "title": "Ordering & Ranking (2025)",
            "desc": "In a queue, Ravi is 15th from front and 20th from back. How many people are in the queue?",
            "opts": ["35", "34", "33", "36"],
            "correct": 1
        },

        # Verbal Ability (2 questions to complete total 30)
        {
            "title": "Reading Comprehension - Inference (2025)",
            "desc": "Passage: 'Cloud computing has transformed how businesses operate. Companies can now access computing resources on-demand without maintaining physical infrastructure. This has led to significant cost savings and increased flexibility.' What is the main advantage mentioned?",
            "opts": ["Hardware ownership", "Cost savings and increased flexibility", "Increased security risks", "Manual server setup"],
            "correct": 1
        },
        {
            "title": "Grammar - Parallelism (2025)",
            "desc": "Choose the correct sentence:",
            "opts": ["a) She likes reading, writing, and to dance", "b) She likes reading, writing, and dancing", "c) She likes to read, writing, and dancing", "d) She likes read, write, and dancing"],
            "correct": 1
        }
    ]

    items_to_add = []
    for t in user_mcqs:
        items_to_add.append({
            "id": f"pmcq_{uuid.uuid4().hex[:6]}",
            "type": "mcq",
            "title": t["title"],
            "description": t["desc"],
            "options": t["opts"],
            "correct_option": t["correct"],
            "difficulty": "Medium",
            "is_placement": True,
            "created_at": datetime.now(timezone.utc).isoformat()
        })

    if items_to_add:
        col.insert_many(items_to_add)
        print(f"[questions] Seeded {len(items_to_add)} 2025 placement MCQs into MongoDB.")


def _seed_placement_coding(count: int):
    """Seed placement coding questions if fewer than 3 exist in DB."""
    col = _get_col()
    problems = [
        {
            "title": "Palindrome Check",
            "description": "Given a string `s`, determine if it is a palindrome considering only alphanumeric characters and ignoring cases.",
            "input_format": "A single string s",
            "output_format": "Print 'true' if palindrome, else 'false'",
            "examples": [{"input": "racecar", "output": "true"}, {"input": "hello", "output": "false"}],
            "test_cases": [{"input": "racecar", "expected": "true"}, {"input": "hello", "expected": "false"}, {"input": "AmanaplanacanalPanama", "expected": "true"}],
            "difficulty": "Easy"
        },
        {
            "title": "Find Missing Number",
            "description": "Given an array containing n distinct numbers taken from 0, 1, 2, ..., n, find the single missing number in the sequence.",
            "input_format": "Space-separated integers",
            "output_format": "The missing integer",
            "examples": [{"input": "3 0 1", "output": "2"}],
            "test_cases": [{"input": "3 0 1", "expected": "2"}, {"input": "0 1 2 4 5", "expected": "3"}],
            "difficulty": "Medium"
        },
        {
            "title": "Maximum Subarray Sum",
            "description": "Given an integer array `nums`, find the contiguous subarray (containing at least one number) which has the largest sum and print its sum.",
            "input_format": "Space-separated integers",
            "output_format": "The maximum subarray sum integer",
            "examples": [{"input": "-2 1 -3 4 -1 2 1 -5 4", "output": "6"}],
            "test_cases": [{"input": "-2 1 -3 4 -1 2 1 -5 4", "expected": "6"}, {"input": "1 2 3 4", "expected": "10"}],
            "difficulty": "Hard"
        }
    ]
    items_to_add = []
    for i in range(min(count, len(problems))):
        p = problems[i]
        items_to_add.append({
            "id": f"pcoding_{uuid.uuid4().hex[:6]}",
            "type": "coding",
            "title": p["title"],
            "description": p["description"],
            "input_format": p["input_format"],
            "output_format": p["output_format"],
            "examples": p["examples"],
            "test_cases": p["test_cases"],
            "difficulty": p["difficulty"],
            "time_limit": 1800,
            "is_placement": True,
            "created_at": datetime.now(timezone.utc).isoformat()
        })
    if items_to_add:
        col.insert_many(items_to_add)

