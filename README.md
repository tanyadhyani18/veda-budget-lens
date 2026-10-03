# Veda Naturals Budget Lens

A Flask-based budget variance analyzer for Use Case 8. The app uses Tanya's supplied Claude sample workbook/CSV as the source dataset and preserves all six source columns, including `Period`.

## Features
- CSV and Excel upload with required-column, numeric, non-negative, nonzero-budget and unique-ID validation
- Budget, actual, variance (actual minus budget), and variance percentage calculations
- Top outliers ranked by absolute rupee or percentage variance
- Category-level variance visualization and management commentary
- Download original sample CSV and calculated variance CSV
- Responsive custom HTML/CSS interface (not Streamlit)

## Run locally
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python app.py
```
Open http://127.0.0.1:5000.

## Deployment
Push this folder to GitHub and create a Render Web Service using the included `render.yaml`. Public deployment requires your own accounts and approval; it has not been deployed from this workspace.

## AI and limitations
The current commentary is deterministic/rule-generated, not a live Gemini call. It summarizes computed values and deliberately avoids inventing causes or ROI. For a live model, add a server-side API key, disclose third-party processing, validate model output against computed figures, and keep API keys out of source control.

## Dataset note
The provided data is illustrative/synthetic for the project; it is not verified company financial data.
