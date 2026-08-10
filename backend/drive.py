"""
drive.py — Google Drive / Docs integration
Creates a Google Doc per submission inside Drive folder: Submissions/<QuestionTitle>/
"""

import os
import re
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
DRIVE_FOLDER_NAME = os.getenv("DRIVE_FOLDER_NAME", "Submissions")

# Lazy-loaded service objects
_drive_service = None
_docs_service  = None


def _get_services():
    """Initialise Google API services (lazy, cached)."""
    global _drive_service, _docs_service

    if _drive_service and _docs_service:
        return _drive_service, _docs_service

    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        scopes = [
            "https://www.googleapis.com/auth/drive",
            "https://www.googleapis.com/auth/documents",
        ]

        if not os.path.exists(CREDENTIALS_PATH):
            raise FileNotFoundError(
                f"credentials.json not found at '{CREDENTIALS_PATH}'. "
                "Follow setup_instructions.md to create a service account."
            )

        creds = service_account.Credentials.from_service_account_file(
            CREDENTIALS_PATH, scopes=scopes
        )
        _drive_service = build("drive", "v3", credentials=creds)
        _docs_service  = build("docs", "v1", credentials=creds)
        return _drive_service, _docs_service

    except ImportError:
        raise RuntimeError(
            "Google API libraries not installed. Run: pip install -r requirements.txt"
        )


def _find_or_create_folder(drive, name: str, parent_id: str | None = None) -> str:
    """Find a Drive folder by name (optionally under parent), or create it."""
    query = (
        f"mimeType='application/vnd.google-apps.folder' "
        f"and name='{name}' and trashed=false"
    )
    if parent_id:
        query += f" and '{parent_id}' in parents"

    results = drive.files().list(
        q=query, fields="files(id, name)", pageSize=1
    ).execute()
    files = results.get("files", [])

    if files:
        return files[0]["id"]

    # Create folder
    meta = {
        "name":     name,
        "mimeType": "application/vnd.google-apps.folder",
    }
    if parent_id:
        meta["parents"] = [parent_id]

    folder = drive.files().create(body=meta, fields="id").execute()
    return folder["id"]


def _safe_name(text: str) -> str:
    """Sanitise text for use in file/folder names."""
    return re.sub(r"[^\w\s\-]", "", text).strip()[:50]


def create_submission_doc(
    username: str,
    question_title: str,
    language: str,
    code: str,
    test_results: list[dict],
    overall_status: str,
    timestamp: str | None = None,
) -> dict:
    """
    Create a Google Doc for a submission.

    Returns:
        { "doc_id": str, "url": str, "file_name": str } on success
        { "error": str } on failure
    """
    if timestamp is None:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    safe_user = _safe_name(username)
    safe_q    = _safe_name(question_title)
    file_name = f"{safe_user}_{safe_q}_{timestamp}"

    try:
        drive, docs = _get_services()

        # Ensure Submissions/<QuestionTitle>/ folder exists
        root_id = _find_or_create_folder(drive, DRIVE_FOLDER_NAME)
        sub_id  = _find_or_create_folder(drive, safe_q, parent_id=root_id)

        # Create an empty Google Doc in that folder
        doc_meta = {
            "name":    file_name,
            "parents": [sub_id],
            "mimeType": "application/vnd.google-apps.document",
        }
        doc_file = drive.files().create(body=doc_meta, fields="id").execute()
        doc_id = doc_file["id"]

        # Build notebook-style document content
        requests_body = _build_doc_requests(
            username=username,
            question_title=question_title,
            language=language,
            code=code,
            test_results=test_results,
            overall_status=overall_status,
            timestamp=timestamp,
        )

        docs.documents().batchUpdate(
            documentId=doc_id,
            body={"requests": requests_body}
        ).execute()

        url = f"https://docs.google.com/document/d/{doc_id}/edit"
        return {"doc_id": doc_id, "url": url, "file_name": file_name}

    except FileNotFoundError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": f"Google Drive error: {str(e)}"}


def _build_doc_requests(
    username, question_title, language, code,
    test_results, overall_status, timestamp
) -> list[dict]:
    """
    Build the list of Google Docs API batchUpdate requests that populate
    the document with notebook-style content.
    """
    lines = []

    lines.append(("TITLE",  f"Submission — {question_title}"))
    lines.append(("BLANK",  ""))
    lines.append(("HEADING", "📋 Submission Info"))
    lines.append(("KV",     f"Name: {username}"))
    lines.append(("KV",     f"Question: {question_title}"))
    lines.append(("KV",     f"Language: {language.capitalize()}"))
    lines.append(("KV",     f"Status: {overall_status}"))
    lines.append(("KV",     f"Time: {timestamp}"))
    lines.append(("BLANK",  ""))
    lines.append(("HEADING", "💻 Code"))
    lines.append(("CODE",   code))
    lines.append(("BLANK",  ""))
    lines.append(("HEADING", "🧪 Test Case Results"))

    for i, tc in enumerate(test_results, 1):
        icon = "✅" if tc.get("passed") else "❌"
        lines.append(("SUB",  f"{icon} Test Case {i}"))
        lines.append(("KV",   f"  Input:    {tc.get('input', '')}"))
        lines.append(("KV",   f"  Expected: {tc.get('expected', '')}"))
        lines.append(("KV",   f"  Got:      {tc.get('got', '')}"))
        lines.append(("BLANK", ""))

    # Build text and track insert positions
    full_text = ""
    segments = []  # (start, end, style, raw_line)

    for style, text in lines:
        start = len(full_text)
        content = text + "\n"
        full_text += content
        segments.append((start + 1, start + 1 + len(content), style, text))

    # Insert all text at once (index 1 = start of doc)
    requests = [
        {
            "insertText": {
                "location": {"index": 1},
                "text": full_text,
            }
        }
    ]

    # Apply paragraph styles
    for start, end, style, text in segments:
        if style == "TITLE":
            requests.append({
                "updateParagraphStyle": {
                    "range": {"startIndex": start, "endIndex": end},
                    "paragraphStyle": {"namedStyleType": "TITLE"},
                    "fields": "namedStyleType",
                }
            })
        elif style == "HEADING":
            requests.append({
                "updateParagraphStyle": {
                    "range": {"startIndex": start, "endIndex": end},
                    "paragraphStyle": {"namedStyleType": "HEADING_2"},
                    "fields": "namedStyleType",
                }
            })
        elif style == "CODE":
            requests.append({
                "updateTextStyle": {
                    "range": {"startIndex": start, "endIndex": end},
                    "textStyle": {
                        "weightedFontFamily": {
                            "fontFamily": "Courier New",
                            "weight": 400,
                        },
                        "fontSize": {"magnitude": 10, "unit": "PT"},
                    },
                    "fields": "weightedFontFamily,fontSize",
                }
            })
        elif style == "SUB":
            requests.append({
                "updateParagraphStyle": {
                    "range": {"startIndex": start, "endIndex": end},
                    "paragraphStyle": {"namedStyleType": "HEADING_3"},
                    "fields": "namedStyleType",
                }
            })

    return requests
