from typing import Optional
from pydantic import BaseModel


class CategoryTotal(BaseModel):
    category: str
    total: float
    count: int


class MonthlyTrend(BaseModel):
    year: int
    month: int
    income: float
    expense: float
    net: float


class DashboardSummary(BaseModel):
    total_income: float
    total_expenses: float
    net_balance: float
    total_transactions: int
    income_count: int
    expense_count: int
    income_by_category: list[CategoryTotal]
    expense_by_category: list[CategoryTotal]
    monthly_trends: list[MonthlyTrend]
    recent_transactions: list  # reuse TransactionResponse at router level
