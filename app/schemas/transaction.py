from datetime import date as DateType, datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator

from app.models.transaction import TransactionType


# ── Request schemas ──────────────────────────────────────────────────────────

class TransactionCreate(BaseModel):
    amount: float = Field(..., gt=0, description="Must be a positive number", examples=[1500.00])
    type: TransactionType
    category: str = Field(..., min_length=1, max_length=100, examples=["Salary"])
    date: DateType = Field(..., examples=["2024-05-20"])
    notes: Optional[str] = Field(None, max_length=500, examples=["Monthly salary"])

    @field_validator("category")
    @classmethod
    def strip_category(cls, v: str) -> str:
        return v.strip().lower()


class TransactionUpdate(BaseModel):
    amount: Optional[float] = Field(None, gt=0)
    type: Optional[TransactionType] = None
    category: Optional[str] = Field(None, min_length=1, max_length=100)
    date: Optional[DateType] = None
    notes: Optional[str] = Field(None, max_length=500)

    @field_validator("category")
    @classmethod
    def strip_category(cls, v: Optional[str]) -> Optional[str]:
        return v.strip().lower() if v else v


# ── Response schemas ─────────────────────────────────────────────────────────

class TransactionResponse(BaseModel):
    id: int
    amount: float
    type: TransactionType
    category: str
    date: DateType
    notes: Optional[str]
    created_by: int
    created_at: datetime

    model_config = {"from_attributes": True}


class PaginatedTransactions(BaseModel):
    total: int
    page: int
    page_size: int
    results: list[TransactionResponse]
