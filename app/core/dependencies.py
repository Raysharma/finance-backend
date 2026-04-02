"""
Access control dependencies.

Usage in routes:
    @router.post("/", dependencies=[Depends(require_admin)])
    @router.get("/", dependencies=[Depends(require_analyst_or_above)])

Or inject the user object:
    @router.get("/me")
    async def me(current_user: User = Depends(get_current_active_user)):
        ...
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.database import get_db
from app.models.user import User, UserRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Extract and validate the JWT token, return the corresponding User."""
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id: str = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Malformed token.")

    user = db.get(User, int(user_id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found.")
    return user


def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """Block deactivated accounts."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is inactive. Contact an administrator.",
        )
    return current_user


# ── Role guards ──────────────────────────────────────────────────────────────

def _require_role(*allowed_roles: UserRole):
    """Factory that returns a dependency enforcing one of the allowed roles."""
    def _guard(current_user: User = Depends(get_current_active_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Access denied. Required role(s): "
                    f"{', '.join(r.value for r in allowed_roles)}. "
                    f"Your role: {current_user.role.value}."
                ),
            )
        return current_user
    return _guard


# Convenience dependencies used in route definitions
require_admin = _require_role(UserRole.ADMIN)
require_analyst_or_above = _require_role(UserRole.ANALYST, UserRole.ADMIN)
require_any_role = get_current_active_user  # just needs to be authenticated
