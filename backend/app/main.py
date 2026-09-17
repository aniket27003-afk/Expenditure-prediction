"""
Smart Expense & Spending Analyzer — FastAPI backend (PRD §5).

Flow: Web UI → FastAPI → Transaction Parser → LLM → PostgreSQL
      → Python/SQL analytics → summary → LLM → insights → Dashboard
"""
from datetime import datetime
import json
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import desc

from .config import settings
from .database import Base, engine, get_db
from . import models
from .schemas import (
    UserCreate, UserOut, TransactionCreate, TransactionOut,
    ParseRequest, ParseResponse, InsightOut,
)
from .llm import parse_transaction, generate_spending_insights, detect_anomalies, forecast_spending
from .analytics import df_from_transactions, build_summary, summary_to_text

Base.metadata.create_all(bind=engine)

app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list + ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok", "app": settings.APP_NAME, "llm_configured": bool(settings.GROQ_API_KEY),
            "llm_provider": "groq", "llm_model": settings.GROQ_MODEL}


@app.get("/")
def root():
    return {"message": settings.APP_NAME + " API — see /docs", "docs": "/docs", "health": "/health"}


# ---------------------------------------------------------------- users
@app.post("/api/users", response_model=UserOut)
def create_user(payload: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.email == payload.email).first()
    if existing:
        return existing
    user = models.User(name=payload.name, email=payload.email)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.get("/api/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db)):
    return db.query(models.User).order_by(models.User.id).all()


def _require_user(db: Session, user_id: int) -> models.User:
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(404, f"User {user_id} not found. Create one via POST /api/users first.")
    return user


# ---------------------------------------------------------------- parse (PRD §4B)
@app.post("/api/parse", response_model=ParseResponse)
def parse_only(payload: ParseRequest):
    try:
        return parse_transaction(payload.description, payload.amount)
    except RuntimeError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(502, f"LLM parse failed: {e}")


# ---------------------------------------------------------------- transactions (PRD §4A/4B/4C)
@app.post("/api/transactions", response_model=TransactionOut)
def add_transaction(payload: TransactionCreate, db: Session = Depends(get_db)):
    _require_user(db, payload.user_id)
    try:
        parsed = parse_transaction(payload.description, payload.amount)
    except RuntimeError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(502, f"LLM categorization failed: {e}")

    txn = models.Transaction(
        user_id=payload.user_id,
        amount=payload.amount,
        description=payload.description,
        merchant=parsed["merchant"],
        category=parsed["category"],
        payment_method=payload.payment_method,
        transaction_date=payload.transaction_date or datetime.utcnow(),
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)
    return txn


@app.get("/api/transactions", response_model=list[TransactionOut])
def list_transactions(user_id: int, limit: int = 100, db: Session = Depends(get_db)):
    _require_user(db, user_id)
    return (
        db.query(models.Transaction)
        .filter(models.Transaction.user_id == user_id)
        .order_by(desc(models.Transaction.transaction_date))
        .limit(min(limit, 500))
        .all()
    )


@app.delete("/api/transactions/{txn_id}")
def delete_transaction(txn_id: int, db: Session = Depends(get_db)):
    txn = db.query(models.Transaction).filter(models.Transaction.id == txn_id).first()
    if not txn:
        raise HTTPException(404, "Transaction not found")
    db.delete(txn)
    db.commit()
    return {"deleted": txn_id}


# ---------------------------------------------------------------- dashboard (PRD §4D — Python/SQL only)
@app.get("/api/dashboard")
def dashboard(user_id: int, db: Session = Depends(get_db)):
    _require_user(db, user_id)
    txns = (
        db.query(models.Transaction)
        .filter(models.Transaction.user_id == user_id)
        .order_by(desc(models.Transaction.transaction_date))
        .all()
    )
    rows = [
        {"amount": t.amount, "category": t.category, "merchant": t.merchant,
         "transaction_date": t.transaction_date}
        for t in txns
    ]
    recent = [
        {"id": t.id, "amount": t.amount, "description": t.description, "merchant": t.merchant,
         "category": t.category, "payment_method": t.payment_method,
         "transaction_date": t.transaction_date.isoformat()}
        for t in txns[:10]
    ]
    summary = build_summary(df_from_transactions(rows), recent=recent)
    return summary


# ---------------------------------------------------------------- AI analysis (PRD §4E/4F/4G)
def _summary_text_for_user(db: Session, user_id: int) -> tuple[str, dict]:
    txns = (
        db.query(models.Transaction)
        .filter(models.Transaction.user_id == user_id)
        .order_by(desc(models.Transaction.transaction_date))
        .limit(200)
        .all()
    )
    if not txns:
        raise HTTPException(400, "No transactions yet — add some before generating insights.")
    rows = [{"amount": t.amount, "category": t.category, "merchant": t.merchant,
             "transaction_date": t.transaction_date} for t in txns]
    summary = build_summary(df_from_transactions(rows))
    detail = "\n".join(f"- ₹{t.amount:,.0f} {t.merchant} ({t.category}): {t.description}" for t in txns[:30])
    text = summary_to_text(summary) + f"\nRecent transactions:\n{detail}"
    return text, summary


def _save_insight(db: Session, user_id: int, kind: str, message: str | dict) -> models.AIInsight:
    if isinstance(message, dict):
        message = json.dumps(message, ensure_ascii=False)
    ins = models.AIInsight(user_id=user_id, insight_type=kind, message=message)
    db.add(ins)
    db.commit()
    db.refresh(ins)
    return ins


@app.post("/api/insights/generate")
def generate_insights(user_id: int, db: Session = Depends(get_db)):
    _require_user(db, user_id)
    summary_text, summary = _summary_text_for_user(db, user_id)
    try:
        insights_msg = generate_spending_insights(summary_text)
        anomaly_msg = detect_anomalies(summary_text)
        monthly_text = "\n".join(f"{m} ₹{v:,.0f}" for m, v in sorted(summary["monthly_spending"].items())) or "No monthly data"
        forecast_msg = forecast_spending(monthly_text)
    except RuntimeError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(502, f"LLM analysis failed: {e}")

    saved = [
        _save_insight(db, user_id, "summary", insights_msg),
        _save_insight(db, user_id, "anomaly", anomaly_msg),
        _save_insight(db, user_id, "forecast", forecast_msg),
    ]
    return {
        "summary": insights_msg,
        "anomalies": anomaly_msg,
        "forecast": forecast_msg,
        "saved_ids": [s.id for s in saved],
    }


@app.get("/api/insights", response_model=list[InsightOut])
def list_insights(user_id: int, limit: int = 20, db: Session = Depends(get_db)):
    _require_user(db, user_id)
    return (
        db.query(models.AIInsight)
        .filter(models.AIInsight.user_id == user_id)
        .order_by(desc(models.AIInsight.created_at))
        .limit(min(limit, 100))
        .all()
    )


# ---------------------------------------------------------------- seed demo data
@app.post("/api/seed")
def seed_demo(user_id: int, db: Session = Depends(get_db)):
    """Insert the PRD's messy-transaction examples + a few more for instant demo."""
    _require_user(db, user_id)
    from .llm import rule_based_parse
    demos = [
        (280, "UPI-UBER-TRIP-284", "UPI", "2026-08-02"),
        (499, "SWIGGY ORDER 8472", "UPI", "2026-08-05"),
        (1299, "AMAZON PAY INDIA", "Credit Card", "2026-08-09"),
        (840, "IRCTC TXN 93821", "Debit Card", "2026-08-14"),
        (450, "ZOMATO ORDER 5521", "UPI", "2026-09-01"),
        (320, "OLA RIDE 9931", "UPI", "2026-09-03"),
        (2100, "ELECTRICITY BILL AUG", "Netbanking", "2026-09-05"),
        (699, "NETFLIX SUBSCRIPTION", "Credit Card", "2026-09-06"),
        (12500, "FLIPKART BIG BILLION SALE", "Credit Card", "2026-09-10"),
        (650, "APOLLO PHARMACY", "UPI", "2026-09-12"),
    ]
    created = 0
    for amount, desc, method, date in demos:
        exists = db.query(models.Transaction).filter(
            models.Transaction.user_id == user_id,
            models.Transaction.description == desc).first()
        if exists:
            continue
        p = rule_based_parse(desc, amount)
        db.add(models.Transaction(
            user_id=user_id, amount=amount, description=desc,
            merchant=p["merchant"], category=p["category"],
            payment_method=method, transaction_date=datetime.fromisoformat(date)))
        created += 1
    db.commit()
    return {"seeded": created}
