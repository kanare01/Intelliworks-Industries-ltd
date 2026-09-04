"""
INTELLIWORKS INDUSTRIES — AUTHENTICATION & RBAC MIDDLEWARE
Strict Supabase JWT verification, user resolution, and role-based access enforcement.
"""

import os
import sys
import uuid
from datetime import datetime, timezone
from functools import wraps
from typing import Optional, Dict, Any, Tuple
from flask import request, jsonify

# Ensure project root is in sys.path
PARENT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

from backend.config import logger
from backend.database import supabase, IS_SUPABASE_CONFIGURED
from backend.middleware.audit import log_audit


def get_current_user() -> Tuple[Optional[Dict[str, Any]], Optional[Tuple[Dict[str, str], int]]]:
    """
    Extracts and cryptographically verifies Supabase JWT token from Authorization header.
    Resolves verified Supabase auth UID to the authoritative user record in `users` table.
    """
    if not IS_SUPABASE_CONFIGURED or not supabase:
        return None, ({"error": "Configuration Required", "message": "Supabase configuration unavailable."}, 503)

    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None, ({"error": "Unauthorized", "message": "Missing or malformed Authorization header."}, 401)

    token = auth_header.split(" ", 1)[1].strip()
    if not token:
        return None, ({"error": "Unauthorized", "message": "Bearer token is empty."}, 401)

    try:
        # Cryptographically verify the session token with Supabase Auth
        auth_res = supabase.auth.get_user(token)
        if not auth_res or not auth_res.user:
            return None, ({"error": "Unauthorized", "message": "Invalid or expired token."}, 401)
        
        user_id = auth_res.user.id
        
        # Retrieve profile record from public.users table
        user_query = supabase.table("users").select("*").eq("id", user_id).execute()
        if not user_query.data or len(user_query.data) == 0:
            # Check if user just registered via Supabase Auth and profile needs creation
            user_meta = auth_res.user.user_metadata or {}
            role = user_meta.get("role", "Client")
            if role not in ["Client", "Writer"]:
                role = "Client"  # Ordinary signup cannot assign Admin
            
            ref_prefix = "IW-WRT-" if role == "Writer" else "IW-CLI-"
            referral_code = f"{ref_prefix}{str(uuid.uuid4())[:8].upper()}"
            
            new_user = {
                "id": user_id,
                "email": auth_res.user.email,
                "full_name": user_meta.get("full_name", auth_res.user.email.split("@")[0]),
                "role": role,
                "account_status": "Active",
                "referral_code": referral_code,
                "total_earnings": 0.0,
                "total_spent": 0.0,
                "available_balance": 0.0,
                "average_rating": 0.0,
                "total_reviews": 0,
                "academic_agreement_accepted": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "last_login": datetime.now(timezone.utc).isoformat()
            }
            create_res = supabase.table("users").insert(new_user).execute()
            current_user = create_res.data[0] if create_res.data else new_user
            log_audit("user_profile_created", "users", user_id, user_id)
        else:
            current_user = user_query.data[0]

        # Enforce account status check
        status = current_user.get("account_status", "Active")
        if status in ["Suspended", "Deactivated"]:
            return None, ({"error": "Forbidden", "message": f"Account is {status}. Contact administration."}, 403)

        return current_user, None

    except Exception as e:
        logger.warning(f"Authentication token verification failure: {e}")
        return None, ({"error": "Unauthorized", "message": "Authentication verification failed."}, 401)


def require_auth(f):
    """Decorator to enforce authenticated session."""
    @wraps(f)
    def decorated(*args, **kwargs):
        user, err = get_current_user()
        if err:
            return jsonify(err[0]), err[1]
        return f(user, *args, **kwargs)
    return decorated


def require_role(*allowed_roles):
    """Decorator to enforce RBAC permissions."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            user, err = get_current_user()
            if err:
                return jsonify(err[0]), err[1]
            if user.get("role") not in allowed_roles:
                return jsonify({
                    "error": "Forbidden",
                    "message": f"Access denied. Requires one of roles: {', '.join(allowed_roles)}"
                }), 403
            return f(user, *args, **kwargs)
        return decorated
    return decorator
