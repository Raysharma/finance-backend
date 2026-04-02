from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.database import Base, engine
from app.routers import auth, users, transactions, dashboard

# Create all tables on startup (safe to call multiple times)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
## Finance Data Processing and Access Control Backend

A backend API for managing financial records with **role-based access control**.

### Roles
| Role | Capabilities |
|------|-------------|
| **viewer** | View balance summary only |
| **analyst** | View records, access full dashboard |
| **admin** | Full access: create, update, delete records and manage users |

### Quick Start
1. Register a user via `POST /auth/register`
2. Login via `POST /auth/login` — copy the `access_token`
3. Click **Authorize** (top right), paste the token
4. Explore the endpoints

### Assumptions
- The first admin must be created via `/auth/register` with `role: admin`.
  In production this would be seeded or protected.
- Deleted transactions are soft-deleted (flagged, not removed) to preserve audit history.
- Amounts are always positive; `type` (income/expense) determines the sign.
""",
    contact={"name": "API Support"},
)

# ── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Global error handlers ─────────────────────────────────────────────────────

@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError):
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": "A database integrity constraint was violated. Possible duplicate entry."},
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": str(exc)},
    )


# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(transactions.router)
app.include_router(dashboard.router)


@app.get("/", tags=["Health"], summary="Health check")
def root():
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
    }
