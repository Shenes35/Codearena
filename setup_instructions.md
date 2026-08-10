# Setup Instructions — CodeArena

---

## 1. Prerequisites

- Python 3.10+
- A free [RapidAPI](https://rapidapi.com) account
- A free [Google Cloud](https://console.cloud.google.com) account (for Drive integration)

---

## 2. Backend Setup

### 2a. Install Python dependencies

```powershell
cd backend
pip install -r requirements.txt
```

### 2b. Configure environment variables

```powershell
Copy-Item .env.example .env
```

Open `.env` and fill in:

| Variable | Where to get it |
|---|---|
| `JUDGE0_API_KEY` | See step 3 below |
| `GOOGLE_CREDENTIALS_PATH` | See step 4 below |
| `ADMIN_PASSWORD` | Choose any password |
| `FLASK_SECRET_KEY` | Any random string |

### 2c. Run the backend

```powershell
python app.py
```

Backend runs at: `http://localhost:5000`

---

## 3. Judge0 API Setup (Free)

1. Go to [https://rapidapi.com/judge0-official/api/judge0-ce](https://rapidapi.com/judge0-official/api/judge0-ce)
2. Create a free RapidAPI account (if you don't have one)
3. Click **Subscribe to Test** → choose the **Basic plan (free)**
4. Copy your **X-RapidAPI-Key** from the header section
5. Paste it as `JUDGE0_API_KEY` in your `.env`

> ⚠️ The free tier allows **50 requests/day**. For more, upgrade or self-host Judge0.

---

## 4. Google Drive Integration Setup

### Step 1: Create a GCP project

1. Go to [https://console.cloud.google.com](https://console.cloud.google.com)
2. Click **New Project** → name it `codearena`

### Step 2: Enable APIs

In the GCP Console, search and enable:
- **Google Drive API**
- **Google Docs API**

### Step 3: Create a Service Account

1. Go to **IAM & Admin → Service Accounts**
2. Click **+ Create Service Account**
3. Name: `codearena-drive`, click **Create and Continue**
4. Skip role selection → **Done**
5. Click the service account → **Keys tab** → **Add Key → JSON**
6. Download the JSON file

### Step 4: Place credentials

```powershell
Copy-Item path\to\downloaded.json backend\credentials.json
```

Set `GOOGLE_CREDENTIALS_PATH=credentials.json` in `.env`

### Step 5: Share a Drive folder with the service account

1. In Google Drive, create a folder called **Submissions**
2. Right-click → **Share**
3. Add the service account email (from the JSON file, field `client_email`)
4. Give it **Editor** permissions

> The backend will automatically create subfolders inside **Submissions** per question.

---

## 5. Frontend Setup

The frontend is pure HTML/JS — no build step needed.

### Local development

Open `frontend/index.html` directly in your browser, or use VS Code Live Server.

> Make sure `API_BASE` in each JS file points to `http://localhost:5000`.

---

## 6. Deployment

### Backend → Render (Free)

1. Push your project to GitHub (do NOT commit `.env` or `credentials.json`)
2. Go to [https://render.com](https://render.com) → **New Web Service**
3. Connect your GitHub repo
4. Settings:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python app.py`
   - **Environment**: Python 3
5. Add environment variables in Render dashboard (same as your `.env`)
6. For `credentials.json`, paste the JSON content as an env var `GOOGLE_CREDENTIALS_JSON`, then update `drive.py` to parse it from env

### Frontend → Netlify (Free)

1. Go to [https://netlify.com](https://netlify.com) → **Add new site → Deploy manually**
2. Drag & drop the `frontend/` folder
3. Update `API_BASE` in all JS files to your Render backend URL (e.g. `https://codearena-api.onrender.com`)
4. Redeploy

---

## 7. Deploying credentials.json on Render

Since you can't upload files directly, use this pattern in `drive.py`:

```python
import os, json, tempfile

creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
if creds_json:
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    json.dump(json.loads(creds_json), tmp)
    tmp.close()
    CREDENTIALS_PATH = tmp.name
```

In Render's environment, set `GOOGLE_CREDENTIALS_JSON` to the entire contents of your `credentials.json`.

---

## 8. Testing the full flow

1. Open `http://localhost:5000` → should return `{"status":"ok",...}`
2. Open `frontend/index.html` → questions should load
3. Click a question → editor opens
4. Write a solution, click **Run** → output appears in console
5. Click **Submit** → test cases run; if all pass, success overlay appears
6. Check Google Drive → `Submissions/<QuestionTitle>/` should contain a new Doc

---

## 9. Changing the Admin Password

Edit `ADMIN_PASSWORD` in your `.env` and restart the Flask server. Default is `admin123`.

---

## 10. Troubleshooting

| Problem | Fix |
|---|---|
| `JUDGE0_API_KEY not configured` | Add it to `.env` |
| `credentials.json not found` | Ensure the file is in `backend/` |
| CORS errors in browser | Ensure Flask is running and `CORS(app)` is active |
| Monaco editor blank | Check browser console; CDN may be blocked |
| Drive: `403 forbidden` | Share the Drive folder with the service account email |
