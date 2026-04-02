from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_active_user, require_admin, require_analyst_or_above
from app.database import get_db
from app.models.transaction import Transaction, TransactionType
from app.models.user import User, UserRole
from app.schemas.transaction import (
    TransactionCreate,
    TransactionUpdate,
    TransactionResponse,
    PaginatedTransactions,
)

router = APIRouter(prefix="/transactions", tags=["Transactions"])


@router.post(
    "/",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a financial record [Admin only]",
)
def create_transaction(
    payload: TransactionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Only admins can create new financial records."""
    txn = Transaction(
        amount=payload.amount,
        type=payload.type,
        category=payload.category,
        date=payload.date,
        notes=payload.notes,
        created_by=current_user.id,
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)
    return txn


@router.get(
    "/",
    response_model=PaginatedTransactions,
    summary="List financial records [Analyst & Admin]",
)
def list_transactions(
    # Filters
    type: Optional[TransactionType] = Query(None, description="Filter by income or expense"),
    category: Optional[str] = Query(None, description="Filter by category (case-insensitive)"),
    date_from: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    date_to: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    # Pagination
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Results per page"),
    db: Session = Depends(get_db),
    _: User = Depends(require_analyst_or_above),
):
    """
    Retrieve paginated financial records with optional filters.

    - Viewers **cannot** access this endpoint.
    - Analysts and Admins can read all records.
    """
    query = db.query(Transaction).filter(Transaction.is_deleted == False)

    if type is not None:
        query = query.filter(Transaction.type == type)
    if category:
        query = query.filter(Transaction.category == category.strip().lower())
    if date_from:
        query = query.filter(Transaction.date >= date_from)
    if date_to:
        query = query.filter(Transaction.date <= date_to)

    total = query.count()
    results = (
        query.order_by(Transaction.date.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return PaginatedTransactions(total=total, page=page, page_size=page_size, results=results)


@router.get(
    "/{transaction_id}",
    response_model=TransactionResponse,
    summary="Get a single financial record [Analyst & Admin]",
)
def get_transaction(
    transaction_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_analyst_or_above),
):
    txn = db.query(Transaction).filter(
        Transaction.id == transaction_id,
        Transaction.is_deleted == False,
    ).first()
    if not txn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found.")
    return txn


@router.patch(
    "/{transaction_id}",
    response_model=TransactionResponse,
    summary="Update a financial record [Admin only]",
)
def update_transaction(
    transaction_id: int,
    payload: TransactionUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    txn = db.query(Transaction).filter(
        Transaction.id == transaction_id,
        Transaction.is_deleted == False,
    ).first()
    if not txn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found.")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(txn, field, value)

    db.commit()
    db.refresh(txn)
    return txn


@router.delete(
    "/{transaction_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete a financial record [Admin only]",
)
def delete_transaction(
    transaction_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """
    Soft-deletes the record — it remains in the database but is excluded
    from all queries. This preserves audit history.
    """
    txn = db.query(Transaction).filter(
        Transaction.id == transaction_id,
        Transaction.is_deleted == False,
    ).first()
    if not txn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found.")

    txn.is_deleted = True
    db.commit()
