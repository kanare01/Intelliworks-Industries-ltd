"""
INTELLIWORKS INDUSTRIES — AUTHENTICATION & RBAC (Compatibility Layer)
Re-exports from backend.middleware.
"""
from backend.middleware.auth import get_current_user, require_auth, require_role
from backend.middleware.audit import log_audit

__all__ = ["get_current_user", "require_auth", "require_role", "log_audit"]
