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
            "### Problem Statement\n"
            "Given an array of integers `nums` and an integer `target`, return the 0-based indices of the two numbers such that they add up to `target`.\n\n"
            "You may assume that each input would have **exactly one solution**, and you may not use the same element twice.\n\n"
            "### Input Format\n"
            "- **Line 1:** Space-separated integers representing array `nums`.\n"
            "- **Line 2:** Target integer `target`.\n\n"
            "### Output Format\n"
            "Print two space-separated indices in ascending order.\n\n"
            "### Example 1\n"
            "**Input:**\n```\n2 7 11 15\n9\n```\n"
            "**Output:**\n```\n0 1\n```\n"
            "**Explanation:** Because nums[0] + nums[1] == 2 + 7 == 9, we return `0 1`."
        ),
        "input_format": "Line 1: Space-separated integers (nums)\nLine 2: Target integer",
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
            "### Problem Statement\n"
            "Write a program that reads a string `s` and prints the string reversed.\n\n"
            "### Input Format\n"
            "A single string `s` without spaces.\n\n"
            "### Output Format\n"
            "The reversed string on a single line.\n\n"
            "### Example 1\n"
            "**Input:** `hello`  \n"
            "**Output:** `olleh`"
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
            "### Problem Statement\n"
            "Given an integer `N`, print the first `N` terms of the Fibonacci sequence.\n\n"
            "The sequence starts with `0` and `1`. Each subsequent term is the sum of the two preceding ones.\n\n"
            "### Input Format\n"
            "A single integer `N` (1 ≤ N ≤ 20).\n\n"
            "### Output Format\n"
            "Print `N` space-separated integers on a single line.\n\n"
            "### Example 1\n"
            "**Input:** `5`  \n"
            "**Output:** `0 1 1 2 3`"
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
    # Auto-seed all 75+ benchmark placement questions into MongoDB
    if col.count_documents({"id": {"$regex": "^pmcq_"}}) < 50:
        col.delete_many({"id": {"$regex": "^pmcq_"}})
        _seed_placement_mcqs(100)
        print(f"[questions] Seeded {col.count_documents({})} total questions into MongoDB.")


# ── Public API ──────────────────────────────────────────────

def _strip(doc: dict) -> dict:
    """Remove MongoDB _id from a document."""
    doc.pop("_id", None)
    return doc


def get_all() -> list[dict]:
    """Return all questions (without test case expected outputs or MCQ correct options for security)."""
    col = _get_col()
    mcq_docs = list(col.find({"type": "mcq"}, {"_id": 0}))
    if len(mcq_docs) < 50 or any("```" not in m.get("description", "") for m in mcq_docs if "Output" in m.get("title", "")):
        col.delete_many({"id": {"$regex": "^pmcq_"}})
        _seed_placement_mcqs(100)

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


def get_placement_exam(mode: str = "full") -> dict:
    """
    Get MCQs and Coding questions for placement/resume exam.
    If database does not have MCQs or coding questions, auto-generate standard placement questions.
    """
    import random

    col = _get_col()
    
    # Always ensure database has fresh clean placement MCQs
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

    if mode == "resume" or mode == "mcq":
        selected_mcqs = mcqs[:30]
        selected_coding = []
    elif mode == "coding":
        selected_mcqs = []
        selected_coding = coding[:3]
    else:
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

    # Calculate user's rank relative to their own past attempt scores
    # (Higher score attempt gets Rank #1, 2nd highest gets Rank #2, etc.)
    user_higher_attempts = scores_col.count_documents({
        "user_email": user_email,
        "score": {"$gt": total_score}
    })
    rank = user_higher_attempts + 1
    total_candidates = scores_col.count_documents({"user_email": user_email})

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
    """Seed comprehensive 135 Chess Application & AI Engine Interview MCQs into MongoDB."""
    col = _get_col()
    
    user_mcqs = [
        # SECTION 1: APPLICATION ARCHITECTURE, JAVA SWING GUI & MULTITHREADING
        {
            "title": "Q1 [Architecture] - Event Dispatch Thread (EDT) Worker Isolation",
            "desc": "Why is the AI computation (Minimax search and LLM API requests) executed on separate worker threads rather than directly on the Event Dispatch Thread (EDT)?",
            "opts": [
                "A) Swing EDT only allows single-threaded mathematical calculations.",
                "B) Running heavy computations on EDT blocks the UI event loop, causing the graphical user interface to freeze.",
                "C) Java Swing graphics rendering fails if executed on the main thread.",
                "D) HttpURLConnection throws a compile-time exception if invoked on EDT."
            ],
            "correct": 1,
            "explanation": "The Swing Event Dispatch Thread (EDT) processes UI events (mouse clicks, drags) and screen repainting. Executing long-running algorithms like Minimax or network HTTP calls on the EDT freezes the UI, making the application non-responsive."
        },
        {
            "title": "Q2 [Multithreading] - Concurrency Guard Flag in AICoach",
            "desc": "Consider the snippet from AICoach.java:\n    public static void fetchAdviceAsync(String moveDescription) {\n        if (isFetching) return;\n        isFetching = true;\n        coachAdvice = \"Coach: Analyzing move...\";\n        new Thread(() -> { ... }).start();\n    }\nWhat is the primary purpose of checking `if (isFetching) return;` at the beginning of this method?",
            "opts": [
                "A) To force the thread to wait until previous network request responds.",
                "B) To act as a concurrency guard flag that prevents overlapping async API requests.",
                "C) To prevent Java heap stack overflow errors during API serialization.",
                "D) To reset the API key stored in .env."
            ],
            "correct": 1,
            "explanation": "isFetching acts as a atomic guard state. If a request is currently processing, subsequent trigger calls return immediately, eliminating race conditions and duplicate HTTP requests to Groq/Ollama."
        },
        {
            "title": "Q3 [GUI Rendering] - Swing Panel Redrawing Mechanism",
            "desc": "In GamePanel.java, the game loop uses `public void run()` with `Thread.sleep()`. What mechanism is used to trigger GUI redrawing on the Swing panel?",
            "opts": ["A) panel.drawNow()", "B) repaint()", "C) Graphics2D.flush()", "D) System.gc()"],
            "correct": 1,
            "explanation": "repaint() requests Swing to schedule a call to paintComponent(Graphics g), which safely renders the 8x8 checkerboard and piece sprites on the EDT."
        },
        {
            "title": "Q4 [GUI Component] - Main Top-Level Container Class",
            "desc": "Which top-level Java Swing container class serves as the main application window in chess.java?",
            "opts": ["A) JPanel", "B) JFrame", "C) JDialog", "D) Canvas"],
            "correct": 1,
            "explanation": "JFrame is the top-level container that holds GamePanel (a JPanel), configures window titles, resize permissions, default close operations (EXIT_ON_CLOSE), and frame icons."
        },
        {
            "title": "Q5 [Coordinate System] - Pixel Coordinate Calculation",
            "desc": "The board is represented as an 8x8 grid. If `Board.SQUARE_SIZE = 100`, what are the pixel coordinates (x, y) of a piece located at column index 3 and row index 5?",
            "opts": ["A) x = 300, y = 500", "B) x = 500, y = 300", "C) x = 3, y = 5", "D) x = 350, y = 550"],
            "correct": 0,
            "explanation": "Pixel coordinates are derived by x = col * SQUARE_SIZE and y = row * SQUARE_SIZE. For col = 3 and row = 5, x = 3 * 100 = 300 and y = 5 * 100 = 500."
        },
        {
            "title": "Q6 [Event Handling] - Mouse Drag-and-Drop Event Capture",
            "desc": "How does Mouse.java capture drag-and-drop input events in Java Swing?",
            "opts": [
                "A) By implementing ActionListener interface.",
                "B) By extending MouseAdapter and overriding mousePressed, mouseDragged, and mouseReleased.",
                "C) By polling the OS cursor position every 10 milliseconds.",
                "D) By reading input streams from System.in."
            ],
            "correct": 1,
            "explanation": "MouseAdapter is an abstract adapter class for receiving mouse events. Extending MouseAdapter allows overriding only relevant mouse handlers like mousePressed and mouseDragged."
        },
        {
            "title": "Q7 [Graphics Optimization] - Graphics2D vs Standard Graphics",
            "desc": "Why is Graphics2D preferred over standard Graphics in paintComponent() rendering?",
            "opts": [
                "A) Graphics2D provides advanced sub-pixel rendering, antialiasing, transformation matrix operations, and high-performance buffered image drawing.",
                "B) Standard Graphics does not support PNG images.",
                "C) Graphics2D automatically runs on GPU shaders.",
                "D) Graphics is deprecated in Java 17."
            ],
            "correct": 0,
            "explanation": "Graphics2D extends Graphics to provide fundamental controls over geometry, coordinate transformations, color management, and text/image rendering in Java AWT/Swing."
        },
        {
            "title": "Q8 [Resource Loading] - Classpath Sprite Loading via getResourceAsStream",
            "desc": "In Piece.java, sprites are loaded via `ImageIO.read(getClass().getResourceAsStream(imagePath + \".png\"))`. What is the key advantage of using getResourceAsStream() over standard File path references?",
            "opts": [
                "A) It loads images 10 times faster.",
                "B) It allows reading image resources embedded inside packaged compiled JAR files.",
                "C) It automatically resizes the image to 100x100 pixels.",
                "D) It converts PNG files to JPEG format."
            ],
            "correct": 1,
            "explanation": "getResourceAsStream() reads files relative to the class path, enabling seamless resource resolution both during development and when bundled into executable JAR files."
        },
        {
            "title": "Q9 [Double Buffering] - Eliminating Render Artifacts",
            "desc": "Java Swing JPanel uses double buffering by default during painting. What problem does double buffering eliminate?",
            "opts": [
                "A) Out of memory errors.",
                "B) Screen flickering caused by rendering intermediate frames directly into visible screen memory.",
                "C) Slow network API responses.",
                "D) Drag-and-drop mouse latency."
            ],
            "correct": 1,
            "explanation": "Double buffering renders visual components into an off-screen image buffer first before flipping it onto the screen, preventing visual tear and flicker."
        },
        {
            "title": "Q10 [State Machine] - Game Phase Architecture",
            "desc": "In GamePanel.java, game phases are controlled using integer constants (GAME_TITLE, PLAY, GAME_OVER, PROMOTION). What software design concept is this?",
            "opts": ["A) Observer Pattern", "B) Finite State Machine (FSM)", "C) Singleton Pattern", "D) Factory Method"],
            "correct": 1,
            "explanation": "Managing distinct application states and transitioning between them based on game events (e.g., reaching rank 0 transitions state to PROMOTION) is a classic Finite State Machine pattern."
        },
        {
            "title": "Q11 [Clean Code] - Classpath Binary Resource Deployment",
            "desc": "Why are piece sprites (.png) copied to the bin/piece/ directory during build compilation in run.ps1?",
            "opts": [
                "A) The Java compiler deletes original PNG files.",
                "B) Compiled .class files look for classpath resources inside the output directory (bin/).",
                "C) To compress image file sizes.",
                "D) To bypass Windows file permission locks."
            ],
            "correct": 1,
            "explanation": "At runtime, Java loads bytecode and classpath assets from the target binary output directory (bin/). Sprites must exist in bin/piece/ for getResourceAsStream() to locate them."
        },
        {
            "title": "Q12 [Game Loop Mechanics] - Target Frame Duration at 60 FPS",
            "desc": "A game loop executing at 60 FPS calculates target frame duration as approximately:",
            "opts": ["A) 100 milliseconds", "B) 16.67 milliseconds", "C) 1 second", "D) 0.16 milliseconds"],
            "correct": 1,
            "explanation": "1000 ms / 60 frames ≈ 16.67 ms per frame."
        },
        {
            "title": "Q13 [Thread Safety] - Invoking UI Mutations via SwingUtilities.invokeLater",
            "desc": "Why should modifications to Swing UI components (e.g., updating labels or showing promotion dialogs) be executed via SwingUtilities.invokeLater() when triggered from background worker threads?",
            "opts": [
                "A) Background threads cannot read String objects.",
                "B) Swing component structures are not thread-safe; mutating them off EDT can cause intermittent rendering bugs or deadlock.",
                "C) invokeLater() increases thread CPU priority.",
                "D) Java Swing crashes immediately if invoked off EDT."
            ],
            "correct": 1,
            "explanation": "Swing UI components are single-threaded and bound to EDT. SwingUtilities.invokeLater() queues runnable actions onto EDT to ensure safe UI execution."
        },
        {
            "title": "Q14 [Memory Management] - Garbage Collection Triggering",
            "desc": "In GamePanel.java, when a piece is captured, it is removed from simpieces. Why is explicit array list removal necessary in Java?",
            "opts": [
                "A) To trigger Java garbage collection by removing references to unneeded piece objects.",
                "B) Java does not have automatic garbage collection.",
                "C) Otherwise captured pieces would still attempt to draw on screen.",
                "D) Both A and C."
            ],
            "correct": 3,
            "explanation": "Removing captured piece objects from active render lists stops them from being drawn and drops active object references so the Garbage Collector can reclaim heap memory."
        },
        {
            "title": "Q15 [Concurrency Guard] - Race Conditions in Async State",
            "desc": "What risk occurs if isFetching variable in AICoach.java is accessed across multiple threads without synchronization or atomic state management?",
            "opts": [
                "A) Java syntax compilation error.",
                "B) Race conditions where two threads read isFetching == false simultaneously and spawn duplicate network requests.",
                "C) Disk corruptions in .env.",
                "D) Automatic model deletion in Ollama."
            ],
            "correct": 1,
            "explanation": "Without volatile access or synchronized atomic guards, thread memory caching can lead to simultaneous execution of critical sections, spawning redundant async requests."
        },

        # SECTION 2: OBJECT-ORIENTED DESIGN, BASE PIECE & INHERITANCE
        {
            "title": "Q16 [OOP Inheritance] - Base Piece Polymorphism",
            "desc": "All piece types (Pawn, Rook, Knight, Bishop, Queen, King) inherit from base class Piece. What is the primary OO benefit of this structure?",
            "opts": [
                "A) Eliminates the need for constructors.",
                "B) Polymorphic abstraction allowing generic lists like ArrayList<Piece> to store, update, draw, and evaluate all pieces identically.",
                "C) Makes piece objects static.",
                "D) Forces all pieces to move in straight lines."
            ],
            "correct": 1,
            "explanation": "Polymorphism allows collections like ArrayList<Piece> to manage any piece subclass uniformally without rigid type branching."
        },
        {
            "title": "Q17 [Method Overriding] - Subclass Movement Abstraction",
            "desc": "Look at Piece.java:\n    public boolean canMove(int targetCol, int targetRow) { return false; }\nWhy does the base class define canMove to return false?",
            "opts": [
                "A) Base Piece is a placeholder that requires concrete piece subclasses to override specific movement validation rules.",
                "B) To disable all piece movements by default.",
                "C) Because Piece is marked as final.",
                "D) To generate compile-time warnings."
            ],
            "correct": 0,
            "explanation": "Piece serves as a base class where default move validation fails unless overridden by concrete piece classes with specific movement rules."
        },
        {
            "title": "Q18 [Encapsulation] - Position Tracking and Rollback",
            "desc": "Fields col, row, preCol, preRow track piece positions. What is the role of preCol and preRow during move drag-and-drop operations?",
            "opts": [
                "A) They record the score of the previous turn.",
                "B) They preserve original board coordinates prior to move validation, enabling easy position rollback if a move is illegal.",
                "C) They store the AI search tree depth.",
                "D) They hold target coordinates for castling."
            ],
            "correct": 1,
            "explanation": "Keeping previous indices (preCol, preRow) allows the game engine to instantly restore a piece to its starting square if move checks fail."
        },
        {
            "title": "Q19 [Polymorphism in Practice] - Dynamic Method Dispatch",
            "desc": "What happens when `piece.canMove(c, r)` is executed on a reference variable `Piece piece = new Knight(WHITE, 1, 0)`?",
            "opts": [
                "A) Calls Piece.canMove().",
                "B) Calls Knight.canMove() at runtime via Dynamic Method Dispatch.",
                "C) Throws a ClassCastException.",
                "D) Returns false always."
            ],
            "correct": 1,
            "explanation": "Java uses runtime dynamic binding to resolve virtual method calls to the concrete instantiated object class (Knight)."
        },
        {
            "title": "Q20 [Grid Math] - Centering Sprite Coordinates",
            "desc": "Look at Piece.java:\n    public int getCol(int x) {\n        return (x + Board.HALF_SQUARE_SIZE) / Board.SQUARE_SIZE;\n    }\nWhat feature does this grid formula provide during visual piece dragging?",
            "opts": [
                "A) Converts integer columns into floating point angles.",
                "B) Snaps the center of the dragged sprite to the nearest board square column index.",
                "C) Prevents piece collision bugs.",
                "D) Calculates diagonal distance."
            ],
            "correct": 1,
            "explanation": "Adding HALF_SQUARE_SIZE shifts the pixel midpoint of the dragged sprite before integer division, causing coordinates to round naturally to nearest board column center."
        },
        {
            "title": "Q21 [Straight Line Collision Detection] - Intervening Obstructions",
            "desc": "In Piece.java, pieceIsOnStraightLine(targetCol, targetRow) iterates over squares between preCol/preRow and target square. What does returning true signify?",
            "opts": [
                "A) The line path is clear.",
                "B) There is an blocking piece obstructing the straight-line path.",
                "C) The target square is off the board.",
                "D) The move is a valid castle."
            ],
            "correct": 1,
            "explanation": "Returning true indicates that an intervening square along the row/column ray contains another piece, blocking sliding movement (Rook/Queen)."
        },
        {
            "title": "Q22 [Diagonal Collision Detection] - Diagonal Step Inspection",
            "desc": "In pieceIsOnDiagonalLine(), how is intervening square calculation performed?",
            "opts": [
                "A) Iterating step-by-step with diff = Math.abs(c - preCol) for matching row/col offsets.",
                "B) Using graph Dijkstra algorithm.",
                "C) Checking only 1 adjacent square.",
                "D) Evaluating Knight jump offsets."
            ],
            "correct": 0,
            "explanation": "Diagonal step checking increments/decrements column and row indices by equal step deltas (diff), verifying whether intermediate diagonal squares are unoccupied."
        },
        {
            "title": "Q23 [Piece Equality & Identification] - Target Square Occupant Lookup",
            "desc": "In Piece.java, how does getHittingP(targetCol, targetRow) locate a piece at target coordinates?",
            "opts": [
                "A) Searches SQL database.",
                "B) Iterates through getBoardList() checking if piece.col == targetCol && piece.row == targetRow && piece != this.",
                "C) Compares sprite image colors.",
                "D) Checks preCol values."
            ],
            "correct": 1,
            "explanation": "getHittingP iterates over active board pieces, matching target column and row while excluding the moving piece itself (piece != this)."
        },
        {
            "title": "Q24 [Validity Checking] - Friendly Fire Prevention",
            "desc": "Look at isValidSquare() in Piece.java:\n    public boolean isValidSquare(int targetCol, int targetRow) {\n        hittingP = getHittingP(targetCol, targetRow);\n        if (hittingP == null) return true;\n        else {\n            if (hittingP.color != this.color) return true;\n            else hittingP = null;\n        }\n        return false;\n    }\nWhat square target condition causes isValidSquare to return false?",
            "opts": [
                "A) Empty target square.",
                "B) Target square occupied by an enemy piece.",
                "C) Target square occupied by a friendly piece of the same color.",
                "D) Target square located on rank 4."
            ],
            "correct": 2,
            "explanation": "In chess, a piece cannot land on a square occupied by a piece of its own color."
        },
        {
            "title": "Q25 [Type Enum] - Type Safety via Enum",
            "desc": "Type.java defines `enum Type { PAWN, ROOK, KNIGHT, BISHOP, QUEEN, KING }`. Why use Java enum over plain integers?",
            "opts": [
                "A) Enums provide strong type safety, readable code constants, and prevent invalid numerical values.",
                "B) Enums run faster than primitive integers.",
                "C) Enums take 0 bytes of memory.",
                "D) Swing requiring enums for rendering."
            ],
            "correct": 0,
            "explanation": "Enums restrict values to predefined valid constants, catching invalid piece type assignments at compile time."
        },
        {
            "title": "Q26 [Board Reference Abstraction] - Cloned Board List Bindings",
            "desc": "Piece.java includes getBoardList():\n    public List<Piece> getBoardList() {\n        return (boardList != null) ? boardList : GamePanel.simpieces;\n    }\nWhy is boardList designed to support custom list overrides?",
            "opts": [
                "A) To allow AI search engines to evaluate isolated cloned board lists without altering active game pieces in GamePanel.simpieces.",
                "B) To handle piece rendering on separate monitors.",
                "C) To bypass garbage collection.",
                "D) To change piece colors dynamically."
            ],
            "correct": 0,
            "explanation": "Providing custom boardList bindings allows cloned pieces in AI simulation threads to run movement checks against isolated board state copies."
        },
        {
            "title": "Q27 [Sprite Memory] - Image Buffering on Initialization",
            "desc": "Piece sprites are loaded into BufferedImage image. What is the advantage of storing loaded images in memory on initialization?",
            "opts": [
                "A) Avoids reading disk files repeatedly on every single 60 FPS animation frame.",
                "B) Reduces CPU usage to 0%.",
                "C) Converts PNG into Vector graphics.",
                "D) Allows sprites to rotate automatically."
            ],
            "correct": 0,
            "explanation": "Disk I/O is slow. Loading image buffers once into heap RAM on object construction allows rapid 60 FPS drawing via hardware-accelerated memory."
        },
        {
            "title": "Q28 [Abstract vs Concrete] - Superclass Instantiation Model",
            "desc": "Why is Piece suitable as a superclass rather than instantiating raw Piece objects directly?",
            "opts": [
                "A) Raw pieces have no inherent movement rules; movement is specified by concrete subclasses (Knight, Rook, etc.).",
                "B) Piece requires 100 parameters.",
                "C) Swing crashes on raw class instances.",
                "D) Java forbids parent classes."
            ],
            "correct": 0,
            "explanation": "Generic pieces do not exist in chess; specific rules belong to concrete subclasses overriding canMove()."
        },
        {
            "title": "Q29 [Board Bound Checking] - Grid Boundary Enforcement",
            "desc": "Look at `isWithinBoard(int targetCol, int targetRow)`:\n    return targetCol >= 0 && targetCol <= 7 && targetRow >= 0 && targetRow <= 7;\nWhat occurs if a piece move check omits this call?",
            "opts": [
                "A) Moves landing outside indices 0..7 attempt out-of-bounds array or board reference evaluations.",
                "B) The piece transforms into a Queen.",
                "C) Game speed doubles.",
                "D) AI depth increases."
            ],
            "correct": 0,
            "explanation": "Chess boards are bounded 8x8 grids. Checking boundary limits prevents logical glitches and array index out-of-bounds errors."
        },
        {
            "title": "Q30 [Position Reset] - Restoring Invalid Drag Position",
            "desc": "What does resetPosition() in Piece.java perform?",
            "opts": [
                "A) Moves piece to starting rank at game launch.",
                "B) Restores col = preCol and row = preRow, resetting pixel coordinates back to original pre-drag state.",
                "C) Promotes pawn to queen.",
                "D) Deletes piece sprite."
            ],
            "correct": 1,
            "explanation": "When an attempted user drag-and-drop move is declared invalid, resetPosition() snaps the visual piece back to its previous square."
        },

        # SECTION 3: CONCRETE PIECE RULES & SPECIAL MOVES
        {
            "title": "Q31 [Pawn Direction Logic] - Vertical Row Index Direction",
            "desc": "In Pawn.java, moveValue is set based on piece color:\n    moveValue = (color == GamePanel.WHITE) ? -1 : 1;\nWhy is moveValue negative (-1) for White and positive (+1) for Black?",
            "opts": [
                "A) White pieces move down towards row 7, Black pieces move up.",
                "B) Board row index 0 represents rank 8 (top of screen, Black side) and row index 7 represents rank 1 (bottom, White side).",
                "C) White pieces move backward.",
                "D) Math.abs() requires negative values."
            ],
            "correct": 1,
            "explanation": "Computer screen graphics coordinates place y = 0 at the top. White starts at row 6/7 and advances upward towards row 0 (negative row direction)."
        },
        {
            "title": "Q32 [Pawn Initial Double Step] - Initial Two-Square Move Criteria",
            "desc": "A pawn can move 2 squares forward if:",
            "opts": [
                "A) moved == false, target column matches, intermediate square is empty, and starting row is rank 2/7 (preRow == 6 or 1).",
                "B) The pawn captures an enemy piece.",
                "C) The king has castled.",
                "D) It is the AI's first turn."
            ],
            "correct": 0,
            "explanation": "Pawns can advance 2 squares strictly on their initial move provided path squares are completely clear of obstructions."
        },
        {
            "title": "Q33 [En Passant State Tracking] - Marking Double Step",
            "desc": "In Piece.java, what sets twoStepped = true?",
            "opts": [
                "A) Moving a knight 2 squares horizontally.",
                "B) A pawn advancing 2 ranks forward in a single move (Math.abs(row - preRow) == 2).",
                "C) Castling across 2 squares.",
                "D) Promoted pawn taking 2 turns."
            ],
            "correct": 1,
            "explanation": "The twoStepped flag is set when a pawn makes a double-step initial advance, making it eligible for en passant capture on the immediate next turn."
        },
        {
            "title": "Q34 [En Passant Capture Mechanics] - Adjacent Capture Rule",
            "desc": "How does Pawn.canMove() identify an en passant capture?",
            "opts": [
                "A) Target row has enemy Queen.",
                "B) Pawn moves diagonally 1 square into empty space behind an adjacent enemy pawn that has twoStepped == true.",
                "C) King moves 2 steps.",
                "D) Pawn moves backward 1 rank."
            ],
            "correct": 1,
            "explanation": "En passant allows a pawn to capture an enemy pawn that passed over an attacked square via double-step on the preceding move."
        },
        {
            "title": "Q35 [Knight Move Vector Math] - L-Shape Offsets Product",
            "desc": "In Knight.java, valid movement satisfies:\n    Math.abs(targetCol - preCol) * Math.abs(targetRow - preRow) == 2\nWhy does this mathematical formula validate all 8 Knight jump moves?",
            "opts": [
                "A) Knights move in L-shapes: 2 steps in one axis and 1 step in perpendicular axis (2 * 1 = 2).",
                "B) Knights jump over 2 pieces.",
                "C) Knights occupy 2 squares simultaneously.",
                "D) It converts negative floats into integers."
            ],
            "correct": 0,
            "explanation": "All L-shaped offsets (±2, ±1) or (±1, ±2) have absolute coordinate deltas whose product equals 2 * 1 = 2."
        },
        {
            "title": "Q36 [Knight Obstruction Exemption] - Intermediate Jump Exemption",
            "desc": "Why does Knight.canMove() NOT call pieceIsOnStraightLine() or pieceIsOnDiagonalLine()?",
            "opts": [
                "A) Knights are not implemented in Java.",
                "B) Knights jump over intermediate pieces directly to target destination squares.",
                "C) Knights move only along rank 0.",
                "D) Knights capture friendly pieces."
            ],
            "correct": 1,
            "explanation": "Knights possess unique jumping mechanics in chess; intermediate squares between start and target do not obstruct Knight movement."
        },
        {
            "title": "Q37 [Bishop Movement] - Diagonal Ray Trajectory",
            "desc": "A Bishop can legally move to (targetCol, targetRow) if:",
            "opts": [
                "A) Absolute column delta equals absolute row delta (Math.abs(targetCol - preCol) == Math.abs(targetRow - preRow)) and diagonal path is unblocked.",
                "B) Target column matches current column.",
                "C) Target square contains a pawn.",
                "D) Target row is rank 0."
            ],
            "correct": 0,
            "explanation": "Diagonal moves require equal changes in horizontal and vertical distance along clear diagonal paths."
        },
        {
            "title": "Q38 [Rook Movement] - Straight Line Trajectory",
            "desc": "A Rook can legally move to (targetCol, targetRow) if:",
            "opts": [
                "A) targetCol == preCol OR targetRow == preRow, and straight line path is unblocked.",
                "B) Move distance is exactly 2 squares.",
                "C) Target square is diagonal.",
                "D) King has not moved."
            ],
            "correct": 0,
            "explanation": "Rooks slide horizontally or vertically along straight lines unblocked by other pieces."
        },
        {
            "title": "Q39 [Queen Movement Composition] - Straight and Diagonal Combination",
            "desc": "How is Queen.canMove() implemented in Queen.java?",
            "opts": [
                "A) Re-implementing custom ray logic from scratch.",
                "B) Combining Rook straight-line checks and Bishop diagonal-line checks: (straightLine || diagonalLine).",
                "C) Inheriting directly from Knight.",
                "D) Calling Minimax function."
            ],
            "correct": 1,
            "explanation": "A Queen combines the full movement capabilities of a Rook and a Bishop."
        },
        {
            "title": "Q40 [King Movement] - Single Adjacent Step",
            "desc": "What is the standard single-square movement condition for King.java?",
            "opts": [
                "A) Max step distance of 1 square in any adjacent direction (horizontal, vertical, diagonal).",
                "B) 2 squares in any direction.",
                "C) Straight lines only.",
                "D) Jump over adjacent pieces."
            ],
            "correct": 0,
            "explanation": "The King can step 1 square in any direction provided target square is valid and safe."
        },
        {
            "title": "Q41 [Kingside Castling Criteria] - Short Castle Requirements",
            "desc": "For Kingside castling (O-O), what conditions must be satisfied in King.canMove()?",
            "opts": [
                "A) King and Kingside Rook have not moved, intervening squares (preCol+1, preCol+2) are empty, and Rook exists on preCol+3.",
                "B) King is under check.",
                "C) Pawn is promoted.",
                "D) Target square has enemy piece."
            ],
            "correct": 0,
            "explanation": "Castling requires that neither King nor Rook has previously moved and all squares between them are unoccupied."
        },
        {
            "title": "Q42 [Queenside Castling Criteria] - Long Castle Intervening Squares",
            "desc": "For Queenside castling (O-O-O), how many intervening squares must be empty between King (col 4) and Queenside Rook (col 0)?",
            "opts": ["A) 1 square (col 3)", "B) 2 squares (col 3, col 2)", "C) 3 squares (col 3, col 2, col 1)", "D) 4 squares"],
            "correct": 2,
            "explanation": "Queenside castling requires 3 clear squares (d-file, c-file, b-file) between King on e-file and Rook on a-file."
        },
        {
            "title": "Q43 [Castling Safety Requirement] - Check Restriction in Castling",
            "desc": "In chess rules, can a King castle through or out of a square that is under attack by an enemy piece?",
            "opts": [
                "A) Yes, castling ignores checks.",
                "B) No, castling is illegal if the King is currently in check or if any square the King passes through/lands on is under attack.",
                "C) Only in Player vs Player mode.",
                "D) Only during Queenside castling."
            ],
            "correct": 1,
            "explanation": "Official chess rules strictly forbid castling out of check, through check, or into check."
        },
        {
            "title": "Q44 [Pawn Promotion Trigger] - Promotion Rank Reached",
            "desc": "In GamePanel.java, when does pawn promotion occur?",
            "opts": [
                "A) When a pawn reaches row index 0 (for White) or row index 7 (for Black).",
                "B) When a pawn captures a Queen.",
                "C) When a pawn moves 2 steps.",
                "D) When the game clock hits 0."
            ],
            "correct": 0,
            "explanation": "Reaching the farthest opposite rank (rank 8 for White = row 0, rank 1 for Black = row 7) triggers mandatory pawn promotion."
        },
        {
            "title": "Q45 [Pawn Promotion Selection] - FIDE Promotion Choices",
            "desc": "In this project's promotion modal UI, which piece types can a user promote a pawn into?",
            "opts": [
                "A) Queen only.",
                "B) Queen, Rook, Bishop, or Knight.",
                "C) King or Pawn.",
                "D) Super-Pawn."
            ],
            "correct": 1,
            "explanation": "FIDE rules allow pawn promotion to any major or minor piece of the same color: Queen, Rook, Bishop, or Knight."
        },

        # SECTION 4: MOVE GENERATION, LEGALITY & KING CHECK SIMULATION
        {
            "title": "Q46 [Move Candidate Generation] - Trajectory Filtering",
            "desc": "Why does MoveGenerator.java first filter candidate target squares before invoking canMove()?",
            "opts": [
                "A) To reduce unnecessary move validation calculations across off-board or irrelevant squares.",
                "B) Because canMove() throws exceptions on empty squares.",
                "C) To force AI search depth to 1.",
                "D) To clear board memory."
            ],
            "correct": 0,
            "explanation": "Generating geometric candidate target vectors (e.g., ray trajectories or knight jump offsets) narrows search space, improving move generation efficiency."
        },
        {
            "title": "Q47 [Simulated Move Application] - Speculative Board Mutation",
            "desc": "Look at MoveGenerator.java:\n    piece.col = c;\n    piece.row = r;\n    if (targetPiece != null) simpieces.remove(targetPiece);\nWhat is the purpose of temporarily mutating piece.col/row and removing targetPiece from simpieces?",
            "opts": [
                "A) To render move graphics on screen.",
                "B) To simulate candidate move board state in order to test if King becomes exposed to check.",
                "C) To save game state to disk.",
                "D) To notify LLM coach."
            ],
            "correct": 1,
            "explanation": "Board mutation simulates the prospective state. The engine then checks King safety (isIllegal) on that hypothetical state."
        },
        {
            "title": "Q48 [Move Rollback Integrity] - Restoring Speculative Mutations",
            "desc": "Immediately after checking isIllegal(), MoveGenerator executes:\n    piece.col = origCol;\n    piece.row = origRow;\n    if (targetPiece != null) simpieces.add(targetPiece);\nWhy is this rollback step mandatory?",
            "opts": [
                "A) To undo test mutations and restore original board state cleanly for subsequent candidate evaluations.",
                "B) To trigger move sounds.",
                "C) To flip turn color.",
                "D) To execute castling."
            ],
            "correct": 0,
            "explanation": "Search routines evaluate dozens of candidate moves. Reverting temporary changes guarantees board state integrity remains pristine for next iterations."
        },
        {
            "title": "Q49 [King Check Detection Logic] - Enemy Move Validation against King",
            "desc": "In isIllegal(simpieces, currentColor), how does the method detect if currentColor King is in check?",
            "opts": [
                "A) Checks if King position equals target position.",
                "B) Finds King of currentColor, then loops through all enemy pieces checking if enemy.canMove(king.col, king.row) == true.",
                "C) Reads .env settings.",
                "D) Checks if King moved == true."
            ],
            "correct": 1,
            "explanation": "If any enemy piece can legally capture the King on the current board configuration, the King is in check, rendering the candidate move illegal."
        },
        {
            "title": "Q50 [Checkmate Definition] - Dual Conditions for Checkmate",
            "desc": "In GamePanel.java, a player is in Checkmate when:",
            "opts": [
                "A) Player's King is currently in check AND MoveGenerator.generateLegalMoves() returns an empty list (0 legal moves).",
                "B) Player's King is captured.",
                "C) Player loses their Queen.",
                "D) Minimax search reaches depth 10."
            ],
            "correct": 0,
            "explanation": "Checkmate requires two simultaneous conditions: the King is under active attack (check), and no legal escape/blocking/capture move exists."
        },
        {
            "title": "Q51 [Stalemate Definition] - Safe King with Zero Moves",
            "desc": "A player is in Stalemate when:",
            "opts": [
                "A) Player's King is NOT in check, but the player has 0 legal moves available on their turn.",
                "B) Both players have equal material points.",
                "C) Game timer expires.",
                "D) Pawns are locked."
            ],
            "correct": 0,
            "explanation": "Stalemate occurs when the player to move is not in check but has no legal move available, resulting in an immediate draw."
        },
        {
            "title": "Q52 [Ray Target Generation] - Sliding Ray Boundary Termination",
            "desc": "In MoveGenerator.java, ray-casting for sliding pieces (Rook, Bishop, Queen) stops stepping along direction vector (dCol, dRow) when:",
            "opts": [
                "A) Ray reaches board edge (c < 0 || c > 7 || r < 0 || r > 7).",
                "B) Ray steps 1 square.",
                "C) Ray encounters a King.",
                "D) Always steps 8 times."
            ],
            "correct": 0,
            "explanation": "Sliding rays terminate as soon as target coordinates exit standard 8x8 board bounds."
        },
        {
            "title": "Q53 [Ray Target Collision Termination] - Obstruction Ray Break",
            "desc": "During ray target generation, why must target iteration break after encountering an occupying piece?",
            "opts": [
                "A) Sliding pieces cannot jump over or move through occupied squares.",
                "B) Java loops overflow.",
                "C) Target piece is destroyed.",
                "D) Prevents castling bugs."
            ],
            "correct": 0,
            "explanation": "A piece blocks sliding ray movement. Squares beyond an occupying piece are unreachable on that ray."
        },
        {
            "title": "Q54 [Pinned Piece Mechanics] - Automated Check Filter",
            "desc": "How does MoveGenerator naturally handle pinned pieces (a piece protecting its King from check)?",
            "opts": [
                "A) Simulating the pinned piece's move exposes King to enemy attack, causing isIllegal() to return true and discard the move.",
                "B) Custom pin checking code.",
                "C) Disabling pinned piece movement in Piece.java.",
                "D) Marking pinned pieces red."
            ],
            "correct": 0,
            "explanation": "Because every candidate move is validated via speculative simulation and check detection (isIllegal), moves that break a pin automatically fail legality validation."
        },
        {
            "title": "Q55 [Deep Clone Board Consistency] - Cloned List Rebinding",
            "desc": "In MoveGenerator.cloneBoard(), why are piece boardList references updated (`cloned.boardList = copy`)?",
            "opts": [
                "A) To bind cloned piece collision/hitting queries to the cloned list rather than active GUI pieces.",
                "B) To increase rendering performance.",
                "C) To allow multi-threaded drawing.",
                "D) To enable image compression."
            ],
            "correct": 0,
            "explanation": "Cloned pieces must evaluate collision methods (getHittingP) against the cloned list copy to avoid querying global GUI state GamePanel.simpieces."
        },
        {
            "title": "Q56 [En Passant Move Generation] - Captured Pawn Reference Pointer",
            "desc": "How is an en passant candidate move captured in MoveGenerator.Move?",
            "opts": [
                "A) capturedPiece reference points to the adjacent enemy pawn being taken en passant.",
                "B) capturedPiece is null.",
                "C) Move type is set to CASTLE.",
                "D) Row coordinate is set to -1."
            ],
            "correct": 0,
            "explanation": "En passant captures an enemy pawn situated on an adjacent column rather than the destination square. capturedPiece correctly points to the captured adjacent pawn."
        },
        {
            "title": "Q57 [Promotion Flag in Move] - Pawn Terminal Rank Evaluation",
            "desc": "In MoveGenerator.java, isPromotion flag evaluates to true when:",
            "opts": [
                "A) piece.type == PAWN AND destination toRow is rank 0 (White) or rank 7 (Black).",
                "B) Any piece reaches row 0.",
                "C) Queen takes King.",
                "D) Minimax search completes."
            ],
            "correct": 0,
            "explanation": "Pawn promotion triggers when a pawn reaches the terminal rank opposite its starting side."
        },
        {
            "title": "Q58 [Performance Optimization in Legal Move Check] - Color Filter",
            "desc": "Why does generateLegalMoves iterate only over pieces matching currentColor?",
            "opts": [
                "A) Opponent pieces cannot be moved on the current turn.",
                "B) Opponent pieces have no movement logic.",
                "C) Opponent pieces are hidden.",
                "D) To reverse board perspective."
            ],
            "correct": 0,
            "explanation": "Standard turn rules permit moving only friendly pieces belonging to the side whose turn it is."
        },
        {
            "title": "Q59 [Move Object Mutability] - Moved Flag Rollback",
            "desc": "In MoveGenerator.Move, storing `prevMoved = piece.moved` allows the search engine to:",
            "opts": [
                "A) Restore exact moved state flag during move undo.",
                "B) Check internet connectivity.",
                "C) Display past moves on GUI panel.",
                "D) Calculate FPS."
            ],
            "correct": 0,
            "explanation": "If a piece had moved == false prior to test simulation, undoing the move must restore moved = false so castling or double-step rights remain valid."
        },
        {
            "title": "Q60 [Castling Legality Verification] - Path Occupancy Check",
            "desc": "Why does King.canMove() check intermediate square occupancy prior to returning true for castling?",
            "opts": [
                "A) Castling requires all squares between King and Rook to be completely clear of pieces.",
                "B) Castling swaps piece colors.",
                "C) Rooks cannot move horizontally.",
                "D) To allow pawn promotion."
            ],
            "correct": 0,
            "explanation": "Castling cannot be executed if any piece stands between the King and the target Rook."
        },

        # SECTION 5: GRAPH ALGORITHMS & BFS PATHFINDING ENGINE
        {
            "title": "Q61 [Shortest Path Problem] - Unweighted Graph Shortest Path",
            "desc": "What graph search algorithm is implemented in BFSPathFinder.java to find the minimum number of legal moves for a piece to reach a destination square?",
            "opts": ["A) Depth-First Search (DFS)", "B) Breadth-First Search (BFS)", "C) A* Search", "D) Floyd-Warshall Algorithm"],
            "correct": 1,
            "explanation": "Breadth-First Search (BFS) explores graph nodes layer-by-layer in order of distance from start, guaranteeing shortest path discovery in unweighted graphs."
        },
        {
            "title": "Q62 [BFS Queue Structure] - FIFO Collection Implementation",
            "desc": "What Java Collection interface/implementation powers the frontier node search in BFSPathFinder.java?",
            "opts": [
                "A) java.util.Stack",
                "B) java.util.Queue implemented via java.util.LinkedList",
                "C) java.util.TreeSet",
                "D) java.util.HashMap"
            ],
            "correct": 1,
            "explanation": "BFS requires First-In, First-Out (FIFO) node processing, which is provided by Queue<Node> instantiated as LinkedList."
        },
        {
            "title": "Q63 [3D Visited Matrix State] - Promotion Reachability Dimension",
            "desc": "In BFSPathFinder.java:\n    boolean[][][] visited = new boolean[8][8][2];\nWhat state does index visited[col][row][1] track?",
            "opts": [
                "A) Square (col, row) visited after pawn promotion to Queen.",
                "B) Square (col, row) visited by Black pieces.",
                "C) Square under attack by enemy King.",
                "D) Square visited during castling."
            ],
            "correct": 0,
            "explanation": "Standard pawns move 1 square forward. Once promoted to a Queen on rank 0/7, movement capabilities change dramatically. Dimension [1] tracks post-promotion reachability."
        },
        {
            "title": "Q64 [BFS Node Definition] - Backtracking Parent Pointers",
            "desc": "A search node in BFSPathFinder stores (col, row, isPromoted, parent). What is the role of parent reference?",
            "opts": [
                "A) Points to predecessor Node in path, enabling backward reconstruction of shortest path from target back to start.",
                "B) Points to King object.",
                "C) Stores parent Java window frame.",
                "D) References parent piece color."
            ],
            "correct": 0,
            "explanation": "Each visited node maintains a link to the node that generated it (parent). Backtracking parent pointers reconstructs the path."
        },
        {
            "title": "Q65 [BFS Promotion Transformation] - Dummy Queen Node Expansion",
            "desc": "In BFSPathFinder.java, when a search node with isPromoted == true is polled, how does the algorithm test valid outgoing moves?",
            "opts": [
                "A) Uses a dummy Queen object (new Queen(color, col, row)) to compute sliding queen moves.",
                "B) Keeps pawn 1-step move logic.",
                "C) Uses Knight jump vectors.",
                "D) Terminates search."
            ],
            "correct": 0,
            "explanation": "Upon promotion, the piece assumes Queen movement capabilities. Creating a temporary Queen instance allows querying queen candidate moves."
        },
        {
            "title": "Q66 [Path Order Correction] - Reversing Backtracked Path",
            "desc": "Why does BFSPathFinder execute Collections.reverse(path) before returning the move list?",
            "opts": [
                "A) Reconstructive parent backtracking traverses from target square back to start node; reversing corrects order to start -> target.",
                "B) BFS finds paths in reverse order of board ranks.",
                "C) To flip Black piece paths.",
                "D) Java lists require reverse sorting."
            ],
            "correct": 0,
            "explanation": "Pointers trace backward (target -> parent -> parent ... -> start). Reversing yields natural forward routing."
        },
        {
            "title": "Q67 [BFS Termination Condition] - Target Match or Queue Exhaustion",
            "desc": "When does the BFS search loop stop scanning nodes?",
            "opts": [
                "A) When polled queue node matches target column and row (current.col == targetCol && current.row == targetRow), OR queue becomes empty.",
                "B) After scanning 10 nodes.",
                "C) When piece takes a King.",
                "D) After 1 second timeout."
            ],
            "correct": 0,
            "explanation": "Finding target coordinates terminates search immediately with optimal path. If queue empties without match, target square is unreachable."
        },
        {
            "title": "Q68 [Graph Representation of Chessboard] - Vertices and Edges Modeling",
            "desc": "In the BFS pathfinder, what components constitute graph vertices and edges?",
            "opts": [
                "A) Vertices = board squares (col, row, promotionState); Edges = legal moves allowed by piece.canMove().",
                "B) Vertices = piece colors; Edges = captures.",
                "C) Vertices = GUI panels; Edges = mouse clicks.",
                "D) Vertices = search depths; Edges = minimax scores."
            ],
            "correct": 0,
            "explanation": "Board state positions represent graph nodes (vertices), while valid piece moves connecting squares act as directed edges."
        },
        {
            "title": "Q69 [BFS Time Complexity on Chess Grid] - Upper Bound Grid Complexity",
            "desc": "For a fixed piece on an 8x8 board with max 128 reachability states, what is the upper bound complexity of BFS pathfinding?",
            "opts": [
                "A) O(V + E) where V <= 128 states and E <= 128 * 27 moves (Constant O(1) bounded runtime).",
                "B) O(2^N) exponential complexity.",
                "C) O(N!) factorial complexity.",
                "D) O(N^3) cubic complexity."
            ],
            "correct": 0,
            "explanation": "Because chess board size is fixed (8 * 8 * 2 = 128 max graph states), BFS executes in bounded time O(V+E) = O(1)."
        },
        {
            "title": "Q70 [Pawn BFS Promotion Edge Case] - Single Step Rank 0 Promotion",
            "desc": "If a White pawn starts at row 1 (b7) and target is b8 (row 0), how many steps does BFS return?",
            "opts": ["A) 1 step (Point(1, 0)).", "B) 2 steps.", "C) 0 steps.", "D) Infinite loop."],
            "correct": 0,
            "explanation": "Single step forward reaches row 0 (b8), satisfying target check in 1 move."
        },
        {
            "title": "Q71 [BFS State Space Isolation] - Preserving Outer Board State",
            "desc": "During BFS search loops, why are original piece attributes (col, row, preCol, preRow, moved) stored before loop expansion and restored immediately after?",
            "opts": [
                "A) To prevent queue iteration from permanently mutating active piece position state.",
                "B) To refresh GUI panel.",
                "C) To force move redrawing.",
                "D) To enable sound effects."
            ],
            "correct": 0,
            "explanation": "Speculative evaluation mutates test properties. Preserving original values ensures outer application state remains unharmed."
        },
        {
            "title": "Q72 [BFS vs DFS for Shortest Path] - Shortest Path Guarantee",
            "desc": "Why is BFS preferred over DFS (Depth-First Search) for computing minimum move paths?",
            "opts": [
                "A) DFS can traverse deep unpromising paths indefinitely without guaranteeing shortest path discovery.",
                "B) DFS uses more RAM than BFS.",
                "C) DFS cannot process Java objects.",
                "D) DFS works only on trees, not graphs."
            ],
            "correct": 0,
            "explanation": "Unweighted shortest path finding requires BFS. DFS may find a path, but it is not guaranteed to be shortest."
        },
        {
            "title": "Q73 [Unreachable Target Handling] - Empty Path Result",
            "desc": "If a target square is completely blocked by friendly pieces, what does BFSPathFinder.findShortestPath() return?",
            "opts": ["A) Empty list path (size 0).", "B) null.", "C) Throws exception.", "D) Returns start square."],
            "correct": 0,
            "explanation": "If queue exhausts without reaching target node, targetNode remains null and an empty list is returned."
        },
        {
            "title": "Q74 [BFS Duplicate State Avoidance] - Visited Matrix Cycle Prevention",
            "desc": "What prevents BFS from getting stuck in infinite loops between two adjacent squares (e.g. e2 -> e3 -> e2)?",
            "opts": [
                "A) visited[c][r][promoIdx] boolean array marks explored states and ignores re-visiting.",
                "B) Thread timeout.",
                "C) Maximum move counter limit.",
                "D) King check detection."
            ],
            "correct": 0,
            "explanation": "Marking nodes in visited matrix ensures each board state state is processed at most once."
        },
        {
            "title": "Q75 [Start Position Identity Check] - Zero Distance Identity",
            "desc": "If startCol == targetCol && startRow == targetRow in findShortestPath(), what is returned?",
            "opts": ["A) Empty path list (0 moves required).", "B) 1 move path.", "C) Null reference.", "D) Error code."],
            "correct": 0,
            "explanation": "If starting square matches target, distance is zero; function returns empty path immediately."
        },

        # SECTION 6: CLASSICAL AI ENGINE — MINIMAX & ALPHA-BETA PRUNING
        {
            "title": "Q76 [Minimax Search Goal] - Adversarial Game Optimization",
            "desc": "What is the fundamental optimization goal of the Minimax algorithm in turn-based 2-player zero-sum games like chess?",
            "opts": [
                "A) Maximize AI's score while assuming opponent plays optimal moves to minimize AI's score.",
                "B) Pick moves completely at random.",
                "C) Maximize material score of both players simultaneously.",
                "D) Minimize game play duration to under 10 seconds."
            ],
            "correct": 0,
            "explanation": "Minimax models zero-sum adversarial play: Maximizer attempts to maximize evaluation score, while Minimizer tries to minimize it."
        },
        {
            "title": "Q77 [Alpha-Beta Pruning Purpose] - Branch Cutoff Efficiency",
            "desc": "What efficiency benefit does Alpha-Beta Pruning bring to Minimax search?",
            "opts": [
                "A) Cuts off branch evaluations that cannot affect final decision, dramatically reducing searched nodes without altering minimax decision outcome.",
                "B) Reduces position evaluation accuracy by 50%.",
                "C) Replaces heuristic scoring with random selection.",
                "D) Bypasses legal move validation checks."
            ],
            "correct": 0,
            "explanation": "Alpha-Beta pruning returns identical mathematical results to full Minimax search while skipping evaluation of subtrees proven inferior to previously analyzed options."
        },
        {
            "title": "Q78 [Alpha Parameter Meaning] - Maximizer Lower Bound",
            "desc": "In Alpha-Beta Pruning, what does parameter alpha represent?",
            "opts": [
                "A) Maximum evaluation score guaranteed to Maximizing player so far along search path.",
                "B) Minimum score of Minimizing player.",
                "C) Current search tree depth.",
                "D) Total count of evaluated nodes."
            ],
            "correct": 0,
            "explanation": "Alpha tracks best lower-bound score Maximizer can guarantee. Any opponent move resulting in score < alpha will be rejected by Maximizer."
        },
        {
            "title": "Q79 [Beta Parameter Meaning] - Minimizer Upper Bound",
            "desc": "In Alpha-Beta Pruning, what does parameter beta represent?",
            "opts": [
                "A) Minimum evaluation score guaranteed to Minimizing player so far along search path.",
                "B) Maximum score of Maximizing player.",
                "C) Search thread priority.",
                "D) Random seed value."
            ],
            "correct": 0,
            "explanation": "Beta tracks best upper-bound score Minimizer can limit Maximizer to. Any move giving score > beta will be avoided by Minimizer."
        },
        {
            "title": "Q80 [Cutoff Condition] - Pruning Abort Condition",
            "desc": "Look at snippet from Minimax.java:\n    if (beta <= alpha) break;\nWhat condition triggers an Alpha-Beta cutoff (pruning)?",
            "opts": ["A) beta <= alpha", "B) alpha > 1000", "C) depth == 1", "D) legalMoves.size() == 0"],
            "correct": 0,
            "explanation": "When beta <= alpha, current search branch is worse than a previously discovered branch for one player, so further exploration of this node is aborted (break)."
        },
        {
            "title": "Q81 [Terminal Search Condition] - Base Case Recursion Termination",
            "desc": "When does recursive method minimax() stop expanding child nodes and return a numeric evaluation?",
            "opts": [
                "A) When depth == 0 OR current board state has 0 legal moves (Checkmate / Stalemate).",
                "B) When time reaches 1 second.",
                "C) When Queen is captured.",
                "D) When alpha equals beta."
            ],
            "correct": 0,
            "explanation": "Reaching search depth limit (depth == 0) or game termination (no legal moves) triggers base-case position scoring."
        },
        {
            "title": "Q82 [Terminal Value for Checkmate] - Checkmate Penalty Constant",
            "desc": "In Minimax.java, what score value is returned when Maximizer faces Checkmate (0 legal moves on Maximizer turn)?",
            "opts": ["A) -100000 (Extremely negative penalty)", "B) +100000", "C) 0", "D) -10"],
            "correct": 0,
            "explanation": "Checkmate against Maximizer represents absolute defeat, encoded as extreme negative penalty (-100000)."
        },
        {
            "title": "Q83 [Depth & Difficulty Scaling] - Search Depth Mapping",
            "desc": "In AIPlayer.java, how do difficulty levels (Easy, Medium, Hard) map to Minimax search depth?",
            "opts": [
                "A) Easy = Depth 2, Medium = Depth 4, Hard = Depth 6.",
                "B) Easy = Depth 10, Medium = Depth 5, Hard = Depth 1.",
                "C) Easy = Random, Medium = Depth 1, Hard = Depth 2.",
                "D) Depth is fixed at 3 for all levels."
            ],
            "correct": 0,
            "explanation": "Search depth controls lookahead horizon. Higher depth explores exponential candidate move combinations, raising play difficulty."
        },
        {
            "title": "Q84 [Move Ordering Benefit] - Early Bound Tightening",
            "desc": "Why does pre-sorting legal moves (e.g. captures first) significantly improve Alpha-Beta Pruning efficiency?",
            "opts": [
                "A) Evaluating strong candidate moves early produces tight alpha / beta bounds sooner, maximizing pruned search branches.",
                "B) Move sorting decreases memory usage.",
                "C) Move sorting changes checkmate definitions.",
                "D) It prevents draw offers."
            ],
            "correct": 0,
            "explanation": "Alpha-Beta pruning achieves theoretical maximum efficiency O(B^(D/2)) when best moves are evaluated first in branch order."
        },
        {
            "title": "Q85 [Minimax Evaluation Perspectivism] - Zero-Sum Polarity",
            "desc": "In Minimax.java, how are evaluation scores interpreted for White vs Black?",
            "opts": [
                "A) Positive score favors White (Maximizer), negative score favors Black (Minimizer).",
                "B) Positive score favors Black, negative favors White.",
                "C) Score is always positive integer.",
                "D) Score reflects move count."
            ],
            "correct": 0,
            "explanation": "Zero-sum convention sets White as Maximizer (+infinity) and Black as Minimizer (-infinity)."
        },
        {
            "title": "Q86 [Tree Search Complexity] - Full Minimax Node visits",
            "desc": "Without pruning, what is the time complexity of full Minimax search with branching factor B and depth D?",
            "opts": ["A) O(B^D)", "B) O(B + D)", "C) O(D^2)", "D) O(log B)"],
            "correct": 0,
            "explanation": "Minimax traverses a uniform tree with B branches per level down D levels, requiring O(B^D) node visits."
        },
        {
            "title": "Q87 [Optimal Alpha-Beta Complexity] - Pruned Tree Complexity",
            "desc": "With perfect move ordering, what is the reduced time complexity of Alpha-Beta Pruning search?",
            "opts": [
                "A) O(B^(D/2)) (Effectively doubling effective search depth for same computational budget).",
                "B) O(B * D)",
                "C) O(1)",
                "D) O(D^B)"
            ],
            "correct": 0,
            "explanation": "Optimal pruning cuts branching search exponent in half, allowing search depth to double in equal computation time."
        },
        {
            "title": "Q88 [Minimax Search State Isolation] - In-Place Mutation and Undo",
            "desc": "Why does minimax() call applyMove() and undoMove() on a single board instance instead of generating new board objects at every node?",
            "opts": [
                "A) Mutating and restoring a single board list avoids generating millions of short-lived objects, avoiding severe Java GC performance overhead.",
                "B) Java forbids allocating memory in loops.",
                "C) Undo move runs faster than clone.",
                "D) Both A and C."
            ],
            "correct": 3,
            "explanation": "Modifying state in-place and undoing after recursive calls avoids massive object allocation churn and garbage collection pauses."
        },
        {
            "title": "Q89 [Transposition Table Concept] - Caching Board Positions",
            "desc": "What optimization technique (often paired with Minimax) caches previously evaluated board positions via Zobrist hashing to prevent re-analyzing duplicate search transposition nodes?",
            "opts": ["A) Transposition Table", "B) Binary Search Tree", "C) HashMap rendering", "D) Stack trace"],
            "correct": 0,
            "explanation": "Transposition tables store evaluation results of positions reached via different move orderings (transpositions), skipping duplicate subtree searches."
        },
        {
            "title": "Q90 [Horizon Effect] - Premature Depth Truncation",
            "desc": "What chess engine limitation occurs when Minimax depth limit cuts off search right before a major piece capture or tactical sequence completes?",
            "opts": ["A) Horizon Effect", "B) Alpha Bleed", "C) Pruning Slip", "D) Memory Leak"],
            "correct": 0,
            "explanation": "The Horizon Effect occurs when depth limit cuts off search prematurely, misevaluating positions whose tactical resolution lies just beyond search depth limit."
        },

        # SECTION 7: EVALUATION HEURISTICS & PIECE-SQUARE TABLES (PST)
        {
            "title": "Q91 [Board Evaluation Zero-Sum Metric] - Score Formula",
            "desc": "How is overall board score calculated in BoardEvaluator.java?",
            "opts": [
                "A) Score = Sum(White Piece Values + Positional Bonuses) - Sum(Black Piece Values + Positional Bonuses)",
                "B) Score = White Piece Count / Black Piece Count",
                "C) Score = Total legal moves",
                "D) Score = Game panel width"
            ],
            "correct": 0,
            "explanation": "Board evaluation sums material and positional scores for White pieces and subtracts material and positional scores for Black pieces."
        },
        {
            "title": "Q92 [Centipawn System] - Integer Pawn Scale",
            "desc": "In chess engines, what unit of value does integer 100 represent in BoardEvaluator.java?",
            "opts": [
                "A) Value equivalent to 1 standard Pawn (100 centipawns = 1.0 pawn material unit).",
                "B) Value of 1 Queen.",
                "C) 100 milliseconds execution time.",
                "D) 100 percent win probability."
            ],
            "correct": 0,
            "explanation": "Centipawn valuation scales 1 Pawn to 100 points, allowing granular integer point adjustments without floating-point math overhead."
        },
        {
            "title": "Q93 [Piece Values in Engine] - Material Centipawn Weights",
            "desc": "According to BoardEvaluator.java, what material values are assigned to pieces?",
            "opts": [
                "A) Pawn = 100, Knight = 320, Bishop = 330, Rook = 500, Queen = 900, King = 20000",
                "B) Pawn = 10, Knight = 30, Bishop = 30, Rook = 50, Queen = 90, King = 100",
                "C) Pawn = 1, Knight = 2, Bishop = 3, Rook = 4, Queen = 5, King = 6",
                "D) Pawn = 50, Knight = 100, Bishop = 150, Rook = 200, Queen = 400, King = 1000"
            ],
            "correct": 0,
            "explanation": "Standard classical engine material weights assign King an overwhelming value (20,000) so king safety overrides all material trades."
        },
        {
            "title": "Q94 [Piece-Square Tables (PST) Purpose] - Positional Bonus Heuristics",
            "desc": "What is the primary purpose of Piece-Square Tables in BoardEvaluator.java?",
            "opts": [
                "A) Provide positional bonuses/penalties based on piece placement on the 8x8 grid (e.g. rewarding knights controlling center, penalizing edge knights).",
                "B) Render piece graphics textures.",
                "C) Store move history strings.",
                "D) Generate random AI delay."
            ],
            "correct": 0,
            "explanation": "PST tables encode positional heuristics, encouraging pieces to occupy strategically advantageous squares (such as center squares d4, d5, e4, e5)."
        },
        {
            "title": "Q95 [Knight PST Penalty for Rim Squares] - Edge Knight Mobility Penalty",
            "desc": "Why do Knight PST matrix borders contain negative values like -50 or -40?",
            "opts": [
                "A) 'A knight on the rim is dim' — Knights on edge squares control far fewer squares (3-4) compared to center knights (8 squares).",
                "B) Edge squares crash graphics rendering.",
                "C) Edge knights cannot jump.",
                "D) Edge squares belong to opponent."
            ],
            "correct": 0,
            "explanation": "Centralized knights exert maximum board control over 8 squares, whereas edge knights have restricted mobility (3-4 target squares)."
        },
        {
            "title": "Q96 [Pawn PST Advancement Incentives] - Promotion Push Reward",
            "desc": "Why do Pawn PST values increase from row 6 to row 1 (e.g. 5, 10, 20, 50)?",
            "opts": [
                "A) Pawns closer to promotion ranks become vastly more dangerous and valuable positional assets.",
                "B) Pawns move faster near rank 0.",
                "C) Pawns change color.",
                "D) Pawns protect King from rank 0."
            ],
            "correct": 0,
            "explanation": "Advanced pawns threaten promotion to Queen, so PST heuristics reward pushing pawns towards opposite rank."
        },
        {
            "title": "Q97 [King PST Opening vs Endgame] - King Safety Positioning",
            "desc": "In BoardEvaluator.java, King PST rewards corner positions (g1/b1 = 20..30) and penalizes center positions (-50). What phase of chess does this PST model?",
            "opts": [
                "A) Opening and Middlegame (encouraging King to stay safe behind pawn shields via castling).",
                "B) Endgame activation.",
                "C) Pawn promotion.",
                "D) Stalemate draw setup."
            ],
            "correct": 0,
            "explanation": "During opening and middlegame phases, King safety requires staying sheltered on castled wing squares behind pawn shields."
        },
        {
            "title": "Q98 [PST Perspective Flipping for Black] - Vertical Mirroring",
            "desc": "Look at BoardEvaluator.java:\n    if (p.color == GamePanel.BLACK) row = 7 - row;\nWhy must row index be inverted to 7 - row when looking up PST values for Black pieces?",
            "opts": [
                "A) PST arrays are written from White's rank perspective (row 0 = rank 8); Black advances down the board, so row indexing must be vertically mirrored.",
                "B) Black pieces move horizontally.",
                "C) Black pieces start at row 0.",
                "D) Java arrays flip for negative numbers."
            ],
            "correct": 0,
            "explanation": "Because Black advances in opposite board direction, vertically mirroring array lookup applies symmetric positional evaluation to Black."
        },
        {
            "title": "Q99 [Bishop Pair Bonus Concept] - Diagonal Coverage Compensation",
            "desc": "Why do modern chess evaluation engines often add an extra +50 point bonus if a player retains both Bishops?",
            "opts": [
                "A) Two Bishops complement each other by controlling dark and light square diagonals simultaneously.",
                "B) Bishops can castle.",
                "C) Bishops move faster than queens.",
                "D) Bishops double pawn values."
            ],
            "correct": 0,
            "explanation": "Retaining both Bishops grants total coverage across all 64 dark and light squares."
        },
        {
            "title": "Q100 [Evaluation Function Static Balance] - Symmetrical Position Equilibrium",
            "desc": "If both players have identical material and symmetrical piece placement, what value does BoardEvaluator.evaluate() return?",
            "opts": ["A) 0 (Neutral equal position balance).", "B) +100", "C) -100", "D) 20000"],
            "correct": 0,
            "explanation": "Zero-sum scoring subtracts Black total score from White total score. Equal positions yield score of 0."
        },

        # SECTION 8: GENERATIVE AI COACH & LLM INTEGRATION (GROQ & OLLAMA)
        {
            "title": "Q101 [Architecture of AI Coach] - Desktop App REST Client",
            "desc": "How does AICoach.java integrate Generative AI coaching into the Java desktop chess app?",
            "opts": [
                "A) Invokes REST HTTP POST calls using native java.net.HttpURLConnection to cloud/local LLM APIs and displays text response on GUI.",
                "B) Embeds Python runtime interpreter inside JVM.",
                "C) Runs C++ binary via JNI.",
                "D) Hardcodes 1000 chess advice strings."
            ],
            "correct": 0,
            "explanation": "AICoach acts as an HTTP REST client sending JSON payloads containing game context to LLM API endpoints and rendering advice strings."
        },
        {
            "title": "Q102 [Primary Cloud API Provider] - Ultra-Low Latency Groq API",
            "desc": "What cloud service and model endpoint does AICoach query when GROQ_API_KEY environment variable is available?",
            "opts": [
                "A) Groq Cloud API (https://api.groq.com/openai/v1/chat/completions) running model llama-3.1-8b-instant.",
                "B) OpenAI GPT-4 API.",
                "C) Google Gemini Pro API.",
                "D) AWS Bedrock API."
            ],
            "correct": 0,
            "explanation": "AICoach targets Groq Cloud API for ultra-fast (~0.15s response latency) LLM inference running llama-3.1-8b-instant."
        },
        {
            "title": "Q103 [Local Ollama Fallback] - Offline Port 11434 Fallback",
            "desc": "If GROQ_API_KEY is missing or unconfigured, what local endpoint URL does AICoach query?",
            "opts": [
                "A) http://localhost:11434/api/generate (Local Ollama server running qwen3:8b).",
                "B) http://localhost:8080/api/chess",
                "C) https://ollama.com/api",
                "D) http://127.0.0.1:3000"
            ],
            "correct": 0,
            "explanation": "Ollama exposes a local REST API on port 11434. AICoach POSTs prompt payloads to /api/generate for zero-cost offline AI advice."
        },
        {
            "title": "Q104 [API Key Configuration Sources] - Environment and .env Cascade",
            "desc": "Where does AICoach attempt to resolve the GROQ_API_KEY credential?",
            "opts": [
                "A) System.getenv(\"GROQ_API_KEY\"), and if null/empty, reads key line from local .env configuration file.",
                "B) Windows Registry only.",
                "C) Command line prompt user input.",
                "D) Scrapes key from web."
            ],
            "correct": 0,
            "explanation": "Checking OS environment variables followed by local .env file parsing supports flexible deployment setups across CLI and IDEs."
        },
        {
            "title": "Q105 [JSON Escape Helper Function] - Escape String Sanitization",
            "desc": "Look at snippet from AICoach.java:\n    private static String escapeJson(String raw) {\n        return raw.replace(\"\\\\\", \"\\\\\\\\\").replace(\"\\\"\", \"\\\\\\\"\").replace(\"\\n\", \"\\\\n\");\n    }\nWhat issue does escapeJson() prevent when constructing raw JSON payloads?",
            "opts": [
                "A) Strips unescaped double quotes and line breaks that would break JSON grammar syntax and trigger HTTP 400 Bad Request error.",
                "B) Encrypts API token.",
                "C) Translates English prompt to French.",
                "D) Removes HTML tags."
            ],
            "correct": 0,
            "explanation": "Payload strings containing unescaped quote marks or carriage returns produce invalid JSON syntax. Escaping special characters produces valid payloads."
        },
        {
            "title": "Q106 [HTTP Connection Timeouts] - Read/Connect Socket Timeouts",
            "desc": "Why does AICoach set explicit timeouts (`conn.setConnectTimeout(4000); conn.setReadTimeout(6000);`)?",
            "opts": [
                "A) Prevents HTTP requests from hanging indefinitely if network connection drops or LLM server freezes.",
                "B) Speed up LLM inference time.",
                "C) Mandated by Swing.",
                "D) Saves API costs."
            ],
            "correct": 0,
            "explanation": "Network calls without timeouts risk hanging threads indefinitely if endpoints fail to respond."
        },
        {
            "title": "Q107 [LLM Response Extraction] - Zero-Dependency Substring Parser",
            "desc": "How does AICoach extract generated text advice from Groq REST JSON response string without external libraries?",
            "opts": [
                "A) Searches substring markers (\"content\":\"\") and extracts content enclosed between response quotes.",
                "B) Uses Regex compiler.",
                "C) Calls Jackson ObjectMapper.",
                "D) Converts response bytes to PNG image."
            ],
            "correct": 0,
            "explanation": "To remain lightweight without external library dependencies, lightweight substring extraction parses text between JSON keys."
        },
        {
            "title": "Q108 [Prompt Engineering Constraints] - Strict Token & Word Bounds",
            "desc": "In AICoach.java, the prompt requests:\n    \"You are a Master Chess Coach. Give a 1-sentence tactical tip under 12 words for this move: ...\"\nWhy are strict token limits (max_tokens = 35, 12 words) enforced in prompt engineering?",
            "opts": [
                "A) Ensures advice fits neatly on Swing GUI overlay panel.",
                "B) Ollama cannot generate more than 12 words.",
                "C) To decrease Groq API costs.",
                "D) Both A and C."
            ],
            "correct": 3,
            "explanation": "Short prompt constraints keep UI display clean, lower generation latency, and minimize API token usage."
        },
        {
            "title": "Q109 [Exception Handling in HTTP Thread] - Network Failure Catch Block",
            "desc": "In AICoach.java, if network fails or Ollama is not running, what advice text displays on GUI?",
            "opts": [
                "A) \"Coach: Set GROQ_API_KEY or run Ollama\"",
                "B) Application crashes with RuntimeException.",
                "C) Black screen.",
                "D) \"Coach: You win!\""
            ],
            "correct": 0,
            "explanation": "Exception catch blocks handle network failures gracefully by displaying clear configuration guidance on the coach HUD."
        },
        {
            "title": "Q110 [Asynchronous UI Update Mechanism] - Volatile Canvas Repaint Binding",
            "desc": "When background thread fetches LLM advice string successfully, how is GUI updated?",
            "opts": [
                "A) Mutates static variable coachAdvice, which next 60 FPS repaint loop automatically renders onto canvas.",
                "B) Reboots application.",
                "C) Sends email notification.",
                "D) Force redraws desktop monitor."
            ],
            "correct": 0,
            "explanation": "The panel continuously repaints at 60 FPS, reading updated coachAdvice string seamlessly without blocking main game loop."
        },

        # SECTION 9: BUILD SYSTEMS, TESTING & DEPLOYMENT PIPELINE
        {
            "title": "Q111 [Build Automation Scripts] - PowerShell run.ps1 Script",
            "desc": "What compilation script is provided in the repository for single-command Windows PowerShell execution?",
            "opts": ["A) run.ps1", "B) build.xml", "C) pom.xml", "D) Makefile"],
            "correct": 0,
            "explanation": "run.ps1 automates invoking javac, copying image assets to bin/, and executing the compiled main Java class chess.chess."
        },
        {
            "title": "Q112 [Java Compiler Flags] - Destination Bytecode Directory",
            "desc": "In run.ps1, the command executed is:\n    javac -d bin -sourcepath src src/chess/*.java src/piece/*.java\nWhat does the -d bin flag specify?",
            "opts": [
                "A) Destination directory where compiled .class bytecode output files are placed.",
                "B) Java debug level 2.",
                "C) Delete source code after compilation.",
                "D) Download dependencies."
            ],
            "correct": 0,
            "explanation": "-d instructs javac to store compiled bytecode (.class) files into the specified directory (bin)."
        },
        {
            "title": "Q113 [Unit Test Suites in Repository] - Graph Pathfinder Unit Test",
            "desc": "Which unit test class in src/chess/ specifically tests graph pathfinder shortest path calculations?",
            "opts": ["A) TestBFS.java", "B) TestCastling.java", "C) TestCastlePlace.java", "D) TestAI.java"],
            "correct": 0,
            "explanation": "TestBFS.java instantiates pieces and asserts that BFSPathFinder.findShortestPath() returns correct move step sequences."
        },
        {
            "title": "Q114 [Classpath Execution Flag] - JVM Runtime Classpath Lookup",
            "desc": "When launching the compiled application via `java -cp bin chess.chess`, what does -cp bin define?",
            "opts": [
                "A) Classpath lookup directory where JVM searches for compiled classes and resources.",
                "B) Compiler optimization flag.",
                "C) CPU core allocation limit.",
                "D) Copy file permission."
            ],
            "correct": 0,
            "explanation": "-cp (or -classpath) tells the Java Virtual Machine where to find compiled .class files and package resources at runtime."
        },
        {
            "title": "Q115 [Environment Variable Overrides] - System getenv Priority",
            "desc": "If .env file contains GROQ_API_KEY=xyz and OS environment has GROQ_API_KEY=abc, which value takes priority in AICoach.java?",
            "opts": [
                "A) System.getenv(\"GROQ_API_KEY\") (abc) because OS environment variables are checked prior to reading .env.",
                "B) .env file value (xyz).",
                "C) Random selection.",
                "D) Triggers compile error."
            ],
            "correct": 0,
            "explanation": "AICoach queries System.getenv() first. If present and non-empty, it uses that value immediately without opening .env."
        },

        # SECTION 10: SYSTEM DESIGN & MULTIPLAYER SCALING ARCHITECTURE
        {
            "title": "Q116 [System Design — Real-time Multiplayer] - Full-Duplex Low Latency Protocol",
            "desc": "If converting this desktop game into an online real-time web application, what protocol is best suited for bidirectional low-latency move transmission between players?",
            "opts": ["A) WebSockets (ws:// or wss://)", "B) HTTP GET Polling every 10 seconds", "C) SMTP Mail transfer", "D) FTP File Transfer"],
            "correct": 0,
            "explanation": "WebSockets provide persistent full-duplex TCP communication channels, allowing game servers to push opponent moves instantly with minimal latency (<10ms)."
        },
        {
            "title": "Q117 [System Design — Game State Representation] - FEN Notation Compression",
            "desc": "How should chess board state be transmitted over WebSocket frames between Client and Server?",
            "opts": [
                "A) Compact FEN (Forsyth-Edwards Notation) strings or PGN (Portable Game Notation) move strings.",
                "B) Sending full raw pixel screenshot buffers.",
                "C) Transmitting serialized Java BufferedImage byte streams.",
                "D) Sending raw SQL queries."
            ],
            "correct": 0,
            "explanation": "FEN strings represent complete board positions in ~80 characters of plain text, minimizing network payload bandwidth."
        },
        {
            "title": "Q118 [System Design — Server-Side Validation] - Authoritative Move Validation",
            "desc": "In a secure online multiplayer chess platform, where MUST move legality (King check, castling, en passant) be validated?",
            "opts": [
                "A) Strictly on the authoritative central backend server to prevent client-side cheat injection or modified code tampering.",
                "B) Exclusively in the user's browser via JavaScript.",
                "C) On the database indexer.",
                "D) Move validation is unnecessary online."
            ],
            "correct": 0,
            "explanation": "Never trust the client. A malicious user could hack client-side code to bypass move checks. Authoritative validation must run on the backend server."
        },
        {
            "title": "Q119 [System Design — Database Schema] - Relational Match Schema",
            "desc": "Which database model is best suited for storing user accounts, Elo ratings, match history, and PGN move records?",
            "opts": [
                "A) Relational Database (PostgreSQL / MySQL) with tables for users, matches, and moves.",
                "B) Raw text files on desktop.",
                "C) In-memory array list.",
                "D) DNS record TXT fields."
            ],
            "correct": 0,
            "explanation": "Relational databases ensure ACID compliance, structured indexing for user leaderboards, foreign key integrity, and transactional match records."
        },
        {
            "title": "Q120 [System Design — Matchmaking Queues] - Redis Sorted Sets Matchmaking",
            "desc": "What system component handles pairing active online players of similar Elo rating skills in real-time?",
            "opts": [
                "A) Matchmaking Service using Redis Sorted Sets (ZSET) or Queue workers.",
                "B) Static HTML files.",
                "C) Minimax search tree.",
                "D) Java Swing EDT."
            ],
            "correct": 0,
            "explanation": "In-memory data structures like Redis Sorted Sets allow instant ranking lookups and low-latency player matchmaking by rating range."
        },

        # SECTION 11: LLM SYSTEM ARCHITECTURE & AI TRADE-OFFS
        {
            "title": "Q121 [Cloud vs Local LLM Trade-off — Latency] - Cloud LPU vs Local Hardware",
            "desc": "How does cloud API inference (Groq) compare to local LLM inference (Ollama) in latency performance?",
            "opts": [
                "A) Groq cloud hardware (LPU accelerators) processes tokens at ultra-high speed (~0.15s), whereas local consumer GPUs/CPUs take 1-4 seconds per response.",
                "B) Ollama local runs 100x faster than cloud servers.",
                "C) Both have identical response latency.",
                "D) Cloud APIs always fail."
            ],
            "correct": 0,
            "explanation": "Cloud providers use dedicated high-bandwidth AI hardware (LPUs/GPUs), delivering sub-second response times compared to consumer hardware."
        },
        {
            "title": "Q122 [Cloud vs Local LLM Trade-off — Privacy & Cost] - Offline Zero-Cost Advantage",
            "desc": "What is the primary operational advantage of running Ollama locally over cloud LLM APIs?",
            "opts": [
                "A) $0 API cost and 100% data privacy (game prompts never leave the local machine).",
                "B) 10x higher parameter count.",
                "C) Infinite context length.",
                "D) Zero RAM usage."
            ],
            "correct": 0,
            "explanation": "Local models run entirely on user hardware, incurring zero third-party API billing costs and ensuring total privacy without internet dependency."
        },
        {
            "title": "Q123 [Model Quantization Concept] - 4-bit Weight Quantization",
            "desc": "Local Ollama runs models like qwen3:8b using 4-bit quantization (e.g. Q4_K_M). What does quantization accomplish?",
            "opts": [
                "A) Compresses 16-bit floating point model weights down to 4-bit representations, reducing VRAM/RAM footprint from ~16GB to ~5GB with minimal intelligence loss.",
                "B) Speeds up internet connection speed.",
                "C) Increases model parameter count.",
                "D) Converts Java code to C++."
            ],
            "correct": 0,
            "explanation": "Quantization maps model weights to lower-bit precision, dramatically cutting memory requirements and enabling large LLMs to run on consumer laptops."
        },
        {
            "title": "Q124 [Context Window Optimization] - Prompt Token Reduction",
            "desc": "Why is the move description passed to the LLM formatted as a short text string (e.g., \"White Knight moved to f3\")?",
            "opts": [
                "A) Minimizes prompt token count, decreasing LLM generation latency and reducing API token costs.",
                "B) Because LLMs cannot read chess board notation.",
                "C) Swing limits text length to 20 characters.",
                "D) To prevent SQL injection."
            ],
            "correct": 0,
            "explanation": "Concise, targeted prompts keep token processing minimal, leading to near-instant advice generation."
        },
        {
            "title": "Q125 [Streaming vs Non-Streaming LLM Responses] - Server-Sent Events Token Chunks",
            "desc": "In AICoach.java, stream: false is configured for Ollama JSON payloads. What would stream: true enable?",
            "opts": [
                "A) Server sends generated tokens incrementally via Server-Sent Events (SSE), allowing UI to stream text character-by-character as it is produced.",
                "B) Video streaming of chess games.",
                "C) Multi-player WebSocket streaming.",
                "D) Fast forward move playback."
            ],
            "correct": 0,
            "explanation": "Streaming delivers token chunks in real-time as the LLM generates them, providing an interactive typing effect on screen."
        },

        # SECTION 12: CLASSICAL AI VS MODERN CHESS ENGINES
        {
            "title": "Q126 [Board Representation — Objects vs Bitboards] - 64-bit Bitmask Performance",
            "desc": "This application uses ArrayList<Piece> object instances. What board representation do world-class engines like Stockfish use for maximum performance?",
            "opts": [
                "A) Bitboards (64-bit long integers representing piece locations as bitmasks).",
                "B) 3D Graphics textures.",
                "C) JSON strings.",
                "D) Linked lists of strings."
            ],
            "correct": 0,
            "explanation": "Bitboards map chess boards to 64-bit integers. Bitwise operations (AND, OR, XOR, bit shifts) execute move generation and attack ray calculation in single CPU instructions."
        },
        {
            "title": "Q127 [Engine Architecture — Minimax vs Neural Networks] - MCTS Deep Learning vs Heuristic Minimax",
            "desc": "How does this classical Minimax + PST engine differ from modern Deep Learning engines like AlphaZero or Stockfish NNUE?",
            "opts": [
                "A) Minimax relies on hand-crafted evaluation functions and explicit tree depth search, whereas AlphaZero uses Monte Carlo Tree Search (MCTS) with Deep Neural Networks trained via self-play.",
                "B) AlphaZero uses Java Swing.",
                "C) Minimax engines evaluate 1 billion positions per second on CPU.",
                "D) There is no functional difference."
            ],
            "correct": 0,
            "explanation": "Classical engines use hardcoded human heuristics and minimax trees, whereas neural engines evaluate positional quality through deep neural network inference."
        },
        {
            "title": "Q128 [Zobrist Hashing Concept] - XOR Position Hashing",
            "desc": "What is Zobrist Hashing used for in advanced chess engine implementation?",
            "opts": [
                "A) Generating unique 64-bit hash keys for board positions via bitwise XOR operations, enabling fast Transposition Table lookups and 3-fold repetition detection.",
                "B) Encrypting user passwords.",
                "C) Rendering piece sprites.",
                "D) Formatting PGN files."
            ],
            "correct": 0,
            "explanation": "Zobrist hashing assigns pseudo-random 64-bit numbers to piece-square combinations, allowing instant position hash updates via bitwise XOR."
        },
        {
            "title": "Q129 [Quiescence Search Concept] - Tactical Exchange Horizon Resolution",
            "desc": "What search enhancement extends Minimax tree evaluation beyond depth limit specifically for tactical capture sequences to eliminate the Horizon Effect?",
            "opts": [
                "A) Quiescence Search (evaluating only quiet, non-capture positions before returning static score).",
                "B) Depth resetting.",
                "C) Random move selection.",
                "D) Piece deletion."
            ],
            "correct": 0,
            "explanation": "Quiescence Search continues evaluating tactical captures until a 'quiet' board state is reached, ensuring search depth doesn't terminate mid-tactical exchange."
        },
        {
            "title": "Q130 [Iterative Deepening Concept] - Progressive Search Horizon Management",
            "desc": "How does Iterative Deepening improve Minimax engine search management?",
            "opts": [
                "A) Runs Minimax progressively at Depth 1, then Depth 2, Depth 3, etc., allowing time-bounded engines to return the best move found from the deepest completed iteration.",
                "B) Repeats move generation 100 times.",
                "C) Increases piece movement speed.",
                "D) Clears RAM memory."
            ],
            "correct": 0,
            "explanation": "Iterative Deepening guarantees that if search time runs out mid-way through depth 6, the complete best move result from depth 5 is returned instantly."
        },

        # SECTION 13: PROJECT PITCH, BEHAVIORAL & TECHNICAL TRADE-OFFS
        {
            "title": "Q131 [Project Technology Selection] - Technical Desktop Justification",
            "desc": "In a technical interview, how should you justify choosing Java Swing over web technologies (React/Node) for this project?",
            "opts": [
                "A) 'Java Swing provides direct native JVM desktop execution, low memory overhead, standalone desktop deployment without browser engine overhead, and straightforward multithreading concurrency primitives.'",
                "B) 'Web technologies do not support chess games.'",
                "C) 'Java Swing is the newest UI framework available.'",
                "D) 'Swing handles AI search automatically.'"
            ],
            "correct": 0,
            "explanation": "A strong technical pitch highlights JVM performance, zero external framework overhead, multi-threading controls, and self-contained desktop deployment."
        },
        {
            "title": "Q132 [Technical Challenge Handling] - Speculative Simulation Engineering",
            "desc": "If asked about the hardest technical challenge faced during development, which aspect of the codebase represents the most complex engineering achievement?",
            "opts": [
                "A) 'Implementing check safety move validation during move generation, preventing illegal moves by speculatively simulating candidate moves on cloned board states and verifying King safety.'",
                "B) Loading PNG images.",
                "C) Setting window titles.",
                "D) Changing background colors."
            ],
            "correct": 0,
            "explanation": "Speculative move simulation, move rollback integrity, and non-blocking check verification form the most mathematically intricate logic in the game engine."
        },
        {
            "title": "Q133 [Performance Profiling & Bottlenecks] - Allocations Profiling & Bitboard Optimization",
            "desc": "If AI search at Depth 6 causes UI stutter, what profiling tool and optimization strategy would you explain to an interviewer?",
            "opts": [
                "A) 'Use Java VisualVM / JProfiler to trace garbage collection allocations; optimize by replacing object allocations with primitive array bitboards and in-place move mutation.'",
                "B) Re-install Windows.",
                "C) Add more Thread.sleep() calls.",
                "D) Reduce screen resolution."
            ],
            "correct": 0,
            "explanation": "Profiling tools (VisualVM, JProfiler) pinpoint CPU hot spots and memory allocation churn, guiding low-level algorithmic optimizations."
        },
        {
            "title": "Q134 [Feature Extensibility] - SOLID Open/Closed Principle",
            "desc": "How does the abstract base class design (Piece.java) satisfy the Open/Closed Principle (Solid Principles)?",
            "opts": [
                "A) Code is Open for extension (new custom fairy chess pieces like 'Archbishop' can be added by extending Piece) and Closed for modification (existing piece classes remain untouched).",
                "B) Code requires editing base Piece class for every edit.",
                "C) Code disables subclassing.",
                "D) Code uses public global variables everywhere."
            ],
            "correct": 0,
            "explanation": "Extending Piece allows adding brand new piece movement behaviors without altering or risking breaking existing piece implementations."
        },
        {
            "title": "Q135 [Core Personal Takeaway] - Decoupled Architecture Lesson",
            "desc": "What is the single most important system architectural lesson learned from building this end-to-end Chess & AI Engine project?",
            "opts": [
                "A) Decoupling core domain logic (move generator, evaluator, game rules) from UI rendering and background AI processing enables clean, maintainable, and extensible software architecture.",
                "B) Monolithic single-file applications run faster.",
                "C) Threading is unnecessary in game development.",
                "D) LLMs can replace all chess rules engines."
            ],
            "correct": 0,
            "explanation": "Separating rendering, business logic, graph pathfinding, and AI models adheres to separation of concerns, delivering clean maintainable architecture."
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
            "explanation": t["explanation"],
            "difficulty": "Medium",
            "is_placement": True,
            "created_at": datetime.now(timezone.utc).isoformat()
        })

    if items_to_add:
        col.insert_many(items_to_add)
        print(f"[questions] Seeded {len(items_to_add)} Chess AI & Application MCQs into MongoDB.")


def _seed_placement_coding(count: int):
    """Seed placement coding questions if fewer than 3 exist in DB."""
    col = _get_col()
    problems = [
        {
            "title": "Palindrome Check",
            "description": (
                "### Problem Statement\n"
                "Given a string `s`, determine if it is a palindrome considering only alphanumeric characters and ignoring cases.\n\n"
                "### Input Format\n"
                "A single string `s`.\n\n"
                "### Output Format\n"
                "Print `true` if it is a palindrome, otherwise print `false`.\n\n"
                "### Example 1\n"
                "**Input:** `racecar`  \n"
                "**Output:** `true`"
            ),
            "input_format": "A single string s",
            "output_format": "Print 'true' if palindrome, else 'false'",
            "examples": [{"input": "racecar", "output": "true"}, {"input": "hello", "output": "false"}],
            "test_cases": [{"input": "racecar", "expected": "true"}, {"input": "hello", "expected": "false"}, {"input": "AmanaplanacanalPanama", "expected": "true"}],
            "difficulty": "Easy"
        },
        {
            "title": "Find Missing Number",
            "description": (
                "### Problem Statement\n"
                "Given an array containing `n` distinct numbers taken from `0, 1, 2, ..., n`, find the single missing number in the sequence.\n\n"
                "### Input Format\n"
                "Space-separated integers representing the array.\n\n"
                "### Output Format\n"
                "Print the single missing integer.\n\n"
                "### Example 1\n"
                "**Input:** `3 0 1`  \n"
                "**Output:** `2`  \n"
                "**Explanation:** n = 3 since there are 3 numbers. The range is [0, 3]. 2 is the missing number."
            ),
            "input_format": "Space-separated integers",
            "output_format": "The missing integer",
            "examples": [{"input": "3 0 1", "output": "2"}],
            "test_cases": [{"input": "3 0 1", "expected": "2"}, {"input": "0 1 2 4 5", "expected": "3"}],
            "difficulty": "Medium"
        },
        {
            "title": "Maximum Subarray Sum",
            "description": (
                "### Problem Statement\n"
                "Given an integer array `nums`, find the contiguous subarray (containing at least one number) which has the largest sum and print its sum.\n\n"
                "### Input Format\n"
                "Space-separated integers representing array `nums`.\n\n"
                "### Output Format\n"
                "Print the maximum subarray sum integer.\n\n"
                "### Example 1\n"
                "**Input:** `-2 1 -3 4 -1 2 1 -5 4`  \n"
                "**Output:** `6`  \n"
                "**Explanation:** Subarray `[4, -1, 2, 1]` has the largest sum = `6`."
            ),
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

