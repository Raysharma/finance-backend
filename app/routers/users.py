from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_active_user, require_admin
from app.core.security import hash_password
from app.database import get_db
from app.models.user import User, UserRole
from app.schemas.user import UserRegister, UserUpdate, UserResponse

router = APIRouter(prefix="/users", tags=["User Management"])


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get your own profile",
)
def get_my_profile(current_user: User = Depends(get_current_active_user)):
    """Any authenticated user can view their own profile."""
    return current_user


@router.get(
    "/",
    response_model=list[UserResponse],
    summary="List all users [Admin only]",
)
def list_users(
    role: Optional[UserRole] = Query(None, description="Filter by role"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Return all users. Supports optional filtering by role or status."""
    query = db.query(User)
    if role is not None:
        query = query.filter(User.role == role)
    if is_active is not None:
        query = query.filter(User.is_active == is_active)
    return query.all()


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Get a specific user [Admin only]",
)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return user


@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    summary="Update a user's role or status [Admin only]",
)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    """
    Admins can update a user's name, role, or active status.

    An admin cannot deactivate their own account.
    """
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    if user.id == current_admin.id and payload.is_active is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot deactivate your own account.",
        )

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)

    db.commit()
    db.refresh(user)
    return user


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a user [Admin only]",
)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    """Permanently delete a user. An admin cannot delete themselves."""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    if user.id == current_admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your own account.",
        )

    db.delete(user)
    db.commit()
