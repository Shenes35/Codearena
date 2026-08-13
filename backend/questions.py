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
    if len(mcqs) < 70:
        # Re-seed expanded 2024 and 2025 benchmark placement & technical MCQs
        col.delete_many({"id": {"$regex": "^pmcq_"}})
        _seed_placement_mcqs(100)
        mcqs = list(col.find({"type": "mcq"}, {"_id": 0}))

    # Fetch Coding questions
    coding = list(col.find({"type": {"$ne": "mcq"}}, {"_id": 0}))
    if len(coding) < 3:
        needed = 3 - len(coding)
        _seed_placement_coding(needed)
        coding = list(col.find({"type": {"$ne": "mcq"}}, {"_id": 0}))

    # Shuffle questions each time candidate attends the test
    random.shuffle(mcqs)
    random.shuffle(coding)

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
        else:
            # Standard MCQ: Shuffle options randomly so correct answer position is unpredictable
            opts = list(m.get("options", []))
            orig_correct_idx = int(m.get("correct_option", 0))
            if opts and 0 <= orig_correct_idx < len(opts):
                correct_val = opts[orig_correct_idx]
                # Keep shuffling until correct_val is not at index 0 (if options count >= 2)
                if len(opts) > 1:
                    while opts[0] == correct_val:
                        random.shuffle(opts)
                else:
                    random.shuffle(opts)
                item["options"] = opts
                item["active_correct_index"] = opts.index(correct_val)
            else:
                item["options"] = opts
                item["active_correct_index"] = orig_correct_idx

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

    # Log submission to MongoDB Leaderboard collection
    user_email = submission.get("user_email", "Guest")
    scores_col = _get_col().database["placement_scores"]
    
    score_entry = {
        "user_email": user_email,
        "score": total_score,
        "mcq_correct": mcq_correct_count,
        "mcq_wrong": mcq_wrong_count,
        "mcq_unattempted": mcq_unattempted_count,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    scores_col.insert_one(score_entry)

    # Calculate candidate rank relative to all placement test attempts
    higher_scores = scores_col.count_documents({"score": {"$gt": total_score}})
    rank = higher_scores + 1
    total_candidates = scores_col.count_documents({})

    return {
        "score": total_score,
        "max_possible_score": max_possible_score,
        "rank": rank,
        "total_candidates": total_candidates,
        "mcq_correct": mcq_correct_count,
        "mcq_wrong": mcq_wrong_count,
        "mcq_unattempted": mcq_unattempted_count,
        "mcq_total": total_mcqs,
        "mcq_details": mcq_results,
        "coding_submitted": len(coding_submissions)
    }


def get_leaderboard() -> dict:
    """Return top leaderboard scores and recent test progress."""
    scores_col = _get_col().database["placement_scores"]
    top_scores = list(scores_col.find({}, {"_id": 0}).sort("score", -1).limit(10))
    total_attempts = scores_col.count_documents({})
    return {
        "top_leaderboard": top_scores,
        "total_attempts": total_attempts
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

        {
            "title": "Vocabulary - Synonyms: MAGNIFICENT (2025)",
            "desc": "Find the synonym of 'MAGNIFICENT':",
            "opts": ["a) Ordinary", "b) Splendid", "c) Small", "d) Ugly"],
            "correct": 1,
            "explanation": "Magnificent means impressively beautiful or grand, so 'Splendid' is the synonym."
        },
        {
            "title": "Vocabulary - Antonyms: BRILLIANT (2025)",
            "desc": "Find the antonym of 'BRILLIANT':",
            "opts": ["a) Bright", "b) Dull", "c) Shining", "d) Smart"],
            "correct": 1,
            "explanation": "Brilliant means very bright or intelligent, so 'Dull' is the antonym."
        },
        {
            "title": "Sentence Correction - Vowel Sound (2025)",
            "desc": "Choose the correct sentence:",
            "opts": ["a) He is a honest man", "b) He is an honest man", "c) He is the honest man", "d) He is honest man"],
            "correct": 1,
            "explanation": "'Honest' starts with a silent 'h' and a vowel sound, so 'an' is used."
        },

        # 2024 Quantitative Aptitude Questions
        {
            "title": "Profit & Loss - Markup & Discount (2024)",
            "desc": "A shopkeeper marks an item 30% above cost price and gives 10% discount. Find his profit percentage.",
            "opts": ["15%", "17%", "20%", "23%"],
            "correct": 1,
            "explanation": "Let CP = ₹100. MP = ₹130. SP = ₹130 - 10% of 130 = ₹117. Profit % = 17%."
        },
        {
            "title": "Time & Work - Partial Work (2024)",
            "desc": "A and B can complete a work in 20 days and 30 days respectively. They work together for 6 days, then A leaves. In how many days will B complete the remaining work?",
            "opts": ["10 days", "12 days", "15 days", "18 days"],
            "correct": 2,
            "explanation": "A + B 1-day work = 1/20 + 1/30 = 1/12. In 6 days = 1/2. Remaining 1/2 work done by B in 15 days."
        },
        {
            "title": "Percentage Calculation (2024)",
            "desc": "If 20% of a number is 60, what is 35% of that number?",
            "opts": ["90", "105", "120", "140"],
            "correct": 1,
            "explanation": "Number = 60 × 100/20 = 300. 35% of 300 = 105."
        },
        {
            "title": "Ratio & Proportion - Age Ratio (2024)",
            "desc": "The ratio of ages of A and B is 3:5. After 10 years, the ratio becomes 5:7. Find the present age of A.",
            "opts": ["12 years", "15 years", "18 years", "25 years"],
            "correct": 1,
            "explanation": "(3x+10)/(5x+10) = 5/7 => x = 5. A's age = 3 × 5 = 15 years."
        },
        {
            "title": "Simple Interest - Two Amounts (2024)",
            "desc": "A sum of money becomes ₹2,400 in 2 years and ₹3,200 in 4 years at simple interest. Find the principal amount.",
            "opts": ["₹1,200", "₹1,600", "₹1,800", "₹2,000"],
            "correct": 1,
            "explanation": "Interest for 2 yrs = 3200 - 2400 = ₹800. Principal = 2400 - 800 = ₹1,600."
        },
        {
            "title": "Compound Interest - Annual (2024)",
            "desc": "Find compound interest on ₹10,000 for 2 years at 10% per annum, compounded annually.",
            "opts": ["₹2,000", "₹2,100", "₹2,200", "₹2,400"],
            "correct": 1,
            "explanation": "Amount = 10000 × (1.1)^2 = ₹12,100. CI = 12100 - 10000 = ₹2,100."
        },
        {
            "title": "Speed & Distance - Platform Crossing (2024)",
            "desc": "A train 150 meters long passes a platform 200 meters long in 20 seconds. Find the speed of the train in km/hr.",
            "opts": ["54 km/hr", "63 km/hr", "72 km/hr", "80 km/hr"],
            "correct": 1,
            "explanation": "Total distance = 350m. Speed = 350/20 = 17.5 m/s = 17.5 × 18/5 = 63 km/hr."
        },
        {
            "title": "Pipes & Cisterns - Filling & Emptying (2024)",
            "desc": "Pipe A fills a tank in 10 hours and Pipe B empties it in 15 hours. How many hours will it take to fill a half empty tank?",
            "opts": ["10 hours", "12 hours", "15 hours", "30 hours"],
            "correct": 2,
            "explanation": "Net rate = 1/10 - 1/15 = 1/30. Time for half tank = (1/2) / (1/30) = 15 hours."
        },
        {
            "title": "Permutations - Code Words (2024)",
            "desc": "A code word consists of two English alphabets followed by two distinct numbers between 1 and 9 (e.g. CA23). How many such code words are there?",
            "opts": ["48,672", "52,480", "42,120", "65,536"],
            "correct": 0,
            "explanation": "Alphabets = 26 × 26 = 676. Numbers = 9 × 8 = 72. Total = 676 × 72 = 48,672."
        },
        {
            "title": "Probability - Two Dice (2024)",
            "desc": "Two dice are thrown. What is the probability of getting a sum of 7?",
            "opts": ["1/6", "1/12", "5/36", "1/4"],
            "correct": 0,
            "explanation": "Favorable outcomes = 6 ((1,6),(2,5),(3,4),(4,3),(5,2),(6,1)). Total = 36. Prob = 6/36 = 1/6."
        },
        {
            "title": "Mixtures & Alligations - Ratio (2024)",
            "desc": "In what ratio should water be mixed with milk costing ₹12 per liter to get a mixture worth ₹8 per liter?",
            "opts": ["1:2", "2:3", "1:3", "3:4"],
            "correct": 0,
            "explanation": "Using alligation ratio: (12-8) : (8-0) = 4 : 8 = 1 : 2."
        },
        {
            "title": "Average - Excluded Number (2024)",
            "desc": "The average of 5 numbers is 25. If one number is excluded, the average becomes 23. Find the excluded number.",
            "opts": ["30", "33", "35", "28"],
            "correct": 1,
            "explanation": "Sum of 5 = 125. Sum of 4 = 92. Excluded number = 125 - 92 = 33."
        },
        {
            "title": "Ages - Intervals (2024)",
            "desc": "The sum of ages of 5 children born at intervals of 3 years is 50 years. Find the age of the youngest child.",
            "opts": ["3 years", "4 years", "5 years", "6 years"],
            "correct": 1,
            "explanation": "Sum = x + (x+3) + (x+6) + (x+9) + (x+12) = 5x + 30 = 50 => x = 4 years."
        },
        {
            "title": "Partnership - Capital Withdrawal (2024)",
            "desc": "A and B invest ₹5,000 and ₹7,000. After 6 months A withdraws ₹2,000. If total yearly profit is ₹4,500, find B's share.",
            "opts": ["₹2,400.00", "₹2,863.64", "₹3,100.50", "₹1,950.00"],
            "correct": 1,
            "explanation": "A ratio = 5000*6 + 3000*6 = 48,000. B ratio = 7000*12 = 84,000. Ratio = 4:7. B share = 7/11 * 4500 = ₹2,863.64."
        },
        {
            "title": "Boats & Streams - Downstream (2024)",
            "desc": "A man can row 8 km/hr in still water. Speed of stream is 2 km/hr. Find time taken to row 30 km downstream.",
            "opts": ["2.5 hours", "3 hours", "4 hours", "5 hours"],
            "correct": 1,
            "explanation": "Downstream speed = 8 + 2 = 10 km/hr. Time = 30 / 10 = 3 hours."
        },
        {
            "title": "Train Speed Problem (2024)",
            "desc": "A train travels 360 km at a uniform speed. If speed had been 5 km/h faster, it would take 48 mins less. What is the speed?",
            "opts": ["40 km/h", "45 km/h", "50 km/h", "55 km/h"],
            "correct": 1,
            "explanation": "Equation: 360/x - 360/(x+5) = 48/60 = 4/5. Solving quadratic yields x = 45 km/h."
        },
        {
            "title": "Father and Son Ages (2024)",
            "desc": "Sum of ages of father and son is 60 years. Father's age is four times that of his son. What are their current ages?",
            "opts": ["Son: 10, Father: 50", "Son: 12, Father: 48", "Son: 15, Father: 45", "Son: 14, Father: 46"],
            "correct": 1,
            "explanation": "x + 4x = 60 => 5x = 60 => x = 12. Son = 12, Father = 48."
        },
        {
            "title": "Time & Work - Worker Rate (2024)",
            "desc": "If 5 workers complete a task in 20 days, how many days will 8 workers take for the same task?",
            "opts": ["10 days", "12.5 days", "15 days", "16 days"],
            "correct": 1,
            "explanation": "Work = 5 × 20 = 100 worker-days. Days for 8 workers = 100 / 8 = 12.5 days."
        },
        {
            "title": "Mixture Problem - Water Percentage (2024)",
            "desc": "12L mixture (20% A) is mixed with 10L mixture (30% A). What is the percentage of water in new mixture?",
            "opts": ["70.5%", "75.45%", "80.2%", "68.4%"],
            "correct": 1,
            "explanation": "Water in 1st = 9.6L. Water in 2nd = 7L. Total water = 16.6L out of 22L = (16.6/22)*100 = 75.45%."
        },
        {
            "title": "Two Trains - Same Direction Passing (2024)",
            "desc": "Two trains move in same direction at 50 kmph and 32 kmph. Slower train passenger sees faster train pass in 15s. Find faster train length.",
            "opts": ["60 meters", "75 meters", "90 meters", "100 meters"],
            "correct": 1,
            "explanation": "Relative speed = 50 - 32 = 18 kmph = 5 m/s. Length = 5 m/s × 15s = 75 meters."
        },
        {
            "title": "Ratio Algebraic Expression (2024)",
            "desc": "Find (7x + 4y) / (x - 2y) if x / 2y = 3 / 2.",
            "opts": ["20", "25", "30", "15"],
            "correct": 1,
            "explanation": "x/2y = 3/2 => x = 3y. Substitute: (21y + 4y) / (3y - 2y) = 25y / y = 25."
        },

        # 2024 Logical Reasoning Questions
        {
            "title": "Number Series - Double Plus One (2024)",
            "desc": "Find the next number: 2, 5, 11, 23, 47, ?",
            "opts": ["90", "95", "96", "100"],
            "correct": 1,
            "explanation": "Pattern: previous × 2 + 1. Next = 47 × 2 + 1 = 95."
        },
        {
            "title": "Number Series - Odd Differences (2024)",
            "desc": "Find the next number: 3, 8, 15, 24, 35, ?",
            "opts": ["42", "48", "50", "52"],
            "correct": 1,
            "explanation": "Differences are 5, 7, 9, 11, 13. Next = 35 + 13 = 48."
        },
        {
            "title": "Letter Series - Plus 3 (2024)",
            "desc": "Find the next letter: A, D, G, J, ?",
            "opts": ["L", "M", "N", "O"],
            "correct": 1,
            "explanation": "Pattern: +3 letters. A(+3)->D(+3)->G(+3)->J(+3)->M."
        },
        {
            "title": "Coding-Decoding - Plus 2 Shift (2024)",
            "desc": "If 'TECHNOLOGY' is coded as 'VGEPQMQNA', how is 'COMPUTER' coded?",
            "opts": ["DQNRVTFU", "EQORWVGT", "EPNQVUFS", "FQPSXWHU"],
            "correct": 1,
            "explanation": "Each letter shifted by +2. COMPUTER -> EQORWVGT."
        },
        {
            "title": "Syllogism - Four Conclusions (2024)",
            "desc": "Statements: 1. All green are blue, 2. All blue are white. Which follow?",
            "opts": ["Only I follows", "Only I, II, and III follow", "All follow", "None follows"],
            "correct": 1,
            "explanation": "All green are blue -> Some blue are green. Combined: All green are white -> Some white/green follow. All white are blue does not follow."
        },
        {
            "title": "Blood Relations - Mother Relation (2024)",
            "desc": "Pointing to a man, a woman said, 'His mother is the only daughter of my mother.' How is the woman related to the man?",
            "opts": ["Sister", "Mother", "Aunt", "Grandmother"],
            "correct": 1,
            "explanation": "Only daughter of woman's mother = woman herself. So she is his mother."
        },
        {
            "title": "Direction Sense - Northeast (2024)",
            "desc": "A person walks 5 km north, then 3 km east, then 2 km south. Distance and direction from starting point?",
            "opts": ["5 km, North", "3√2 km, Northeast", "6 km, East", "4 km, Southeast"],
            "correct": 1,
            "explanation": "Net North = 3 km, Net East = 3 km. Distance = √(9+9) = 3√2 km Northeast."
        },
        {
            "title": "Seating Arrangement - Row Middle (2024)",
            "desc": "Five friends A, B, C, D, E sit in a row. A is not at end. B is right of A. C is at one end. D is between C and E. Who is in the middle?",
            "opts": ["A", "E", "D", "B"],
            "correct": 1,
            "explanation": "Arrangement: A-B-E-D-C. Middle position is E."
        },
        {
            "title": "Ordering & Ranking - Bottom Rank (2024)",
            "desc": "In a class of 40 students, Ravi ranks 15th from the top. What is his rank from the bottom?",
            "opts": ["25th", "26th", "27th", "24th"],
            "correct": 1,
            "explanation": "Rank from bottom = 40 - 15 + 1 = 26th."
        },
        {
            "title": "Statement & Conclusions - Flowers (2024)",
            "desc": "Statement: All roses are flowers. Some flowers are red. Conclusions: I) Some roses are red, II) All red things are flowers.",
            "opts": ["Only I follows", "Neither I nor II follows", "Only II follows", "Both follow"],
            "correct": 1,
            "explanation": "Neither conclusion necessarily follows from the given statements."
        },
        {
            "title": "Syllogism - Cats and Dogs Validity (2024)",
            "desc": "All cats are animals. Some animals are dogs. Therefore, some cats are dogs. Is this conclusion valid?",
            "opts": ["Valid", "Invalid conclusion", "Partially valid", "Cannot say"],
            "correct": 1,
            "explanation": "No direct link between cats and dogs is provided, so the conclusion is invalid."
        },
        {
            "title": "Blood Relations - Girl Photograph (2024)",
            "desc": "Pointing to a photograph, a man says, 'She is the daughter of my grandfather's only son.' How is the girl related to the man?",
            "opts": ["Mother", "Sister", "Daughter", "Cousin"],
            "correct": 1,
            "explanation": "Grandfather's only son = father. Father's daughter = sister."
        },
        {
            "title": "Number Series - Product Pattern (2024)",
            "desc": "Find missing number: 2, 6, 12, 20, ?",
            "opts": ["28", "30", "32", "36"],
            "correct": 1,
            "explanation": "n(n+1): 1*2=2, 2*3=6, 3*4=12, 4*5=20, 5*6=30."
        },
        {
            "title": "Coding-Decoding - Reverse Word (2024)",
            "desc": "If 'APPLE' is written as 'ELPPA', how is 'ORANGE' written?",
            "opts": ["EGNARO", "EGNORA", "OEGARN", "RANOEG"],
            "correct": 0,
            "explanation": "Reverses the letters: ORANGE -> EGNARO."
        },

        # 2024 Verbal Ability Questions
        {
            "title": "Reading Comprehension - AI Concerns (2024)",
            "desc": "Passage: 'Artificial Intelligence has revolutionized industries... However, concerns about job displacement and ethical implications remain significant challenges.' What are the main concerns?",
            "opts": ["High costs", "Job displacement and ethical implications", "Lack of memory", "Manual data entry"],
            "correct": 1,
            "explanation": "The passage highlights job displacement and ethical implications."
        },
        {
            "title": "Grammar - Neither Nor Rule (2024)",
            "desc": "Choose the correct sentence:",
            "opts": ["a) Neither the students nor the teacher were present", "b) Neither the students nor the teacher was present", "c) Neither the students or the teacher was present", "d) Neither student nor teachers was present"],
            "correct": 1,
            "explanation": "With 'neither...nor', verb agrees with closer subject ('teacher' is singular => 'was')."
        },
        {
            "title": "Vocabulary - Synonyms: ABUNDANT (2024)",
            "desc": "Find the synonym of 'ABUNDANT':",
            "opts": ["a) Scarce", "b) Plentiful", "c) Limited", "d) Rare"],
            "correct": 1,
            "explanation": "Abundant means existing in large quantities ('Plentiful')."
        },
        {
            "title": "Vocabulary - Antonyms: TRANSPARENT (2024)",
            "desc": "Find the antonym of 'TRANSPARENT':",
            "opts": ["a) Clear", "b) Opaque", "c) Visible", "d) Bright"],
            "correct": 1,
            "explanation": "Transparent means see-through, so 'Opaque' is the antonym."
        },
        {
            "title": "Sentence Correction - Data Subject (2024)",
            "desc": "Choose the correct sentence:",
            "opts": ["a) The data are incorrect", "b) The data is incorrect", "c) The datas are incorrect", "d) Data were wrong"],
            "correct": 1,
            "explanation": "'The data is incorrect' is the standard modern usage."
        },
        {
            "title": "Vocabulary - Synonyms: EPHEMERAL (2024)",
            "desc": "Choose the synonym for 'Ephemeral':",
            "opts": ["a) Eternal", "b) Transient", "c) Permanent", "d) Perpetual"],
            "correct": 1,
            "explanation": "Ephemeral means short-lived or temporary ('Transient')."
        },
        # 2024 Technical Assessment Questions
        {
            "title": "C Programming Output - Increment Sequence (2024)",
            "desc": "What is the output?\n\nint main() {\n    int x = 5;\n    printf(\"%d\", x++ + ++x);\n    return 0;\n}",
            "opts": ["10", "11", "12", "13"],
            "correct": 2,
            "explanation": "Note: Undefined behavior. Many compilers compute: x++ uses 5 (x=6), then ++x makes x=7, yielding 5 + 7 = 12."
        },
        {
            "title": "Loop Output - Continue Statement (2024)",
            "desc": "What is the output?\n\nint main() {\n    int i;\n    for(i=0; i<5; i++) {\n        if(i == 3) continue;\n        printf(\"%d \", i);\n    }\n    return 0;\n}",
            "opts": ["0 1 2 3 4", "0 1 2 4", "0 1 2", "1 2 4"],
            "correct": 1,
            "explanation": "Loop prints 0 1 2, skips i=3 due to continue, then prints 4."
        },
        {
            "title": "Array Pointer Manipulation (2024)",
            "desc": "What is the output?\n\nint main() {\n    int arr[] = {1, 2, 3, 4, 5};\n    int *p = arr;\n    printf(\"%d %d\", *(p+2), arr[3]);\n    return 0;\n}",
            "opts": ["2 3", "3 4", "3 5", "2 4"],
            "correct": 1,
            "explanation": "*(p+2) is arr[2] = 3. arr[3] = 4. Output: 3 4."
        },
        {
            "title": "Recursion Output - Factorial (2024)",
            "desc": "What is the output?\n\nint func(int n) {\n    if(n <= 1) return 1;\n    return n * func(n-1);\n}\nprintf(\"%d\", func(5));",
            "opts": ["24", "120", "720", "60"],
            "correct": 1,
            "explanation": "Calculates 5! = 5 × 4 × 3 × 2 × 1 = 120."
        },
        {
            "title": "Java Output - Pre & Post Increment (2024)",
            "desc": "What is the output?\n\npublic class Test {\n    public static void main(String[] args) {\n        int x = 10;\n        System.out.println(x++ + ++x);\n    }\n}",
            "opts": ["20", "21", "22", "24"],
            "correct": 2,
            "explanation": "x++ uses 10 (x becomes 11), ++x evaluates to 12. Total = 10 + 12 = 22."
        },
        {
            "title": "Python Output - Step Recursion (2024)",
            "desc": "What is the output?\n\ndef func(n):\n    if n <= 1:\n        return 1\n    return n * func(n-2)\n\nprint(func(6))",
            "opts": ["24", "48", "96", "120"],
            "correct": 1,
            "explanation": "func(6) = 6 × func(4) = 6 × (4 × func(2)) = 6 × 4 × (2 × func(0)) = 6 × 4 × 2 × 1 = 48."
        },
        {
            "title": "Pointer Arithmetic Output (2024)",
            "desc": "What is the output?\n\nint main() {\n    int arr[] = {10, 20, 30, 40, 50};\n    int *ptr = arr + 2;\n    printf(\"%d\", *(ptr+1));\n    return 0;\n}",
            "opts": ["20", "30", "40", "50"],
            "correct": 2,
            "explanation": "ptr points to arr[2] (30). ptr+1 points to arr[3] (40)."
        },
        {
            "title": "String Operations - strlen (2024)",
            "desc": "What is the output?\n\nint main() {\n    char str[] = \"HELLO\";\n    printf(\"%d\", strlen(str));\n    return 0;\n}",
            "opts": ["4", "5", "6", "0"],
            "correct": 1,
            "explanation": "'HELLO' contains 5 characters (excluding null terminator)."
        },
        {
            "title": "Pseudo Code - Value Swap (2024)",
            "desc": "What will be the output?\n\nBegin\n  Integer x = 10\n  Integer y = 5\n  x = x + y\n  y = x - y\n  x = x - y\n  Print x, y\nEnd",
            "opts": ["x = 10, y = 5", "x = 5, y = 10", "x = 15, y = 5", "x = 5, y = 5"],
            "correct": 1,
            "explanation": "Swaps x and y without temp variable. Final values: x = 5, y = 10."
        },
        {
            "title": "Networking - OSI Model Layer (2024)",
            "desc": "Which layer of the OSI model is responsible for end-to-end communication and error-free delivery of data?",
            "opts": ["a) Network Layer", "b) Transport Layer", "c) Session Layer", "d) Data Link Layer"],
            "correct": 1,
            "explanation": "Transport Layer (Layer 4) provides end-to-end communication and reliability."
        },

        # 2025 Technical Assessment Questions
        {
            "title": "C Output - Post and Pre Increment Dual Printf (2025)",
            "desc": "What is the output?\n\nint main() {\n    int a = 5, b = 10;\n    printf(\"%d %d\", a++, ++b);\n    printf(\" %d %d\", a, b);\n    return 0;\n}",
            "opts": ["5 10 6 11", "5 11 6 11", "6 11 6 11", "5 11 5 11"],
            "correct": 1,
            "explanation": "a++ uses 5 (a becomes 6), ++b makes b=11. First printf: 5 11. Second printf: 6 11."
        },
        {
            "title": "Loop with Break Output (2025)",
            "desc": "What is the output?\n\nint main() {\n    int i;\n    for(i=1; i<=10; i++) {\n        if(i == 5) break;\n        printf(\"%d \", i);\n    }\n    return 0;\n}",
            "opts": ["1 2 3 4 5", "1 2 3 4", "1 2 3 4 5 6 7 8 9 10", "5"],
            "correct": 1,
            "explanation": "Loop prints 1 2 3 4 and breaks when i == 5."
        },
        {
            "title": "Array and Pointer Indexing (2025)",
            "desc": "What is the output?\n\nint main() {\n    int arr[] = {10, 20, 30, 40};\n    int *p = arr;\n    printf(\"%d %d\", *p, *(p+3));\n    return 0;\n}",
            "opts": ["10 30", "10 40", "20 40", "10 20"],
            "correct": 1,
            "explanation": "*p is arr[0] = 10. *(p+3) is arr[3] = 40."
        },
        {
            "title": "Recursion - Natural Sum (2025)",
            "desc": "What is the output?\n\nint sum(int n) {\n    if(n == 0) return 0;\n    return n + sum(n-1);\n}\nprintf(\"%d\", sum(5));",
            "opts": ["10", "15", "20", "25"],
            "correct": 1,
            "explanation": "Calculates 5 + 4 + 3 + 2 + 1 + 0 = 15."
        },
        {
            "title": "Java Output - String Comparison (2025)",
            "desc": "What is the output?\n\npublic class Test {\n    public static void main(String[] args) {\n        String s1 = \"Hello\";\n        String s2 = new String(\"Hello\");\n        System.out.println(s1 == s2);\n        System.out.println(s1.equals(s2));\n    }\n}",
            "opts": ["true true", "false true", "true false", "false false"],
            "correct": 1,
            "explanation": "== checks reference identity (false), .equals() checks text content (true)."
        },
        {
            "title": "Python Output - Recursive List Sum (2025)",
            "desc": "What is the output?\n\ndef func(lst):\n    if len(lst) == 0:\n        return 0\n    return lst[0] + func(lst[1:])\n\nprint(func([1, 2, 3, 4]))",
            "opts": ["6", "10", "24", "0"],
            "correct": 1,
            "explanation": "Recursively sums elements: 1 + 2 + 3 + 4 + 0 = 10."
        },
        {
            "title": "Pointer Arithmetic - Negative Index (2025)",
            "desc": "What is the output?\n\nint main() {\n    int arr[] = {1, 2, 3, 4, 5};\n    int *p = &arr[2];\n    printf(\"%d %d\", p[-1], p[1]);\n    return 0;\n}",
            "opts": ["1 3", "2 4", "3 5", "2 3"],
            "correct": 1,
            "explanation": "p points to arr[2] (3). p[-1] is arr[1] = 2. p[1] is arr[3] = 4."
        },
        {
            "title": "Nested Loops - Right Triangle Pattern (2025)",
            "desc": "What is the output?\n\nint main() {\n    int i, j;\n    for(i=1; i<=3; i++) {\n        for(j=1; j<=i; j++) {\n            printf(\"%d\", j);\n        }\n        printf(\"\\n\");\n    }\n    return 0;\n}",
            "opts": ["1\\n12\\n123", "123\\n123\\n123", "1\\n22\\n333", "321"],
            "correct": 0,
            "explanation": "Prints 1 on line 1, 12 on line 2, 123 on line 3."
        },
        {
            "title": "Abstract Reasoning - Shape Sequence (2025)",
            "desc": "Identify the next shape in the sequence: Circle, Square, Triangle, Circle, Square, ?",
            "opts": ["Circle", "Square", "Triangle", "Hexagon"],
            "correct": 2,
            "explanation": "Sequence repeats every 3 shapes (Circle, Square, Triangle)."
        },
        {
            "title": "Pseudo Code - Simple Addition (2025)",
            "desc": "What will be the output?\n\nBegin\n    Set A = 10\n    Set B = 20\n    Set C = A + B\n    Print C\nEnd",
            "opts": ["10", "20", "30", "1020"],
            "correct": 2,
            "explanation": "Prints C = 10 + 20 = 30."
        },
        {
            "title": "Networking - Secure Protocol (2025)",
            "desc": "Which of the following is a common protocol used for secure communication over the internet?",
            "opts": ["a) HTTP", "b) FTP", "c) HTTPS", "d) SMTP"],
            "correct": 2,
            "explanation": "HTTPS (HyperText Transfer Protocol Secure) provides encrypted web communication."
        },
        {
            "title": "Statement & Assumption - Assignment Deadline (2025)",
            "desc": "Statement: 'All students must submit their assignments by Friday.' Assumption: Students are aware of the deadline. Is the assumption valid?",
            "opts": ["Yes, the assumption is valid", "No, invalid", "Irrelevant", "Cannot say"],
            "correct": 0,
            "explanation": "Valid assumption because instructions imply students are informed of the deadline."
        },
        {
            "title": "Cause and Effect - Company Profits (2025)",
            "desc": "Event 1: Company reported significant increase in profits. Event 2: Company launched a new product line. Relationship?",
            "opts": ["Event 1 is cause, Event 2 is effect", "Event 2 is the cause, Event 1 is the effect", "Independent events", "Both are causes"],
            "correct": 1,
            "explanation": "Launching a new product line (Event 2) leads to profit increase (Event 1)."
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

