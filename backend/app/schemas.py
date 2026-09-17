"""Pydantic request/response schemas."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

CATEGORIES = [
    "Food",
    "Transportation",
    "Shopping",
    "Bills",
    "Entertainment",
    "Healthcare",
    "Education",
    "Travel",
    "Investment",
    "Other",
]


# ---------- Users ----------
class UserCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: str = Field(..., min_length=3, max_length=255)


class UserOut(BaseModel):
    id: int
    name: str
    email: str
    created_at: datetime

    class Config:
        from_attributes = True


# ---------- Transactions ----------
class TransactionCreate(BaseModel):
    user_id: int
    amount: float = Field(..., gt=0)
    description: str = Field(..., min_length=1)
    payment_method: str = "UPI"
    transaction_date: Optional[datetime] = None


class TransactionOut(BaseModel):
    id: int
    user_id: int
    amount: float
    description: str
    merchant: str
    category: str
    payment_method: str
    transaction_date: datetime
    created_at: datetime

    class Config:
        from_attributes = True


class ParseRequest(BaseModel):
    description: str
    amount: float = 0


class ParseResponse(BaseModel):
    merchant: str
    category: str
    amount: float


# ---------- Insights ----------
class InsightOut(BaseModel):
    id: int
    user_id: int
    insight_type: str
    message: str
    created_at: datetime

    class Config:
        from_attributes = True
