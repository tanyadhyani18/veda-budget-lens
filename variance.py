"""
variance.py - input validation and variance calculations.

This file contains NO AI. Every number the app shows is calculated here, so it
is always exact and can be checked by hand. All money values are in INR (rupees).
"""
import math
import re

import pandas as pd

MAX_ROWS = 500          # demo limit on line items per file
MAX_VALUE = 1e12        # anything larger is treated as a typing error
TEXT_LIMIT = 80         # maximum characters kept from a line-item / category name


class AnalysisError(Exception):
    """Raised when a file cannot be analysed. Carries rejected rows if any."""

    def __init__(self, message, rejected=None):
        super().__init__(message)
        self.rejected = rejected or []


# ---------------------------------------------------------------- column names
# Headers are matched ignoring case, spaces and punctuation, so "Budget (INR)",
# "budget_inr" and "BUDGET INR" are all accepted.
ALIASES = {
    "line_item": {"line_item", "lineitem", "item", "budget_line", "description", "line"},
    "budget_inr": {"budget_inr", "budget", "budget_rs", "budget_amount", "planned",
                   "planned_spend", "plan"},
    "actual_inr": {"actual_inr", "actual", "actual_rs", "actual_amount", "actual_spend",
                   "spend"},
    "category": {"category", "group", "head", "channel_group"},
    "line_id": {"line_id", "id"},
    "period": {"period", "quarter", "month"},
}
REQUIRED = {"line_item": "Line_Item", "budget_inr": "Budget_INR", "actual_inr": "Actual_INR"}
LOOKUP = {alias: canon for canon, names in ALIASES.items() for alias in names}


def _norm(header):
    return re.sub(r"[^a-z0-9]+", "_", str(header).lower()).strip("_")


def _standardise_columns(df):
    """Rename recognised columns to standard names. Returns (df, warnings)."""
    mapping, warnings, ignored = {}, [], []
    for col in df.columns:
        canon = LOOKUP.get(_norm(col))
        if canon is None:
            ignored.append(str(col))
        elif canon in mapping.values():
            warnings.append(f"Column '{col}' was ignored because another column already "
                            f"provides {REQUIRED.get(canon, canon)}.")
        else:
            mapping[col] = canon
    missing = [name for canon, name in REQUIRED.items() if canon not in mapping.values()]
    if missing:
        found = ", ".join(str(c) for c in df.columns) or "none"
        raise AnalysisError(
            f"The file is missing required column(s): {', '.join(missing)}. "
            f"Columns found: {found}.")
    if ignored:
        warnings.append("Unrecognised columns were ignored: " + ", ".join(ignored) + ".")
    return df.rename(columns=mapping)[list(mapping.values())], warnings


# ------------------------------------------------------------------ cell parsing
def _clean_text(value):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    text = re.sub(r"[\x00-\x1f\x7f]", " ", str(value))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:TEXT_LIMIT]


def _to_number(value):
    """Return a float, or raise ValueError with a short reason."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        raise ValueError("is blank")
    if isinstance(value, bool):
        raise ValueError("is not a number")
    if isinstance(value, (int, float)):
        number = float(value)
    else:
        text = str(value).strip()
        if text == "" or text.lower() in {"nan", "none", "null", "na", "n/a", "-"}:
            raise ValueError("is blank")
        cleaned = re.sub(r"[₹,\s]|\brs\.?|\binr\b", "", text, flags=re.I)
        try:
            number = float(cleaned)
        except ValueError:
            raise ValueError(f"is not a number ('{text[:20]}')") from None
    if math.isnan(number) or math.isinf(number):
        raise ValueError("is not a valid number")
    return number


# ----------------------------------------------------------------- formatting
def fmt_inr(amount, signed=False):
    """Indian digit grouping: 2400000 -> '₹24,00,000'."""
    sign = "-" if amount < 0 else ("+" if signed and amount > 0 else "")
    digits = str(int(round(abs(amount))))
    if len(digits) > 3:
        head, tail = digits[:-3], digits[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        digits = ",".join(parts + [tail])
    return f"{sign}₹{digits}"


def fmt_short(amount):
    """Readable size: 24091500 -> '₹2.41 crore', 492000 -> '₹4.92 lakh'."""
    size = abs(amount)
    sign = "-" if amount < 0 else ""
    if size >= 1e7:
        return f"{sign}₹{size / 1e7:.2f} crore"
    if size >= 1e5:
        return f"{sign}₹{size / 1e5:.2f} lakh"
    return fmt_inr(amount)


def fmt_pct(pct, signed=True):
    sign = "+" if signed and pct > 0 else ""
    return f"{sign}{pct:.1f}%"


# ---------------------------------------------------------------------- analysis
def analyse(df, tolerance_pct=5.0):
    """Validate the table, calculate variances and pick the top-3 outliers."""
    if df is None or df.empty:
        raise AnalysisError("The file has no data rows. Please add at least one line item.")
    if len(df) > MAX_ROWS:
        raise AnalysisError(f"The file has {len(df):,} rows. This demo accepts up to "
                            f"{MAX_ROWS} line items.")
    df, warnings = _standardise_columns(df)

    lines, rejected, seen = [], [], {}
    for position, row in enumerate(df.to_dict("records")):
        row_number = position + 2          # row 1 is the header in the user's file
        reasons = []
        name = _clean_text(row.get("line_item"))
        category = _clean_text(row.get("category")) or "Uncategorised"
        if not name:
            reasons.append("Line_Item is blank")

        budget = actual = None
        for field, label in (("budget_inr", "Budget_INR"), ("actual_inr", "Actual_INR")):
            try:
                number = _to_number(row.get(field))
                if number < 0:
                    reasons.append(f"{label} cannot be negative")
                elif number > MAX_VALUE:
                    reasons.append(f"{label} is unrealistically large")
                elif field == "budget_inr":
                    if number == 0:
                        reasons.append("Budget_INR must be greater than 0 "
                                       "(a % variance cannot be calculated)")
                    else:
                        budget = number
                else:
                    actual = number
            except ValueError as err:
                reasons.append(f"{label} {err}")

        key = (category.lower(), name.lower())
        if name and not reasons:
            if key in seen:
                reasons.append(f"Duplicate of row {seen[key]}")
            else:
                seen[key] = row_number

        if reasons:
            rejected.append({"row": row_number, "line_item": name or "(blank)",
                             "reasons": reasons})
            continue

        variance = actual - budget
        pct = variance / budget * 100
        status = "On budget" if abs(variance) < 0.5 else (
            "Over budget" if variance > 0 else "Under budget")
        lines.append({
            "idx": len(lines), "row": row_number,
            "line_id": _clean_text(row.get("line_id")),
            "period": _clean_text(row.get("period")),
            "category": category, "line_item": name,
            "budget": round(budget, 2), "actual": round(actual, 2),
            "variance": round(variance, 2), "pct": round(pct, 2),
            "status": status, "outside_tolerance": abs(pct) > tolerance_pct,
        })

    if not lines:
        raise AnalysisError("No valid rows were found, so nothing could be analysed.", rejected)

    total_budget = sum(l["budget"] for l in lines)
    total_actual = sum(l["actual"] for l in lines)
    total_var = total_actual - total_budget
    periods = sorted({l["period"] for l in lines if l["period"]})

    summary = {
        "n_lines": len(lines),
        "total_budget": round(total_budget, 2),
        "total_actual": round(total_actual, 2),
        "total_variance": round(total_var, 2),
        "total_pct": round(total_var / total_budget * 100, 2),
        "n_over": sum(l["status"] == "Over budget" for l in lines),
        "n_under": sum(l["status"] == "Under budget" for l in lines),
        "n_on": sum(l["status"] == "On budget" for l in lines),
        "n_outside": sum(l["outside_tolerance"] for l in lines),
        "tolerance_pct": tolerance_pct,
        "period": ", ".join(periods) if periods else "not stated",
    }

    # Top-3 outliers. The Excel does not define "outlier"; this app ranks by the
    # size of the gap, either in rupees (default) or in % of budget.
    moved = [l for l in lines if l["status"] != "On budget"]
    by_amount = sorted(moved, key=lambda l: (-abs(l["variance"]), -abs(l["pct"]), l["line_item"]))
    by_pct = sorted(moved, key=lambda l: (-abs(l["pct"]), -abs(l["variance"]), l["line_item"]))

    cats = {}
    for l in lines:
        c = cats.setdefault(l["category"], {"category": l["category"], "budget": 0.0,
                                            "actual": 0.0, "n_lines": 0})
        c["budget"] += l["budget"]
        c["actual"] += l["actual"]
        c["n_lines"] += 1
    categories = []
    for c in cats.values():
        c["variance"] = round(c["actual"] - c["budget"], 2)
        c["pct"] = round(c["variance"] / c["budget"] * 100, 2)
        c["budget"], c["actual"] = round(c["budget"], 2), round(c["actual"], 2)
        categories.append(c)
    categories.sort(key=lambda c: -abs(c["variance"]))

    return {
        "lines": lines, "summary": summary, "categories": categories,
        "top_by_amount": [l["idx"] for l in by_amount[:3]],
        "top_by_pct": [l["idx"] for l in by_pct[:3]],
        "rejected": rejected, "warnings": warnings,
    }
