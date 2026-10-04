# Veda Budget Lens

An AI-assisted web app for **Use Case 8 - Budget variance analyzer** (AI for Managers, End-Term Project).
A marketing team uploads planned vs. actual spend; the app calculates every variance, flags the **top 3 outlier
line items**, and uses Google Gemini to write a plain-English **variance commentary**.

*All sample data is synthetic (fictional company "Veda Naturals").*

## How it works (one paragraph)
`variance.py` validates the file and calculates all numbers (no AI). `ai_commentary.py` sends only those
calculated figures to Gemini and checks the answer; if Gemini is unavailable it falls back to a rules-based
summary. `app.py` is the Flask web server; `templates/` and `static/` are the web page.

## Folder structure
```
marketing-variance-desk/
  app.py               web server
  variance.py          validation + calculations (no AI)
  ai_commentary.py     Gemini call, guardrails, fallback
  requirements.txt     Python packages
  gunicorn.conf.py     server settings (1 worker, 4 threads, 120 s timeout)
  .python-version      Python 3.12.3 (used by Render)
  templates/index.html web page
  static/style.css     styling
  static/app.js        browser logic
  sample_data/         demo files (30-line sample as CSV and XLSX, plus two test files)
  tests/test_app.py    29 automated tests
```

## Run on your own computer
1. Install Python 3.12 from python.org (tick "Add Python to PATH" on Windows).
2. Open a terminal in this folder and run:
   - Windows: `python -m venv .venv` then `.venv\Scripts\activate`
   - Mac/Linux: `python3 -m venv .venv` then `source .venv/bin/activate`
3. `pip install -r requirements.txt`
4. (Optional, for AI commentary) get a free key at https://aistudio.google.com/apikey and set it:
   - Windows (PowerShell): `$env:GEMINI_API_KEY="your-key"`
   - Mac/Linux: `export GEMINI_API_KEY="your-key"`
5. `python app.py` and open http://127.0.0.1:5000

Without a key the app still works and shows the rules-based summary.

## Run the tests
`pip install pytest` then `python -m pytest -q` (Gemini is never called during tests).

## Deploy for free on Render (public link)
1. Create a GitHub repository and upload all files in this folder (not the folder itself).
2. At https://render.com sign up (no card needed) and choose **New > Web Service** > connect the repository.
3. Settings:
   - Runtime: **Python 3**
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn app:app` (settings are read from `gunicorn.conf.py`)
   - Instance Type: **Free**
4. Under **Environment** add:
   - `GEMINI_API_KEY` = your key (keep it secret; never put it in GitHub)
   - `PYTHON_VERSION` = `3.12.3`
5. Click **Create Web Service**. After the build, your link looks like `https://your-name.onrender.com`.

Optional settings (Environment): `GEMINI_MODEL` (default `gemini-3.5-flash-lite`), `GEMINI_FALLBACK_MODEL`
(default `gemini-3.1-flash-lite`), `AI_HOURLY_LIMIT` (default 12 per visitor), `AI_DAILY_CAP` (default 300 total).

**Why one worker?** Short-lived analysis memory and the usage limits live in the server's memory, so the app uses
a single worker with several threads.

## Troubleshooting
| Problem | Fix |
|---|---|
| First visit takes about a minute | Render's free service sleeps after 15 minutes idle. Open the link a few minutes before a demo. |
| "AI commentary is not configured" | `GEMINI_API_KEY` is missing in Render > Environment. |
| "rejected the API key" | Key is wrong or expired. Create a new one and update it in Render. |
| "model is not available" | Set `GEMINI_MODEL` to a current Gemini Flash-Lite model name. |
| "rate limit reached" | Free-tier limit. Wait a minute; the rules-based summary still works. |
| Build fails on Render | Check `PYTHON_VERSION` is `3.12.3` and `requirements.txt` is in the repository root. |
| `ModuleNotFoundError` locally | Activate the virtual environment, then `pip install -r requirements.txt`. |
| "This analysis has expired" | The server restarted or an hour passed. Upload the file again. |

## Privacy
Calculations run on the server and nothing is stored. Commentary requests send line-item names and calculated
figures to Google's Gemini API. On Google's free tier, content may be used to improve Google's products, so use
**synthetic or consented data only**.
