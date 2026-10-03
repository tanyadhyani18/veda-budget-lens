import io, os
import pandas as pd
from flask import Flask, render_template, request, send_file
app = Flask(__name__)
BASE = os.path.dirname(__file__)
SAMPLE = os.path.join(BASE, "veda_naturals_marketing_budget.csv")
REQUIRED = ["Line_ID", "Period", "Category", "Line_Item", "Budget_INR", "Actual_INR"]

def analyze(raw):
    missing = [c for c in REQUIRED if c not in raw.columns]
    if missing: raise ValueError("Missing required columns: " + ", ".join(missing))
    d = raw[REQUIRED].copy()
    for c in ["Budget_INR", "Actual_INR"]:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    if d[REQUIRED].isna().any().any(): raise ValueError("Required fields contain blank or non-numeric values.")
    if (d[["Budget_INR", "Actual_INR"]] < 0).any().any(): raise ValueError("Budget and actual amounts must be non-negative.")
    if d["Line_ID"].duplicated().any(): raise ValueError("Duplicate Line_ID values found; each line must be unique.")
    if (d["Budget_INR"] == 0).any(): raise ValueError("Budget must be greater than zero to calculate variance percentage.")
    d["Variance_INR"] = d["Actual_INR"] - d["Budget_INR"]
    d["Variance_Pct"] = (d["Variance_INR"] / d["Budget_INR"] * 100).round(2)
    d["Status"] = d["Variance_INR"].apply(lambda x: "Over budget" if x > 0 else ("Under budget" if x < 0 else "On budget"))
    return d

def money(x): return f"₹{x:,.0f}"
def build_view(d, mode):
    budget=float(d.Budget_INR.sum()); actual=float(d.Actual_INR.sum()); variance=actual-budget
    summary={"budget":budget,"actual":actual,"variance":variance,"pct":variance/budget*100 if budget else 0,
      "over":int((d.Variance_INR>0).sum()),"under":int((d.Variance_INR<0).sum()),"on":int((d.Variance_INR==0).sum()),"count":len(d)}
    cat=d.groupby("Category",as_index=False).agg(Budget_INR=("Budget_INR","sum"),Actual_INR=("Actual_INR","sum"))
    cat["Variance_INR"]=cat.Actual_INR-cat.Budget_INR
    cat=cat.sort_values("Variance_INR",key=lambda x:x.abs(),ascending=False)
    maxv=max(cat.Variance_INR.abs().max(),1)
    categories=[{"name":r.Category,"budget":money(r.Budget_INR),"actual":money(r.Actual_INR),"variance":money(r.Variance_INR),"positive":r.Variance_INR>=0,"width":abs(r.Variance_INR)/maxv*100} for r in cat.itertuples()]
    ranked=d.assign(_abs=d.Variance_INR.abs() if mode=="amount" else d.Variance_Pct.abs()).sort_values("_abs",ascending=False)
    rows=[]
    for r in ranked.itertuples(): rows.append({"id":r.Line_ID,"period":r.Period,"category":r.Category,"item":r.Line_Item,"budget":money(r.Budget_INR),"actual":money(r.Actual_INR),"variance":money(r.Variance_INR),"pct":f"{r.Variance_Pct:+.2f}%","status":r.Status})
    over=d[d.Variance_INR>0].nlargest(3,"Variance_INR")
    under=d[d.Variance_INR<0].nsmallest(3,"Variance_INR")
    insights=[f"Across {len(d)} records, actual spend was {money(actual)} against a budget of {money(budget)}: net {money(variance)} ({variance/budget*100:+.2f}%).",
      f"{summary['over']} line items exceeded budget, {summary['under']} were below budget, and {summary['on']} matched budget."]
    if len(over): insights.append("Largest overspends by rupee amount: "+", ".join(f"{r.Line_Item} ({money(r.Variance_INR)})" for r in over.itertuples())+".")
    if len(under): insights.append("Largest underspends by rupee amount: "+", ".join(f"{r.Line_Item} ({money(r.Variance_INR)})" for r in under.itertuples())+".")
    insights.append("Follow-up: confirm approval and business outcomes for overspends; check whether underspends reflect genuine savings, delayed activity, or incomplete execution. Spend variance alone cannot establish ROI.")
    fallback=" ".join(insights)
    api_key=os.getenv("GEMINI_API_KEY")
    if api_key:
        try:
            from google import genai
            client=genai.Client(api_key=api_key)
            prompt=("Act as a cautious marketing finance analyst. Using only these computed facts, write 3 concise, decision-useful observations and 2 follow-up questions. Do not recalculate, invent causes, claim ROI, or introduce facts not provided. Facts: "+fallback)
            response=client.models.generate_content(model=os.getenv("GEMINI_MODEL","gemini-2.5-flash"), contents=prompt)
            if response and response.text and response.text.strip(): fallback=response.text.strip()+"\n\nComputed figures above are the source of truth; validate explanations with budget owners."
        except Exception:
            pass  # safe deterministic fallback if the model is unavailable
    return summary,categories,rows,fallback

@app.route('/', methods=['GET','POST'])
def home():
    mode="amount"; error=None; summary=None; categories=[]; rows=[]; comment=None
    try:
        if request.method=="POST":
            mode=request.form.get("mode","amount")
            f=request.files.get("file")
            if f and f.filename:
                if f.filename.lower().endswith('.csv'): raw=pd.read_csv(f)
                elif f.filename.lower().endswith(('.xlsx','.xls')): raw=pd.read_excel(f)
                else: raise ValueError("Please upload a CSV or Excel workbook.")
            else: raw=pd.read_csv(SAMPLE)
        else: raw=pd.read_csv(SAMPLE)
        d=analyze(raw); summary,categories,rows,comment=build_view(d,mode)
    except Exception as e: error=str(e)
    return render_template('index.html',summary=summary,categories=categories,rows=rows,comment=comment,error=error,mode=mode)

@app.route('/download')
def download():
    d=analyze(pd.read_csv(SAMPLE)); out=io.BytesIO(); d.to_csv(out,index=False); out.seek(0)
    return send_file(out,mimetype='text/csv',as_attachment=True,download_name='veda_budget_variance_analysis.csv')

@app.route('/source')
def source_file(): return send_file(SAMPLE,mimetype='text/csv',as_attachment=True,download_name='veda_naturals_marketing_budget.csv')

if __name__=='__main__': app.run(host='0.0.0.0',port=int(os.environ.get('PORT',5000)))
