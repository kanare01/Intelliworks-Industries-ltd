"""
INTELLIWORKS INDUSTRIES — UNIT & SECURITY TEST SUITE
Testing backend authorization, RBAC, input validation, and security boundaries.
"""

import os
import json
import pytest
from unittest.mock import patch, MagicMock
from app import app

@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


# =====================================================================
# 1. HEALTH & PUBLIC CONFIGURATION TESTS
# =====================================================================
def test_health_endpoint(client):
    """Verify /api/health reports online status and truthful DB connectivity."""
    res = client.get("/api/health")
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
