"""
Seed script — populates the database with demo users and transactions.

Run with:
    python seed.py

Creates:
    admin@finance.dev   / admin123    (role: admin)
    analyst@finance.dev / analyst123  (role: analyst)
    viewer@finance.dev  / viewer123   (role: viewer)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from datetime import date, timedelta
import random

from app.database import SessionLocal, Base, engine
from app.models.user import User, UserRole
from app.models.transaction import Transaction, TransactionType
from app.core.security import hash_password

Base.metadata.create_all(bind=engine)

SEED_USERS = [
    {"name": "Admin User",    "email": "admin@finance.dev",   "password": "admin123",   "role": UserRole.ADMIN},
    {"name": "Analyst User",  "email": "analyst@finance.dev", "password": "analyst123", "role": UserRole.ANALYST},
    {"name": "Viewer User",   "email": "viewer@finance.dev",  "password": "viewer123",  "role": UserRole.VIEWER},
]

INCOME_CATEGORIES = ["salary", "freelance", "investment", "bonus", "rental income"]
EXPENSE_CATEGORIES = ["rent", "groceries", "utilities", "transport", "entertainment", "healthcare", "subscriptions"]

INCOME_NOTES = ["Monthly salary", "Freelance project payment", "Stock dividends", "Performance bonus", "Rental collection"]
EXPENSE_NOTES = ["Monthly rent", "Weekly groceries", "Electricity bill", "Commute", "Netflix + Spotify", "Doctor visit", "SaaS tools"]

def seed():
    db = SessionLocal()
    try:
        # ── Users ──────────────────────────────────────────────────────────
        users_created = []
        for u in SEED_USERS:
            existing = db.query(User).filter(User.email == u["email"]).first()
            if existing:
                print(f"  [skip] User {u['email']} already exists.")
                users_created.append(existing)
                continue
            user = User(
                name=u["name"],
                email=u["email"],
                hashed_password=hash_password(u["password"]),
                role=u["role"],
            )
            db.add(user)
            db.flush()
            users_created.append(user)
            print(f"  [+] Created user: {u['email']} ({u['role'].value})")

        db.commit()

        admin_user = next(u for u in users_created if u.role == UserRole.ADMIN)

        # ── Transactions (6 months of demo data) ──────────────────────────
        existing_count = db.query(Transaction).count()
        if existing_count > 0:
            print(f"  [skip] Transactions already seeded ({existing_count} records found).")
            return

        today = date.today()
        transactions = []

        for month_offset in range(6):
            month_start = date(today.year, today.month, 1) - timedelta(days=30 * month_offset)

            # 1-2 income entries per month
            for _ in range(random.randint(1, 2)):
                cat = random.choice(INCOME_CATEGORIES)
                transactions.append(Transaction(
                    amount=round(random.uniform(20000, 80000), 2),
                    type=TransactionType.INCOME,
                    category=cat,
                    date=month_start + timedelta(days=random.randint(0, 28)),
                    notes=random.choice(INCOME_NOTES),
                    created_by=admin_user.id,
                ))

            # 5-8 expense entries per month
            for _ in range(random.randint(5, 8)):
                cat = random.choice(EXPENSE_CATEGORIES)
                transactions.append(Transaction(
                    amount=round(random.uniform(500, 15000), 2),
                    type=TransactionType.EXPENSE,
                    category=cat,
                    date=month_start + timedelta(days=random.randint(0, 28)),
                    notes=random.choice(EXPENSE_NOTES),
                    created_by=admin_user.id,
                ))

        db.add_all(transactions)
        db.commit()
        print(f"  [+] Seeded {len(transactions)} transactions.")

    finally:
        db.close()

    print("\nSeed complete!")
    print("─" * 40)
    print("Login credentials:")
    for u in SEED_USERS:
        print(f"  {u['role'].value:<10}  {u['email']}  /  {u['password']}")


if __name__ == "__main__":
    print("Seeding database...\n")
    seed()
