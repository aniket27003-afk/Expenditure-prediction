"""
PRD §8 — deterministic analytics with Python/pandas (NOT the LLM).
Computes: total, monthly totals, category totals, top merchants,
recent transactions, trends.
"""
import pandas as pd


def df_from_transactions(rows: list[dict]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=["amount", "category", "merchant", "transaction_date"])
    df = pd.DataFrame(rows)
    df["transaction_date"] = pd.to_datetime(df["transaction_date"])
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)
    return df


def build_summary(df: pd.DataFrame, recent: list[dict] | None = None) -> dict:
    if df.empty:
        return {
            "total_spending": 0.0,
            "transaction_count": 0,
            "average_transaction": 0.0,
            "monthly_spending": {},
            "category_spending": {},
            "top_merchants": [],
            "recent_transactions": recent or [],
            "trend": [],
        }
    total = float(df["amount"].sum())
    count = int(len(df))
    avg = float(df["amount"].mean())

    monthly = df.copy()
    monthly["month"] = monthly["transaction_date"].dt.strftime("%Y-%m")
    monthly_spending = monthly.groupby("month")["amount"].sum().round(2).to_dict()

    category_spending = df.groupby("category")["amount"].sum().round(2).sort_values(ascending=False).to_dict()

    top = df.groupby("merchant")["amount"].sum().round(2).sort_values(ascending=False).head(5)
    top_merchants = [{"merchant": m, "total": float(v)} for m, v in top.items()]

    trend = [{"month": k, "total": float(v)} for k, v in sorted(monthly_spending.items())]

    return {
        "total_spending": round(total, 2),
        "transaction_count": count,
        "average_transaction": round(avg, 2),
        "monthly_spending": monthly_spending,
        "category_spending": category_spending,
        "top_merchants": top_merchants,
        "recent_transactions": recent or [],
        "trend": trend,
    }


def summary_to_text(s: dict, current_month: str = "") -> str:
    lines = [
        f"Total spending: ₹{s['total_spending']:,.0f} across {s['transaction_count']} transactions "
        f"(avg ₹{s['average_transaction']:,.0f}).",
    ]
    if s["monthly_spending"]:
        lines.append("Monthly totals: " + ", ".join(f"{m} ₹{v:,.0f}" for m, v in sorted(s["monthly_spending"].items())))
    if s["category_spending"]:
        lines.append("By category: " + ", ".join(f"{c} ₹{v:,.0f}" for c, v in s["category_spending"].items()))
    if s["top_merchants"]:
        lines.append("Top merchants: " + ", ".join(f"{m['merchant']} (₹{m['total']:,.0f})" for m in s["top_merchants"]))
    if current_month:
        lines.append(f"Focus month for forecast: {current_month}.")
    return "\n".join(lines)
