# Finance Data Processing and Access Control Backend

A role-based finance dashboard backend built with **FastAPI**, **SQLAlchemy**, and **SQLite**.

---

## Table of Contents

- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Setup and Running](#setup-and-running)
- [Role-Based Access Control](#role-based-access-control)
- [API Overview](#api-overview)
- [Design Decisions and Assumptions](#design-decisions-and-assumptions)
- [Running Tests](#running-tests)

---

## Tech Stack

| Layer | Choice | Reason |
|---|---|---|
| Framework | FastAPI | Fast, Pydantic-native, auto-generates Swagger docs |
| ORM | SQLAlchemy 2.x | Mature, relational, clean query interface |
| Database | SQLite | Zero-config; easy for evaluators to run locally |
| Auth | JWT (python-jose) | Stateless, standard, token-based |
| Passwords | bcrypt (passlib) | Industry-standard password hashing |
| Validation | Pydantic v2 | Integrated with FastAPI, expressive schemas |

---

## Project Structure

```
finance-backend/
├── app/
│   ├── core/
│   │   ├── config.py          # App settings (env-driven)
│   │   ├── security.py        # JWT creation/decoding, password hashing
│   │   └── dependencies.py    # FastAPI auth + role-guard dependencies
│   ├── models/
│   │   ├── user.py            # User SQLAlchemy model
│   │   └── transaction.py     # Transaction SQLAlchemy model
│   ├── schemas/
│   │   ├── user.py            # Pydantic request/response schemas for users
│   │   ├── transaction.py     # Pydantic schemas for transactions
│   │   └── dashboard.py       # Pydantic schemas for dashboard summaries
│   ├── routers/
│   │   ├── auth.py            # /auth — register and login
│   │   ├── users.py           # /users — user management
│   │   ├── transactions.py    # /transactions — CRUD + filters
│   │   └── dashboard.py       # /dashboard — aggregated analytics
│   ├── database.py            # SQLAlchemy engine, session, Base
│   └── main.py                # FastAPI app, router wiring, error handlers
├── tests/
│   └── test_main.py           # Unit + integration tests
├── seed.py                    # Demo data seeder
├── requirements.txt
├── .env.example
└── README.md
```

---

## Setup and Running

### 1. Clone and create a virtual environment

```bash
git clone <repo-url>
cd finance-backend

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment (optional)

```bash
cp .env.example .env
# Edit .env if needed — defaults work out of the box
```

### 4. Seed demo data

```bash
python seed.py
```

This creates three demo users and ~40 transactions spread across the last 6 months:

| Email | Password | Role |
|---|---|---|
| admin@finance.dev | admin123 | admin |
| analyst@finance.dev | analyst123 | analyst |
| viewer@finance.dev | viewer123 | viewer |

### 5. Run the server

```bash
uvicorn app.main:app --reload
```

Open **http://localhost:8000/docs** — the interactive Swagger UI has every endpoint documented.

---

## Role-Based Access Control

Access control is enforced at the route level using FastAPI dependency injection.
Every protected route declares which role(s) are permitted directly in its signature — there is no scattered `if user.role == ...` logic inside business code.

```
dependencies.py
  └── get_current_user()          → validates JWT, loads User from DB
      └── get_current_active_user() → rejects inactive accounts
          ├── require_admin            → admin only
          ├── require_analyst_or_above → analyst + admin
          └── require_any_role         → all authenticated users
```

### Permission Matrix

| Endpoint | Viewer | Analyst | Admin |
|---|:---:|:---:|:---:|
| `GET /dashboard/balance` | ✅ | ✅ | ✅ |
| `GET /dashboard/summary` | ❌ | ✅ | ✅ |
| `GET /transactions/` | ❌ | ✅ | ✅ |
| `GET /transactions/{id}` | ❌ | ✅ | ✅ |
| `POST /transactions/` | ❌ | ❌ | ✅ |
| `PATCH /transactions/{id}` | ❌ | ❌ | ✅ |
| `DELETE /transactions/{id}` | ❌ | ❌ | ✅ |
| `GET /users/me` | ✅ | ✅ | ✅ |
| `GET /users/` | ❌ | ❌ | ✅ |
| `PATCH /users/{id}` | ❌ | ❌ | ✅ |
| `DELETE /users/{id}` | ❌ | ❌ | ✅ |

---

## API Overview

### Authentication — `/auth`

| Method | Path | Description |
|---|---|---|
| POST | `/auth/register` | Register a new user |
| POST | `/auth/login` | Login, receive JWT token |

### Users — `/users`

| Method | Path | Description | Role |
|---|---|---|---|
| GET | `/users/me` | Your own profile | Any |
| GET | `/users/` | List all users (filter by role/status) | Admin |
| GET | `/users/{id}` | Get a specific user | Admin |
| PATCH | `/users/{id}` | Update name, role, or status | Admin |
| DELETE | `/users/{id}` | Delete a user | Admin |

### Transactions — `/transactions`

| Method | Path | Description | Role |
|---|---|---|---|
| POST | `/transactions/` | Create a record | Admin |
| GET | `/transactions/` | List records (paginated, filterable) | Analyst+ |
| GET | `/transactions/{id}` | Get single record | Analyst+ |
| PATCH | `/transactions/{id}` | Update record | Admin |
| DELETE | `/transactions/{id}` | Soft-delete record | Admin |

**Available filters for `GET /transactions/`:**
- `type` — `income` or `expense`
- `category` — exact match (case-insensitive)
- `date_from` / `date_to` — date range (YYYY-MM-DD)
- `page` / `page_size` — pagination (default: page 1, 20 per page)

### Dashboard — `/dashboard`

| Method | Path | Description | Role |
|---|---|---|---|
| GET | `/dashboard/balance` | Quick income/expense/net snapshot | Any |
| GET | `/dashboard/summary` | Full analytics: totals, category breakdowns, monthly trends, recent activity | Analyst+ |

**Optional date filter for `/dashboard/summary`:**
- `date_from` / `date_to` — limit analytics to a date window

---

## Design Decisions and Assumptions

**SQLite over PostgreSQL**
SQLite was chosen to make the project immediately runnable without any database installation. The ORM layer means switching to PostgreSQL requires only a one-line change to `DATABASE_URL`.

**Soft deletes on transactions**
Financial records are soft-deleted (flagged with `is_deleted = True`) rather than permanently removed. This preserves audit history — a realistic requirement for any finance system. Deleted records are excluded from all queries and analytics automatically.

**Amounts are always positive**
The `type` field (income/expense) carries the sign semantics. Storing negative amounts would be ambiguous and would complicate aggregation queries.

**Categories are normalized to lowercase**
A Pydantic validator strips whitespace and lowercases all category values at input time. This prevents `"Salary"`, `"salary"`, and `"SALARY"` from appearing as three separate categories in dashboard summaries.

**Admin self-protection rules**
An admin cannot deactivate or delete their own account. This prevents accidental lockout.

**First admin bootstrap**
The `/auth/register` endpoint accepts any role, including `admin`. In a production system this would be restricted — only existing admins could promote others. For this assessment, this is documented as a known simplification.

**JWT expiry**
Tokens expire after 24 hours by default. This is configurable via `ACCESS_TOKEN_EXPIRE_MINUTES` in `.env`.

**Viewer gets `GET /dashboard/balance`**
The Viewer role was given access to the lightweight balance endpoint so they have something meaningful to see. The full summary (which exposes raw category data and trends) is restricted to Analyst and above.

---

## Running Tests

```bash
pytest tests/ -v
```

Tests use an in-memory SQLite database — no setup required. The suite covers:

- Registration and login flows
- Invalid token / wrong password rejection
- Role enforcement for every access level (viewer, analyst, admin)
- Full transaction CRUD lifecycle
- Soft-delete behavior (deleted records return 404)
- Input validation (negative amounts, missing fields)
- Dashboard summary correctness (totals, net balance)
- Viewer access to balance endpoint
