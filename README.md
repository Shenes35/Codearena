# ⚡ CodeArena — Mini Coding Platform

A full-stack web coding platform where admins create problems and users write, run, and submit code — with submissions saved as Google Docs.

## Features
- **Problem List** — card grid with difficulty filters and search
- **Monaco Editor** — VS Code-grade editing experience
- **Run Code** — powered by Judge0 CE (supports Python, JS, C++, Java, C)
- **Submit** — runs all hidden test cases; submit only if all pass
- **Google Drive** — each accepted submission creates a notebook-style Google Doc
- **Admin Panel** — password-protected; create/delete problems with test cases
- **Timer** — per-problem countdown

## Project Structure
```
question-solver/
├── frontend/          # Static HTML/CSS/JS (deployable to Netlify/Vercel)
│   ├── index.html
│   ├── editor.html
│   ├── admin.html
│   ├── css/style.css
│   └── js/{main,editor,admin}.js
└── backend/           # Flask API (deployable to Render)
    ├── app.py
    ├── judge0.py
    ├── drive.py
    ├── questions.py
    ├── questions.json
    └── requirements.txt
```

## Quick Start
See [setup_instructions.md](setup_instructions.md) for detailed steps.

```bash
# 1. Backend
cd backend
cp .env.example .env    # fill in your keys
pip install -r requirements.txt
python app.py

# 2. Frontend — open in browser
open frontend/index.html   # or use Live Server in VS Code
```

## Default Admin Password
`admin123` (change via `ADMIN_PASSWORD` in your `.env`)

## License
MIT
