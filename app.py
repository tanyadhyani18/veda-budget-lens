"""
app.py - Flask web server for the Marketing Budget Variance Desk.

Routes
  GET  /               the web page
  GET  /api/health     shows whether the AI key is configured
  POST /api/analyze    upload a file (or use the sample) -> validated variance analysis
  POST /api/commentary generate AI (or rules-based) commentary for an analysis
"""
import io
import os
import threading
import time
import uuid
from collections import OrderedDict

import pandas as pd
from flask import Flask, jsonify, render_template, request

import ai_commentary
import variance

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SAMPLE_PATH = os.path.join(BASE_DIR, "sample_data", "veda_naturals_marketing_budget_sample.csv")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024     # 2 MB upload limit

# Short-lived server-side memory of analyses, so the AI step uses the numbers the
# server calculated (not numbers sent back by the browser). Lost on restart.
_STORE = OrderedDict()
_STORE_LOCK = threading.Lock()
STORE_TTL, STORE_MAX = 3600, 100


def _store_put(analysis):
    analysis_id = uuid.uuid4().hex
    with _STORE_LOCK:
        _STORE[analysis_id] = (time.time(), analysis)
        while len(_STORE) > STORE_MAX:
            _STORE.popitem(last=False)
    return analysis_id


def _store_get(analysis_id):
    with _STORE_LOCK:
        item = _STORE.get(analysis_id)
        if item and time.time() - item[0] < STORE_TTL:
            return item[1]
        _STORE.pop(analysis_id, None)
    return None


def _error(message, status, **extra):
    return jsonify({"ok": False, "error": message, **extra}), status


def _client_ip():
    forwarded = request.headers.get("X-Forwarded-For", "")
    return forwarded.split(",")[0].strip() or request.remote_addr or "unknown"


def _read_table(file_storage):
    """Read an uploaded CSV or XLSX into a DataFrame of raw (unparsed) cells."""
    name = (file_storage.filename or "").lower()
    raw = file_storage.read()
    if name.endswith(".csv"):
        for encoding in ("utf-8-sig", "latin-1"):
            try:
                text = raw.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        return pd.read_csv(io.StringIO(text), dtype=object)
    if name.endswith(".xlsx"):
        return pd.read_excel(io.BytesIO(raw), dtype=object, engine="openpyxl")
    raise ValueError("Please upload a .csv or .xlsx file.")


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/health")
def health():
    return jsonify({"status": "ok",
                    "ai_configured": bool(os.environ.get("GEMINI_API_KEY", "").strip()),
                    "model": ai_commentary.PRIMARY_MODEL})


@app.post("/api/analyze")
def analyze():
    try:
        tolerance = float(request.form.get("tolerance", "5"))
    except ValueError:
        return _error("Tolerance must be a number between 0 and 100.", 400)
    if not 0 <= tolerance <= 100 or tolerance != tolerance:
        return _error("Tolerance must be a number between 0 and 100.", 400)

    try:
        if request.form.get("use_sample") == "true":
            df = pd.read_csv(SAMPLE_PATH, dtype=object)
        else:
            file = request.files.get("file")
            if file is None or not file.filename:
                return _error("Please choose a .csv or .xlsx file first.", 400)
            df = _read_table(file)
    except ValueError as err:
        return _error(str(err), 400)
    except pd.errors.EmptyDataError:
        return _error("The file is empty.", 422)
    except Exception:
        return _error("The file could not be read. Please upload a valid .csv or .xlsx file.", 422)

    try:
        analysis = variance.analyse(df, tolerance)
    except variance.AnalysisError as err:
        return _error(str(err), 422, rejected=err.rejected)

    analysis["analysis_id"] = _store_put(analysis)
    return jsonify({"ok": True, **analysis})


@app.post("/api/commentary")
def commentary():
    data = request.get_json(silent=True) or {}
    rank_by = data.get("rank_by", "amount")
    if rank_by not in ("amount", "pct"):
        return _error("rank_by must be 'amount' or 'pct'.", 400)
    analysis = _store_get(str(data.get("analysis_id", "")))
    if analysis is None:
        return _error("This analysis has expired. Please upload the file again.", 410)
    result = ai_commentary.get_commentary(analysis, rank_by, _client_ip(),
                                          bool(data.get("simulate_outage")))
    return jsonify({"ok": True, **result})


@app.errorhandler(413)
def too_large(_):
    return _error("The file is larger than the 2 MB limit.", 413)


@app.errorhandler(404)
def not_found(_):
    return _error("Not found.", 404) if request.path.startswith("/api/") else ("Page not found", 404)


@app.errorhandler(405)
def bad_method(_):
    return _error("Method not allowed.", 405)


@app.errorhandler(500)
def server_error(_):
    return _error("Something went wrong on the server. Please try again.", 500)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 5000)), debug=False)
