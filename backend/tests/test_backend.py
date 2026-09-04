"""
INTELLIWORKS INDUSTRIES — UNIT & SECURITY TEST SUITE
Testing backend authorization, RBAC, input validation, and security boundaries.
"""

import os
import sys
import json
import pytest

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.app import app, create_app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


# =====================================================================
# 1. HEALTH & PUBLIC CONFIGURATION TESTS
# =====================================================================
def test_health_endpoint(client):
    """Verify /api/health and /health report online status and truthful DB connectivity."""
    for path in ["/api/health", "/health"]:
        res = client.get(path)
        assert res.status_code == 200
        data = res.get_json()
        assert data["status"] == "online"
        assert "configured" in data
        assert "database" in data
        assert "system" in data


def test_academic_policy_endpoint(client):
    """Verify explicit permitted and prohibited academic assistance declarations."""
    res = client.get("/api/academic-policy")
    assert res.status_code == 200
    data = res.get_json()
    assert "permitted_services" in data
    assert "prohibited_activities" in data
    assert len(data["permitted_services"]) > 0
    assert len(data["prohibited_activities"]) > 0


def test_public_settings(client):
    """Verify public settings returns standard 80/20 split and minimum withdrawal."""
    res = client.get("/api/settings")
    assert res.status_code == 200
    data = res.get_json()
    assert "escrow_split" in data
    assert data["escrow_split"]["writer_percentage"] == 80.0
    assert data["escrow_split"]["platform_fee_percentage"] == 20.0


# =====================================================================
# 2. SECURITY TESTS: AUTHENTICATION & SPOOFING REJECTION
# =====================================================================
def test_reject_missing_token(client):
    """Verify protected endpoints reject missing Authorization header."""
    res = client.get("/api/me")
    assert res.status_code in [401, 503]
    data = res.get_json()
    assert "error" in data


def test_reject_malformed_token(client):
    """Verify protected endpoints reject malformed or non-Bearer tokens."""
    headers = {"Authorization": "Basic 12345"}
    res = client.get("/api/me", headers=headers)
    assert res.status_code in [401, 503]


def test_reject_custom_header_spoofing(client):
    """
    CRITICAL SECURITY CHECK:
    Verify that custom headers like X-User-ID or X-Role are strictly IGNORED
    and do not bypass authentication.
    """
    headers = {
        "X-User-ID": "00000000-0000-0000-0000-000000000001",
        "X-Role": "Admin"
    }
    res = client.get("/api/me", headers=headers)
    # Must fail with 401 Unauthorized or 503 (if Supabase not configured), never 200
    assert res.status_code in [401, 503]


def test_reject_query_param_spoofing(client):
    """
    CRITICAL SECURITY CHECK:
    Verify that query parameters like ?user_id=123 or ?role=Admin do not grant access.
    """
    res = client.get("/api/me?user_id=00000000-0000-0000-0000-000000000001&role=Admin")
    assert res.status_code in [401, 503]


# =====================================================================
# 3. UNIT TESTS: VALIDATION LOGIC & ESCROW ACCOUNTING
# =====================================================================
def test_escrow_80_20_calculation():
    """Verify exact 80/20 arithmetic."""
    budget = 150.00
    writer_payout = round(budget * 0.80, 2)
    platform_fee = round(budget * 0.20, 2)
    assert writer_payout == 120.00
    assert platform_fee == 30.00
    assert (writer_payout + platform_fee) == budget


def test_client_assignment_validation_without_auth(client):
    """Creating assignment without authentication must fail."""
    payload = {
        "title": "Quantum Physics Literature Review",
        "category": "Research Assistance",
        "subject": "Physics",
        "description": "Comprehensive review of superconducting qubits",
        "instructions": "Follow IEEE format and peer-reviewed journals only",
        "deadline": "2026-12-31T23:59:59Z",
        "budget": 200.0,
        "academic_integrity_declaration": True
    }
    res = client.post("/api/assignments", json=payload)
    assert res.status_code in [401, 503]


def test_admin_routes_protected(client):
    """Admin metric and arbitration routes must reject unauthenticated requests."""
    res_metrics = client.get("/api/admin/metrics")
    assert res_metrics.status_code in [401, 503]

    res_users = client.get("/api/admin/users")
    assert res_users.status_code in [401, 503]

    res_audit = client.get("/api/admin/audit-logs")
    assert res_audit.status_code in [401, 503]


def test_consistent_json_error_handling(client):
    """Verify 404 returns structured JSON error."""
    res = client.get("/api/non-existent-route-12345")
    assert res.status_code == 404
    data = res.get_json()
    assert "error" in data


def test_backend_folder_modular_architecture():
    """Verify backend package exposes app, create_app, and health endpoint."""
    from backend.app import app as backend_app, create_app
    assert backend_app is not None
    assert callable(create_app)
    with backend_app.test_client() as backend_client:
        res = backend_client.get("/api/health")
        assert res.status_code == 200
        data = res.get_json()
        assert data["status"] == "online"


def test_supabase_jwt_verification_decorator():
    """Verify verify_supabase_jwt decorator in backend/app.py secures routes properly."""
    from backend.app import verify_supabase_jwt, require_auth, require_role
    from flask import Flask, jsonify

    test_app = Flask(__name__)

    @test_app.route("/protected-endpoint")
    @verify_supabase_jwt
    def protected_route():
        return jsonify({"message": "success"})

    with test_app.test_client() as tc:
        # Missing Authorization header
        r1 = tc.get("/protected-endpoint")
        assert r1.status_code == 401
        assert "Missing or malformed Authorization header" in r1.get_json()["message"]

        # Malformed Authorization header (non-Bearer)
        r2 = tc.get("/protected-endpoint", headers={"Authorization": "Token 12345"})
        assert r2.status_code == 401

        # Empty Bearer token
        r3 = tc.get("/protected-endpoint", headers={"Authorization": "Bearer "})
        assert r3.status_code == 401


def test_backend_schema_sql_exists_and_defines_all_tables():
    """
    Verify backend/schema.sql exists and defines all 13 required tables:
    users, assignments, submissions, transactions, withdrawals, disputes,
    reviews, messages, notifications, referrals, audit_logs, platform_settings, and files.
    """
    schema_path = os.path.join(os.path.dirname(__file__), "../schema.sql")
    assert os.path.exists(schema_path), "backend/schema.sql must exist"

    with open(schema_path, "r") as f:
        content = f.read().lower()

    required_tables = [
        "users",
        "assignments",
        "submissions",
        "transactions",
        "withdrawals",
        "disputes",
        "reviews",
        "messages",
        "notifications",
        "referrals",
        "audit_logs",
        "platform_settings",
        "files"
    ]

    for table in required_tables:
        pattern = f"create table {table}"
        assert pattern in content, f"backend/schema.sql must define table: {table}"


# =====================================================================
# 4. DATABASE HELPERS & CORE CRUD ROUTE TESTS
# =====================================================================
def test_database_helpers_exported_and_callable():
    """Verify all database helper functions for Supabase service role interactions exist."""
    from backend.app import (
        get_supabase_admin_client,
        db_get_record,
        db_list_records,
        db_insert_record,
        db_update_record,
        db_delete_record,
        get_user_by_id,
        get_user_by_email,
        create_user_record,
        update_user_record,
        delete_user_record,
        list_users_records,
        create_user,
        update_user,
        delete_user,
        list_users,
        get_assignment_by_id,
        create_assignment_record,
        update_assignment_record,
        delete_assignment_record,
        list_assignments_records,
        create_assignment,
        update_assignment,
        delete_assignment,
        list_assignments
    )

    helpers = [
        get_supabase_admin_client,
        db_get_record,
        db_list_records,
        db_insert_record,
        db_update_record,
        db_delete_record,
        get_user_by_id,
        get_user_by_email,
        create_user_record,
        update_user_record,
        delete_user_record,
        list_users_records,
        create_user,
        update_user,
        delete_user,
        list_users,
        get_assignment_by_id,
        create_assignment_record,
        update_assignment_record,
        delete_assignment_record,
        list_assignments_records,
        create_assignment,
        update_assignment,
        delete_assignment,
        list_assignments
    ]

    for h in helpers:
        assert callable(h), f"Helper function {h.__name__} must be callable"


def test_user_crud_endpoints_security(client):
    """Verify all User CRUD endpoints are secured with cryptographic JWT verification."""
    # List users
    r1 = client.get("/api/users")
    assert r1.status_code in [401, 503]

    # Create user
    r2 = client.post("/api/users", json={"email": "newuser@example.com", "full_name": "New User"})
    assert r2.status_code in [401, 503]

    # Get single user
    r3 = client.get("/api/users/00000000-0000-0000-0000-000000000001")
    assert r3.status_code in [401, 503]

    # Update user
    r4 = client.put("/api/users/00000000-0000-0000-0000-000000000001", json={"bio": "Updated bio"})
    assert r4.status_code in [401, 503]

    # Delete user
    r5 = client.delete("/api/users/00000000-0000-0000-0000-000000000001")
    assert r5.status_code in [401, 503]


def test_assignment_crud_endpoints_security(client):
    """Verify all Assignment CRUD endpoints are secured with cryptographic JWT verification."""
    # List assignments
    r1 = client.get("/api/assignments")
    assert r1.status_code in [401, 503]

    # Create assignment
    r2 = client.post("/api/assignments", json={
        "title": "Empirical Macroeconomics Analysis",
        "category": "Quantitative Analysis",
        "budget": 100.0,
        "academic_integrity_declaration": True
    })
    assert r2.status_code in [401, 503]

    # Get single assignment
    r3 = client.get("/api/assignments/00000000-0000-0000-0000-000000000001")
    assert r3.status_code in [401, 503]

    # Update assignment
    r4 = client.put("/api/assignments/00000000-0000-0000-0000-000000000001", json={"title": "Updated Title"})
    assert r4.status_code in [401, 503]

    # Delete assignment
    r5 = client.delete("/api/assignments/00000000-0000-0000-0000-000000000001")
    assert r5.status_code in [401, 503]


def test_database_helpers_with_mock_client(monkeypatch):
    """Verify that database helper functions correctly format and execute queries via Supabase client."""
    import sys
    from unittest.mock import MagicMock

    app_module = sys.modules["backend.app"]

    mock_client = MagicMock()
    mock_table = MagicMock()
    mock_client.table.return_value = mock_table

    # Mock execute result
    mock_execute_result = MagicMock()
    mock_execute_result.data = [{"id": "test-id-123", "title": "Test Assignment", "status": "Open"}]
    mock_execute_result.count = 1

    mock_table.select.return_value = mock_table
    mock_table.insert.return_value = mock_table
    mock_table.update.return_value = mock_table
    mock_table.delete.return_value = mock_table
    mock_table.eq.return_value = mock_table
    mock_table.order.return_value = mock_table
    mock_table.limit.return_value = mock_table
    mock_table.offset.return_value = mock_table
    mock_table.execute.return_value = mock_execute_result

    monkeypatch.setattr(app_module, "get_supabase_admin_client", lambda: mock_client)

    # Test db_get_record
    record = app_module.db_get_record("assignments", "test-id-123")
    assert record is not None
    assert record["id"] == "test-id-123"
    mock_client.table.assert_called_with("assignments")

    # Test db_list_records
    records, count = app_module.db_list_records("assignments", filters={"status": "Open"}, limit=10)
    assert len(records) == 1
    assert count == 1

    # Test db_insert_record
    inserted = app_module.db_insert_record("assignments", {"title": "New Assignment"})
    assert inserted["id"] == "test-id-123"

    # Test db_update_record
    updated = app_module.db_update_record("assignments", "test-id-123", {"title": "Updated"})
    assert updated["id"] == "test-id-123"

    # Test db_delete_record
    deleted = app_module.db_delete_record("assignments", "test-id-123")
    assert deleted is True

    # Test high level user helpers
    u = app_module.get_user_by_id("test-id-123")
    assert u is not None

    # Test high level assignment helpers
    a = app_module.get_assignment_by_id("test-id-123")
    assert a is not None


def test_authenticated_crud_routes_execution(monkeypatch, client):
    """Verify that CRUD endpoints execute correctly when called with a valid user context."""
    import sys
    from unittest.mock import MagicMock

    app_module = sys.modules["backend.app"]

    # Mock user object
    mock_user = {
        "id": "11111111-2222-3333-4444-555555555555",
        "email": "client@example.com",
        "role": "Client",
        "account_status": "Active",
        "total_spent": 0.0
    }

    # Mock supabase client and responses
    mock_client = MagicMock()
    mock_table = MagicMock()
    mock_client.table.return_value = mock_table

    mock_res = MagicMock()
    mock_res.data = [mock_user]
    mock_res.count = 1

    mock_table.select.return_value = mock_table
    mock_table.insert.return_value = mock_table
    mock_table.update.return_value = mock_table
    mock_table.delete.return_value = mock_table
    mock_table.eq.return_value = mock_table
    mock_table.order.return_value = mock_table
    mock_table.limit.return_value = mock_table
    mock_table.offset.return_value = mock_table
    mock_table.execute.return_value = mock_res

    # Mock Supabase Auth
    mock_auth_user = MagicMock()
    mock_auth_user.id = mock_user["id"]
    mock_auth_user.email = mock_user["email"]
    mock_auth_user.user_metadata = {"role": "Client"}

    mock_auth_res = MagicMock()
    mock_auth_res.user = mock_auth_user

    mock_client.auth.get_user.return_value = mock_auth_res

    monkeypatch.setattr(app_module, "supabase", mock_client)
    monkeypatch.setattr(app_module, "IS_SUPABASE_CONFIGURED", True)
    monkeypatch.setattr(app_module, "get_supabase_admin_client", lambda: mock_client)

    headers = {"Authorization": "Bearer mock-valid-jwt-token"}

    # Test GET /api/users
    res_users = client.get("/api/users", headers=headers)
    assert res_users.status_code == 200
    assert "users" in res_users.get_json()

    # Test GET /api/assignments
    res_assignments = client.get("/api/assignments", headers=headers)
    assert res_assignments.status_code == 200
    assert "assignments" in res_assignments.get_json()

    # Test POST /api/assignments validation errors (missing fields)
    res_invalid_post = client.post("/api/assignments", json={}, headers=headers)
    assert res_invalid_post.status_code == 422




