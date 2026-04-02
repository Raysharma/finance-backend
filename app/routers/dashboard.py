from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, extract
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_active_user, require_analyst_or_above
from app.database import get_db
from app.models.transaction import Transaction, TransactionType
from app.models.user import User
from app.schemas.dashboard import CategoryTotal, MonthlyTrend, DashboardSummary
from app.schemas.transaction import TransactionResponse

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


def _base_query(db: Session, date_from: Optional[date], date_to: Optional[date]):
    """Shared filtered base query for all summary endpoints."""
    q = db.query(Transaction).filter(Transaction.is_deleted == False)
    if date_from:
        q = q.filter(Transaction.date >= date_from)
    if date_to:
        q = q.filter(Transaction.date <= date_to)
    return q


@router.get(
    "/summary",
    response_model=DashboardSummary,
    summary="Full dashboard summary [Analyst & Admin]",
)
def get_dashboard_summary(
    date_from: Optional[date] = Query(None, description="Filter from date (YYYY-MM-DD)"),
    date_to: Optional[date] = Query(None, description="Filter to date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    _: User = Depends(require_analyst_or_above),
):
    """
    Returns a complete dashboard snapshot:
    - Income / expense totals and net balance
    - Category breakdowns for both income and expenses
    - Monthly trends
    - Last 5 transactions
    """
    base = _base_query(db, date_from, date_to)

    # ── Totals ───────────────────────────────────────────────────────────────
    income_row = (
        base.filter(Transaction.type == TransactionType.INCOME)
        .with_entities(func.coalesce(func.sum(Transaction.amount), 0.0), func.count())
        .first()
    )
    expense_row = (
        base.filter(Transaction.type == TransactionType.EXPENSE)
        .with_entities(func.coalesce(func.sum(Transaction.amount), 0.0), func.count())
        .first()
    )

    total_income = float(income_row[0])
    income_count = income_row[1]
    total_expenses = float(expense_row[0])
    expense_count = expense_row[1]
    net_balance = total_income - total_expenses

    # ── Category breakdowns ──────────────────────────────────────────────────
    income_by_cat = (
        base.filter(Transaction.type == TransactionType.INCOME)
        .with_entities(
            Transaction.category,
            func.sum(Transaction.amount).label("total"),
            func.count().label("count"),
        )
        .group_by(Transaction.category)
        .order_by(func.sum(Transaction.amount).desc())
        .all()
    )

    expense_by_cat = (
        base.filter(Transaction.type == TransactionType.EXPENSE)
        .with_entities(
            Transaction.category,
            func.sum(Transaction.amount).label("total"),
            func.count().label("count"),
        )
        .group_by(Transaction.category)
        .order_by(func.sum(Transaction.amount).desc())
        .all()
    )

    # ── Monthly trends ────────────────────────────────────────────────────────
    monthly_raw = (
        base.with_entities(
            extract("year", Transaction.date).label("year"),
            extract("month", Transaction.date).label("month"),
            Transaction.type,
            func.sum(Transaction.amount).label("total"),
        )
        .group_by("year", "month", Transaction.type)
        .order_by("year", "month")
        .all()
    )

    trends: dict[tuple, dict] = {}
    for row in monthly_raw:
        key = (int(row.year), int(row.month))
        if key not in trends:
            trends[key] = {"income": 0.0, "expense": 0.0}
        if row.type == TransactionType.INCOME:
            trends[key]["income"] = float(row.total)
        else:
            trends[key]["expense"] = float(row.total)

    monthly_trends = [
        MonthlyTrend(
            year=k[0],
            month=k[1],
            income=v["income"],
            expense=v["expense"],
            net=v["income"] - v["expense"],
        )
        for k, v in sorted(trends.items())
    ]

    # ── Recent activity (last 5) ──────────────────────────────────────────────
    recent = (
        base.order_by(Transaction.date.desc(), Transaction.id.desc())
        .limit(5)
        .all()
    )

    return DashboardSummary(
        total_income=total_income,
        total_expenses=total_expenses,
        net_balance=net_balance,
        total_transactions=income_count + expense_count,
        income_count=income_count,
        expense_count=expense_count,
        income_by_category=[
            CategoryTotal(category=r.category, total=float(r.total), count=r.count)
            for r in income_by_cat
        ],
        expense_by_category=[
            CategoryTotal(category=r.category, total=float(r.total), count=r.count)
            for r in expense_by_cat
        ],
        monthly_trends=monthly_trends,
        recent_transactions=[TransactionResponse.model_validate(t) for t in recent],
    )


@router.get(
    "/balance",
    summary="Quick balance snapshot [All authenticated users]",
)
def get_balance(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    """
    Lightweight endpoint — returns just total income, expenses, and net.
    Accessible to **all roles** including viewers.
    This gives the viewer something useful without exposing raw records.
    """
    income = db.query(func.coalesce(func.sum(Transaction.amount), 0.0)).filter(
        Transaction.is_deleted == False,
        Transaction.type == TransactionType.INCOME,
    ).scalar()

    expense = db.query(func.coalesce(func.sum(Transaction.amount), 0.0)).filter(
        Transaction.is_deleted == False,
        Transaction.type == TransactionType.EXPENSE,
    ).scalar()

    return {
        "total_income": float(income),
        "total_expenses": float(expense),
        "net_balance": float(income) - float(expense),
    }
