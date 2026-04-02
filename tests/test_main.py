"""
Tests for the Finance Backend.

Run with:
    pytest tests/ -v

Uses an in-memory SQLite database — no setup needed.
"""

import pytest
from datetime import date
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app

# ── In-memory test database ──────────────────────────────────────────────────

TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_db():
    """Create tables before each test, drop after."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def client():
    return TestClient(app)


# ── Helpers ──────────────────────────────────────────────────────────────────

def register_and_login(client, email, password, role="viewer"):
    client.post("/auth/register", json={
        "name": "Test User", "email": email, "password": password, "role": role
    })
    resp = client.post("/auth/login", data={"username": email, "password": password})
    return resp.json()["access_token"]


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


# ── Auth tests ────────────────────────────────────────────────────────────────

class TestAuth:
    def test_register_success(self, client):
        resp = client.post("/auth/register", json={
            "name": "Alice", "email": "alice@test.com", "password": "pass123"
        })
        assert resp.status_code == 201
        assert resp.json()["email"] == "alice@test.com"
        assert resp.json()["role"] == "viewer"

    def test_register_duplicate_email(self, client):
        data = {"name": "Alice", "email": "alice@test.com", "password": "pass123"}
        client.post("/auth/register", json=data)
        resp = client.post("/auth/register", json=data)
        assert resp.status_code == 409

    def test_login_success(self, client):
        client.post("/auth/register", json={
            "name": "Bob", "email": "bob@test.com", "password": "pass123"
        })
        resp = client.post("/auth/login", data={"username": "bob@test.com", "password": "pass123"})
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    def test_login_wrong_password(self, client):
        client.post("/auth/register", json={
            "name": "Bob", "email": "bob@test.com", "password": "pass123"
        })
        resp = client.post("/auth/login", data={"username": "bob@test.com", "password": "wrongpass"})
        assert resp.status_code == 401

    def test_invalid_token_rejected(self, client):
        resp = client.get("/users/me", headers={"Authorization": "Bearer invalidtoken"})
        assert resp.status_code == 401


# ── Access control tests ──────────────────────────────────────────────────────

class TestAccessControl:
    def test_viewer_cannot_create_transaction(self, client):
        token = register_and_login(client, "viewer@test.com", "pass123", "viewer")
        resp = client.post("/transactions/", headers=auth_header(token), json={
            "amount": 1000, "type": "income", "category": "salary",
            "date": str(date.today()),
        })
        assert resp.status_code == 403

    def test_viewer_cannot_list_transactions(self, client):
        token = register_and_login(client, "viewer@test.com", "pass123", "viewer")
        resp = client.get("/transactions/", headers=auth_header(token))
        assert resp.status_code == 403

    def test_viewer_can_see_balance(self, client):
        token = register_and_login(client, "viewer@test.com", "pass123", "viewer")
        resp = client.get("/dashboard/balance", headers=auth_header(token))
        assert resp.status_code == 200

    def test_analyst_can_list_transactions(self, client):
        token = register_and_login(client, "analyst@test.com", "pass123", "analyst")
        resp = client.get("/transactions/", headers=auth_header(token))
        assert resp.status_code == 200

    def test_analyst_cannot_create_transaction(self, client):
        token = register_and_login(client, "analyst@test.com", "pass123", "analyst")
        resp = client.post("/transactions/", headers=auth_header(token), json={
            "amount": 500, "type": "expense", "category": "rent",
            "date": str(date.today()),
        })
        assert resp.status_code == 403

    def test_admin_can_create_transaction(self, client):
        token = register_and_login(client, "admin@test.com", "pass123", "admin")
        resp = client.post("/transactions/", headers=auth_header(token), json={
            "amount": 5000, "type": "income", "category": "salary",
            "date": str(date.today()),
        })
        assert resp.status_code == 201

    def test_viewer_cannot_list_users(self, client):
        token = register_and_login(client, "viewer@test.com", "pass123", "viewer")
        resp = client.get("/users/", headers=auth_header(token))
        assert resp.status_code == 403

    def test_admin_can_list_users(self, client):
        token = register_and_login(client, "admin@test.com", "pass123", "admin")
        resp = client.get("/users/", headers=auth_header(token))
        assert resp.status_code == 200


# ── Transaction CRUD tests ────────────────────────────────────────────────────

class TestTransactions:
    def setup_admin(self, client):
        return register_and_login(client, "admin@test.com", "pass123", "admin")

    def test_create_and_retrieve(self, client):
        token = self.setup_admin(client)
        create_resp = client.post("/transactions/", headers=auth_header(token), json={
            "amount": 10000, "type": "income", "category": "Salary",
            "date": "2024-05-01", "notes": "May salary",
        })
        assert create_resp.status_code == 201
        txn_id = create_resp.json()["id"]
        # Category should be lowercased
        assert create_resp.json()["category"] == "salary"

        get_resp = client.get(f"/transactions/{txn_id}", headers=auth_header(token))
        assert get_resp.status_code == 200
        assert get_resp.json()["amount"] == 10000

    def test_update_transaction(self, client):
        token = self.setup_admin(client)
        create_resp = client.post("/transactions/", headers=auth_header(token), json={
            "amount": 500, "type": "expense", "category": "rent", "date": "2024-05-01",
        })
        txn_id = create_resp.json()["id"]

        update_resp = client.patch(f"/transactions/{txn_id}", headers=auth_header(token), json={
            "amount": 600,
        })
        assert update_resp.status_code == 200
        assert update_resp.json()["amount"] == 600

    def test_soft_delete(self, client):
        token = self.setup_admin(client)
        create_resp = client.post("/transactions/", headers=auth_header(token), json={
            "amount": 200, "type": "expense", "category": "food", "date": "2024-05-10",
        })
        txn_id = create_resp.json()["id"]

        del_resp = client.delete(f"/transactions/{txn_id}", headers=auth_header(token))
        assert del_resp.status_code == 204

        # Deleted record should not be found
        get_resp = client.get(f"/transactions/{txn_id}", headers=auth_header(token))
        assert get_resp.status_code == 404

    def test_negative_amount_rejected(self, client):
        token = self.setup_admin(client)
        resp = client.post("/transactions/", headers=auth_header(token), json={
            "amount": -100, "type": "income", "category": "salary", "date": "2024-05-01",
        })
        assert resp.status_code == 422

    def test_filter_by_type(self, client):
        token = self.setup_admin(client)
        for txn in [
            {"amount": 1000, "type": "income", "category": "salary", "date": "2024-05-01"},
            {"amount": 200,  "type": "expense", "category": "rent",  "date": "2024-05-02"},
        ]:
            client.post("/transactions/", headers=auth_header(token), json=txn)

        resp = client.get("/transactions/?type=income", headers=auth_header(token))
        assert resp.status_code == 200
        assert all(t["type"] == "income" for t in resp.json()["results"])


# ── Dashboard tests ───────────────────────────────────────────────────────────

class TestDashboard:
    def test_summary_returns_correct_totals(self, client):
        token = register_and_login(client, "admin@test.com", "pass123", "admin")
        for txn in [
            {"amount": 50000, "type": "income",  "category": "salary", "date": "2024-05-01"},
            {"amount": 10000, "type": "expense", "category": "rent",   "date": "2024-05-05"},
            {"amount": 5000,  "type": "expense", "category": "food",   "date": "2024-05-10"},
        ]:
            client.post("/transactions/", headers=auth_header(token), json=txn)

        resp = client.get("/dashboard/summary", headers=auth_header(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_income"] == 50000
        assert data["total_expenses"] == 15000
        assert data["net_balance"] == 35000

    def test_balance_endpoint_accessible_to_viewer(self, client):
        token = register_and_login(client, "viewer@test.com", "pass123", "viewer")
        resp = client.get("/dashboard/balance", headers=auth_header(token))
        assert resp.status_code == 200
        assert "net_balance" in resp.json()
