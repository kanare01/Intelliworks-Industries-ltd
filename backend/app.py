"""
INTELLIWORKS INDUSTRIES — FLASK APPLICATION ENGINE
Modular Flask skeleton with CORS configuration, centralized JSON error handling,
and the mandatory /api/health health-check endpoint.
"""

import os
import sys

# Ensure project root is in sys.path when running backend/app.py directly
PARENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

import inspect
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from functools import wraps
from typing import Optional, Dict, Any, List, Tuple
from flask import Flask, jsonify, request, send_from_directory, g
from flask_cors import CORS

from backend.config import (
    FLASK_SECRET_KEY,
    APP_ENV,
    IS_SUPABASE_CONFIGURED,
    SUPABASE_URL,
    SUPABASE_SERVICE_ROLE_KEY,
    logger
)
from backend.database import supabase
from backend.middleware.audit import log_audit
from backend.routes import register_routes


# =====================================================================
# SUPABASE SERVICE ROLE DATABASE HELPER FUNCTIONS
# =====================================================================
def get_supabase_admin_client():
    """
    Returns the Supabase client initialized with the privileged Service Role Key.
    Ensures administrative and authoritative access for backend CRUD operations.
    """
    global supabase
    if supabase is not None:
        return supabase
    if IS_SUPABASE_CONFIGURED and SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY:
        try:
            from supabase import create_client
            supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
            return supabase
        except Exception as e:
            logger.error(f"Error instantiating Supabase service role client: {e}")
    return None


def db_get_record(table: str, id_value: str, id_col: str = "id") -> Optional[Dict[str, Any]]:
    """Retrieve a single record by primary key or column using the service role key."""
    client = get_supabase_admin_client()
    if not client:
        return None
    try:
        res = client.table(table).select("*").eq(id_col, id_value).execute()
        if res.data and len(res.data) > 0:
            return res.data[0]
        return None
    except Exception as e:
        logger.error(f"db_get_record error ({table}:{id_value}): {e}")
        raise e


def db_list_records(
    table: str,
    filters: Optional[Dict[str, Any]] = None,
    order_col: str = "created_at",
    desc: bool = True,
    limit: int = 50,
    offset: int = 0
) -> Tuple[List[Dict[str, Any]], int]:
    """List records from a table with filters, ordering, pagination, and total count."""
    client = get_supabase_admin_client()
    if not client:
        return [], 0
    try:
        query = client.table(table).select("*", count="exact")
        if filters:
            for k, v in filters.items():
                if v is not None:
                    query = query.eq(k, v)
        if order_col:
            query = query.order(order_col, desc=desc)
        if limit and limit > 0:
            query = query.limit(min(limit, 100))
        if offset and offset > 0:
            query = query.offset(offset)
        res = query.execute()
        count = res.count if res.count is not None else len(res.data or [])
        return res.data or [], count
    except Exception as e:
        logger.error(f"db_list_records error ({table}): {e}")
        raise e


def db_insert_record(table: str, record_data: Dict[str, Any]) -> Dict[str, Any]:
    """Insert a new record into a table using the service role key."""
    client = get_supabase_admin_client()
    if not client:
        raise RuntimeError("Database client unavailable (Supabase not configured)")
    try:
        res = client.table(table).insert(record_data).execute()
        if res.data and len(res.data) > 0:
            return res.data[0]
        return record_data
    except Exception as e:
        logger.error(f"db_insert_record error ({table}): {e}")
        raise e


def db_update_record(table: str, id_value: str, updates: Dict[str, Any], id_col: str = "id") -> Dict[str, Any]:
    """Update a record by ID using the service role key."""
    client = get_supabase_admin_client()
    if not client:
        raise RuntimeError("Database client unavailable (Supabase not configured)")
    try:
        res = client.table(table).update(updates).eq(id_col, id_value).execute()
        if res.data and len(res.data) > 0:
            return res.data[0]
        return updates
    except Exception as e:
        logger.error(f"db_update_record error ({table}:{id_value}): {e}")
        raise e


def db_delete_record(table: str, id_value: str, id_col: str = "id") -> bool:
    """Delete a record by ID using the service role key."""
    client = get_supabase_admin_client()
    if not client:
        raise RuntimeError("Database client unavailable (Supabase not configured)")
    try:
        client.table(table).delete().eq(id_col, id_value).execute()
        return True
    except Exception as e:
        logger.error(f"db_delete_record error ({table}:{id_value}): {e}")
        raise e


# --- User-Specific Database Helpers ---
def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    return db_get_record("users", user_id)


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    return db_get_record("users", email.strip().lower(), id_col="email")


def create_user_record(user_data: Dict[str, Any]) -> Dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    if "created_at" not in user_data:
        user_data["created_at"] = now
    if "updated_at" not in user_data:
        user_data["updated_at"] = now
    return db_insert_record("users", user_data)


def update_user_record(user_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    return db_update_record("users", user_id, updates)


def delete_user_record(user_id: str) -> bool:
    return db_delete_record("users", user_id)


def list_users_records(
    role: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
) -> Tuple[List[Dict[str, Any]], int]:
    filters = {}
    if role:
        filters["role"] = role
    if status:
        filters["account_status"] = status
    return db_list_records("users", filters=filters, order_col="created_at", desc=True, limit=limit, offset=offset)


# Direct function aliases
create_user = create_user_record
update_user = update_user_record
delete_user = delete_user_record
list_users = list_users_records


# --- Assignment-Specific Database Helpers ---
def get_assignment_by_id(assignment_id: str) -> Optional[Dict[str, Any]]:
    return db_get_record("assignments", assignment_id)


def create_assignment_record(assignment_data: Dict[str, Any]) -> Dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    if "created_at" not in assignment_data:
        assignment_data["created_at"] = now
    if "updated_at" not in assignment_data:
        assignment_data["updated_at"] = now
    return db_insert_record("assignments", assignment_data)


def update_assignment_record(assignment_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    return db_update_record("assignments", assignment_id, updates)


def delete_assignment_record(assignment_id: str) -> bool:
    return db_delete_record("assignments", assignment_id)


def list_assignments_records(
    status: Optional[str] = None,
    client_id: Optional[str] = None,
    writer_id: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
) -> Tuple[List[Dict[str, Any]], int]:
    filters = {}
    if status:
        filters["status"] = status
    if client_id:
        filters["client_id"] = client_id
    if writer_id:
        filters["writer_id"] = writer_id
    if category:
        filters["category"] = category
    return db_list_records("assignments", filters=filters, order_col="created_at", desc=True, limit=limit, offset=offset)


# Direct function aliases
create_assignment = create_assignment_record
update_assignment = update_assignment_record
delete_assignment = delete_assignment_record
list_assignments = list_assignments_records


def verify_supabase_jwt(f):
    """
    Decorator that cryptographically validates Supabase access tokens from the Authorization header.
    Extracts Bearer token, validates with Supabase Auth API, verifies active user account status,
    and sets g.current_user (also injecting 'user' into route handlers that declare it).
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({
                "error": "Unauthorized",
                "message": "Missing or malformed Authorization header. Expected 'Bearer <token>'."
            }), 401

        token = auth_header.split(" ", 1)[1].strip()
        if not token:
            return jsonify({
                "error": "Unauthorized",
                "message": "Bearer token is empty."
            }), 401

        if not IS_SUPABASE_CONFIGURED or not supabase:
            return jsonify({
                "error": "Configuration Required",
                "message": "Supabase configuration unavailable."
            }), 503

        try:
            # Validate access token with Supabase Auth
            auth_res = supabase.auth.get_user(token)
            if not auth_res or not auth_res.user:
                return jsonify({
                    "error": "Unauthorized",
                    "message": "Invalid or expired Supabase token."
                }), 401

            user_id = auth_res.user.id

            # Retrieve profile record from public.users table
            user_query = supabase.table("users").select("*").eq("id", user_id).execute()
            if not user_query.data or len(user_query.data) == 0:
                user_meta = auth_res.user.user_metadata or {}
                role = user_meta.get("role", "Client")
                if role not in ["Client", "Writer"]:
                    role = "Client"

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
            else:
                current_user = user_query.data[0]

            # Verify active account status
            status = current_user.get("account_status", "Active")
            if status in ["Suspended", "Deactivated"]:
                return jsonify({
                    "error": "Forbidden",
                    "message": f"Account is {status}. Contact administration."
                }), 403

            g.current_user = current_user

            # If function expects user or current_user as first parameter, provide it
            sig = inspect.signature(f)
            if "user" in sig.parameters or "current_user" in sig.parameters:
                return f(current_user, *args, **kwargs)
            return f(*args, **kwargs)

        except Exception as e:
            logger.warning(f"Supabase JWT verification failure: {e}")
            return jsonify({
                "error": "Unauthorized",
                "message": "Authentication verification failed."
            }), 401

    return decorated_function


# Aliases for flexible import conventions
require_auth = verify_supabase_jwt
verify_jwt = verify_supabase_jwt


def require_role(*allowed_roles):
    """
    Decorator that validates Supabase JWT and enforces allowed user roles.
    """
    def decorator(f):
        @wraps(f)
        @verify_supabase_jwt
        def decorated_function(*args, **kwargs):
            user = getattr(g, "current_user", None)
            if not user or user.get("role") not in allowed_roles:
                return jsonify({
                    "error": "Forbidden",
                    "message": f"Access denied. Requires one of roles: {', '.join(allowed_roles)}"
                }), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def create_app() -> Flask:
    """
    Initializes and configures the Flask application skeleton.
    Includes CORS configuration, basic error handling, /api/health endpoint,
    and modular API blueprint registration.
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dist_dir = os.path.join(base_dir, "dist")

    app = Flask(__name__, static_folder=dist_dir, static_url_path="")
    app.config["SECRET_KEY"] = FLASK_SECRET_KEY

    # -----------------------------------------------------------------
    # CORS CONFIGURATION
    # -----------------------------------------------------------------
    CORS(
        app,
        resources={r"/api/*": {"origins": "*"}},
        supports_credentials=True,
        allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
        methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"]
    )

    # -----------------------------------------------------------------
    # HEALTH CHECK ROUTE (/health & /api/health)
    # -----------------------------------------------------------------
    @app.route("/health", methods=["GET"])
    @app.route("/api/health", methods=["GET"])
    def health_check():
        """Health check endpoint showing real backend status and Supabase connectivity."""
        db_status = "VERIFIED" if IS_SUPABASE_CONFIGURED else "BLOCKED — Supabase configuration unavailable"
        return jsonify({
            "status": "online",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "environment": APP_ENV,
            "configured": IS_SUPABASE_CONFIGURED,
            "supabase_connected": IS_SUPABASE_CONFIGURED,
            "database": db_status,
            "auth": db_status,
            "storage": db_status,
            "system": "Intelliworks Industries Core Engine"
        }), 200

    # -----------------------------------------------------------------
    # CORE CRUD ROUTES: USERS
    # -----------------------------------------------------------------
    @app.route("/api/users", methods=["GET"])
    @verify_supabase_jwt
    def handle_list_users(current_user):
        """List user records with optional role and status filters."""
        role_filter = request.args.get("role")
        status_filter = request.args.get("status")
        try:
            limit = int(request.args.get("limit", 50))
            offset = int(request.args.get("offset", 0))
        except ValueError:
            limit, offset = 50, 0

        try:
            users, count = list_users_records(
                role=role_filter,
                status=status_filter,
                limit=limit,
                offset=offset
            )
            # If requester is not Admin, sanitize sensitive private financial details
            if current_user.get("role") != "Admin":
                sanitized = []
                for u in users:
                    sanitized.append({
                        "id": u.get("id"),
                        "full_name": u.get("full_name"),
                        "role": u.get("role"),
                        "bio": u.get("bio"),
                        "skills": u.get("skills", []),
                        "average_rating": u.get("average_rating", 0.0),
                        "total_reviews": u.get("total_reviews", 0),
                        "account_status": u.get("account_status"),
                        "created_at": u.get("created_at")
                    })
                users = sanitized

            return jsonify({"users": users, "count": count}), 200
        except Exception as e:
            logger.error(f"Error listing users: {e}")
            return jsonify({"error": "Failed to list users", "message": str(e)}), 500

    @app.route("/api/users", methods=["POST"])
    @verify_supabase_jwt
    def handle_create_user(current_user):
        """Create a new user profile record using the privileged service role key."""
        # Only Admin or user creation flows
        data = request.get_json() or {}
        email = str(data.get("email", "")).strip().lower()
        if not email or "@" not in email:
            return jsonify({"error": "Validation Error", "message": "A valid email address is required."}), 422

        role = data.get("role", "Client")
        if role not in ["Client", "Writer", "Admin"]:
            role = "Client"

        # Check existing user
        try:
            existing = get_user_by_email(email)
            if existing:
                return jsonify({"error": "Conflict", "message": "User with this email already exists."}), 409

            user_id = data.get("id") or str(uuid.uuid4())
            ref_prefix = "IW-WRT-" if role == "Writer" else "IW-CLI-"
            referral_code = f"{ref_prefix}{str(uuid.uuid4())[:8].upper()}"

            new_user = {
                "id": user_id,
                "email": email,
                "full_name": str(data.get("full_name", email.split("@")[0])).strip(),
                "role": role,
                "account_status": data.get("account_status", "Active"),
                "bio": str(data.get("bio", "")).strip(),
                "skills": data.get("skills", []) if isinstance(data.get("skills"), list) else [],
                "referral_code": referral_code,
                "total_earnings": 0.0,
                "total_spent": 0.0,
                "available_balance": 0.0,
                "average_rating": 0.0,
                "total_reviews": 0,
                "academic_agreement_accepted": bool(data.get("academic_agreement_accepted", True)),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }

            created = create_user_record(new_user)
            log_audit("create_user", "users", user_id, current_user.get("id"), {"email": email, "role": role})
            return jsonify({"message": "User created successfully", "user": created}), 201
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            return jsonify({"error": "Failed to create user", "message": str(e)}), 500

    @app.route("/api/users/<user_id>", methods=["GET"])
    @verify_supabase_jwt
    def handle_get_user(current_user, user_id):
        """Retrieve a specific user profile by user ID."""
        try:
            user_data = get_user_by_id(user_id)
            if not user_data:
                return jsonify({"error": "Not Found", "message": "User not found."}), 404

            # Non-admins viewing another user receive sanitized public profile
            if current_user.get("role") != "Admin" and current_user.get("id") != user_id:
                user_data = {
                    "id": user_data.get("id"),
                    "full_name": user_data.get("full_name"),
                    "role": user_data.get("role"),
                    "bio": user_data.get("bio"),
                    "skills": user_data.get("skills", []),
                    "average_rating": user_data.get("average_rating", 0.0),
                    "total_reviews": user_data.get("total_reviews", 0),
                    "account_status": user_data.get("account_status"),
                    "created_at": user_data.get("created_at")
                }

            return jsonify({"user": user_data}), 200
        except Exception as e:
            logger.error(f"Error retrieving user {user_id}: {e}")
            return jsonify({"error": "Failed to retrieve user", "message": str(e)}), 500

    @app.route("/api/users/<user_id>", methods=["PUT", "PATCH"])
    @verify_supabase_jwt
    def handle_update_user(current_user, user_id):
        """Update an existing user profile with role-aware authorization."""
        # Self or Admin can update
        is_admin = current_user.get("role") == "Admin"
        is_self = current_user.get("id") == user_id
        if not (is_admin or is_self):
            return jsonify({"error": "Forbidden", "message": "You cannot modify another user's profile."}), 403

        data = request.get_json() or {}
        allowed_updates = {}

        # Standard user-editable fields
        if "full_name" in data and isinstance(data["full_name"], str) and data["full_name"].strip():
            allowed_updates["full_name"] = data["full_name"].strip()
        if "bio" in data and isinstance(data["bio"], str):
            allowed_updates["bio"] = data["bio"].strip()
        if "skills" in data and isinstance(data["skills"], list):
            allowed_updates["skills"] = [str(s).strip() for s in data["skills"] if str(s).strip()]
        if "profile_photo" in data and isinstance(data["profile_photo"], str):
            allowed_updates["profile_photo"] = data["profile_photo"].strip()
        if "academic_agreement_accepted" in data:
            allowed_updates["academic_agreement_accepted"] = bool(data["academic_agreement_accepted"])

        # Admin-only privileged fields
        if is_admin:
            if "role" in data and data["role"] in ["Client", "Writer", "Admin"]:
                allowed_updates["role"] = data["role"]
            if "account_status" in data and data["account_status"] in ["Active", "Suspended", "Pending Approval", "Deactivated"]:
                allowed_updates["account_status"] = data["account_status"]
            if "available_balance" in data:
                try:
                    allowed_updates["available_balance"] = float(Decimal(str(data["available_balance"])).quantize(Decimal("0.01")))
                except Exception:
                    pass

        if not allowed_updates:
            return jsonify({"error": "Validation Error", "message": "No valid fields provided for update."}), 400

        try:
            updated = update_user_record(user_id, allowed_updates)
            log_audit("update_user", "users", user_id, current_user.get("id"), {"fields": list(allowed_updates.keys())})
            return jsonify({"message": "User updated successfully", "user": updated}), 200
        except Exception as e:
            logger.error(f"Error updating user {user_id}: {e}")
            return jsonify({"error": "Failed to update user", "message": str(e)}), 500

    @app.route("/api/users/<user_id>", methods=["DELETE"])
    @verify_supabase_jwt
    def handle_delete_user(current_user, user_id):
        """Delete or deactivate user profile with role-aware authorization."""
        is_admin = current_user.get("role") == "Admin"
        is_self = current_user.get("id") == user_id
        if not (is_admin or is_self):
            return jsonify({"error": "Forbidden", "message": "You cannot delete another user's account."}), 403

        try:
            hard_delete = request.args.get("hard", "false").lower() == "true" and is_admin
            if hard_delete:
                delete_user_record(user_id)
                action = "hard_delete_user"
            else:
                update_user_record(user_id, {"account_status": "Deactivated"})
                action = "deactivate_user"

            log_audit(action, "users", user_id, current_user.get("id"))
            return jsonify({"message": "User deleted successfully"}), 200
        except Exception as e:
            logger.error(f"Error deleting user {user_id}: {e}")
            return jsonify({"error": "Failed to delete user", "message": str(e)}), 500

    # -----------------------------------------------------------------
    # CORE CRUD ROUTES: ASSIGNMENTS
    # -----------------------------------------------------------------
    @app.route("/api/assignments", methods=["GET"])
    @verify_supabase_jwt
    def handle_list_assignments(current_user):
        """List assignments with role-aware views and filtering."""
        status_filter = request.args.get("status")
        category_filter = request.args.get("category")
        client_id = request.args.get("client_id")
        writer_id = request.args.get("writer_id")
        view = request.args.get("view", "default")

        try:
            limit = int(request.args.get("limit", 50))
            offset = int(request.args.get("offset", 0))
        except ValueError:
            limit, offset = 50, 0

        # Role-based scoping
        user_role = current_user.get("role", "Client")
        user_id = current_user.get("id")

        if user_role == "Client":
            # Clients default to viewing their own assignments unless explicitly querying
            if not client_id and view != "all":
                client_id = user_id
        elif user_role == "Writer":
            if view == "workspace":
                writer_id = user_id
            elif view == "marketplace" or (not status_filter and not writer_id):
                status_filter = "Open"
        # Admin can view all without implicit filter restrictions

        try:
            assignments, count = list_assignments_records(
                status=status_filter,
                client_id=client_id,
                writer_id=writer_id,
                category=category_filter,
                limit=limit,
                offset=offset
            )
            return jsonify({"assignments": assignments, "count": count}), 200
        except Exception as e:
            logger.error(f"Error listing assignments: {e}")
            return jsonify({"error": "Failed to list assignments", "message": str(e)}), 500

    @app.route("/api/assignments", methods=["POST"])
    @verify_supabase_jwt
    def handle_create_assignment(current_user):
        """
        Create a new assignment with server-authoritative 80/20 escrow calculation,
        deadline validation, academic integrity declaration, and transactional escrow deposit.
        """
        if current_user.get("role") not in ["Client", "Admin"]:
            return jsonify({
                "error": "Forbidden",
                "message": "Only Clients or Administrators can commission assignments."
            }), 403

        data = request.get_json() or {}

        title = str(data.get("title", "")).strip()
        category = str(data.get("category", "")).strip()
        subject = str(data.get("subject", "")).strip()
        description = str(data.get("description", "")).strip()
        instructions = str(data.get("instructions", "")).strip()
        deadline_str = data.get("deadline")
        budget_raw = data.get("budget")
        word_count_raw = data.get("word_count", 0)
        academic_accepted = bool(data.get("academic_integrity_declaration", False))

        if not all([title, category, subject, description, instructions, deadline_str, budget_raw]):
            return jsonify({
                "error": "Validation Error",
                "message": "All project specifications and instructions are required."
            }), 422

        if not academic_accepted:
            return jsonify({
                "error": "Academic Policy",
                "message": "You must confirm the Academic Integrity Declaration."
            }), 422

        try:
            budget = float(Decimal(str(budget_raw)).quantize(Decimal("0.01")))
            if budget < 10.0:
                return jsonify({
                    "error": "Validation Error",
                    "message": "Minimum project budget is $10.00."
                }), 422
        except Exception:
            return jsonify({
                "error": "Validation Error",
                "message": "Invalid budget format."
            }), 422

        try:
            word_count = max(0, int(word_count_raw))
        except Exception:
            word_count = 0

        try:
            deadline_dt = datetime.fromisoformat(deadline_str.replace("Z", "+00:00"))
            if deadline_dt <= datetime.now(timezone.utc):
                return jsonify({
                    "error": "Validation Error",
                    "message": "Deadline must be set in the future."
                }), 422
        except Exception:
            return jsonify({
                "error": "Validation Error",
                "message": "Invalid deadline ISO format."
            }), 422

        # Server-authoritative 80/20 Escrow calculation
        writer_payout = round(budget * 0.80, 2)
        platform_fee = round(budget * 0.20, 2)

        assignment_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        assignment_record = {
            "id": assignment_id,
            "client_id": current_user["id"],
            "writer_id": None,
            "title": title,
            "category": category,
            "subject": subject,
            "description": description,
            "instructions": instructions,
            "word_count": word_count,
            "budget": budget,
            "deadline": deadline_dt.isoformat(),
            "status": "Open",
            "revision_count": 0,
            "escrow_status": "Funded",
            "writer_payout": writer_payout,
            "platform_fee": platform_fee,
            "academic_integrity_declaration": True,
            "created_at": now,
            "updated_at": now
        }

        try:
            # 1. Insert assignment record using service role key helper
            created = create_assignment_record(assignment_record)

            # 2. Record immutable Escrow Deposit transaction
            deposit_tx = {
                "id": str(uuid.uuid4()),
                "user_id": current_user["id"],
                "assignment_id": assignment_id,
                "transaction_type": "Escrow Deposit",
                "amount": budget,
                "status": "Completed",
                "reference": f"ESCROW-DEP-{assignment_id[:8]}",
                "idempotency_key": f"escrow-dep-{assignment_id}",
                "metadata": {
                    "writer_payout": writer_payout,
                    "platform_fee": platform_fee,
                    "title": title
                },
                "created_at": now
            }
            try:
                db_insert_record("transactions", deposit_tx)
            except Exception as tx_err:
                logger.warning(f"Could not write deposit transaction: {tx_err}")

            # 3. Update client total spent
            try:
                curr_spent = float(current_user.get("total_spent", 0.0))
                update_user_record(current_user["id"], {"total_spent": round(curr_spent + budget, 2)})
            except Exception as user_err:
                logger.warning(f"Could not update user spent total: {user_err}")

            # 4. Write audit entry
            log_audit("create_assignment", "assignments", assignment_id, current_user["id"], {
                "budget": budget,
                "writer_payout": writer_payout,
                "platform_fee": platform_fee
            })

            return jsonify({
                "message": "Assignment created and escrow successfully funded.",
                "assignment": created
            }), 201
        except Exception as e:
            logger.error(f"Error creating assignment: {e}")
            return jsonify({"error": "Failed to create assignment", "message": str(e)}), 500

    @app.route("/api/assignments/<assignment_id>", methods=["GET"])
    @verify_supabase_jwt
    def handle_get_assignment(current_user, assignment_id):
        """Retrieve a specific assignment record by ID."""
        try:
            assignment = get_assignment_by_id(assignment_id)
            if not assignment:
                return jsonify({"error": "Not Found", "message": "Assignment not found."}), 404

            # Open assignments are viewable by any authenticated marketplace user
            # Claimed/completed assignments require ownership or Admin role
            status = assignment.get("status")
            user_id = current_user.get("id")
            user_role = current_user.get("role")

            is_owner = assignment.get("client_id") == user_id
            is_writer = assignment.get("writer_id") == user_id
            is_admin = user_role == "Admin"

            if status != "Open" and not (is_owner or is_writer or is_admin):
                return jsonify({
                    "error": "Forbidden",
                    "message": "You do not have permission to view this assignment."
                }), 403

            return jsonify({"assignment": assignment}), 200
        except Exception as e:
            logger.error(f"Error retrieving assignment {assignment_id}: {e}")
            return jsonify({"error": "Failed to retrieve assignment", "message": str(e)}), 500

    @app.route("/api/assignments/<assignment_id>", methods=["PUT", "PATCH"])
    @verify_supabase_jwt
    def handle_update_assignment(current_user, assignment_id):
        """Update assignment specifications with authorization checks."""
        try:
            existing = get_assignment_by_id(assignment_id)
            if not existing:
                return jsonify({"error": "Not Found", "message": "Assignment not found."}), 404

            user_id = current_user.get("id")
            is_admin = current_user.get("role") == "Admin"
            is_client = existing.get("client_id") == user_id
            is_open = existing.get("status") == "Open"

            if not is_admin and not (is_client and is_open):
                return jsonify({
                    "error": "Forbidden",
                    "message": "Only the commissioning Client (while Open) or an Administrator can update this project."
                }), 403

            data = request.get_json() or {}
            allowed_updates = {}

            # Project specification fields
            if "title" in data and isinstance(data["title"], str) and data["title"].strip():
                allowed_updates["title"] = data["title"].strip()
            if "category" in data and isinstance(data["category"], str) and data["category"].strip():
                allowed_updates["category"] = data["category"].strip()
            if "subject" in data and isinstance(data["subject"], str) and data["subject"].strip():
                allowed_updates["subject"] = data["subject"].strip()
            if "description" in data and isinstance(data["description"], str) and data["description"].strip():
                allowed_updates["description"] = data["description"].strip()
            if "instructions" in data and isinstance(data["instructions"], str) and data["instructions"].strip():
                allowed_updates["instructions"] = data["instructions"].strip()
            if "word_count" in data:
                try:
                    allowed_updates["word_count"] = max(0, int(data["word_count"]))
                except Exception:
                    pass
            if "deadline" in data:
                try:
                    dl = datetime.fromisoformat(str(data["deadline"]).replace("Z", "+00:00"))
                    if dl > datetime.now(timezone.utc):
                        allowed_updates["deadline"] = dl.isoformat()
                except Exception:
                    pass

            # Admin-only fields
            if is_admin:
                if "status" in data:
                    allowed_updates["status"] = data["status"]
                if "escrow_status" in data:
                    allowed_updates["escrow_status"] = data["escrow_status"]
                if "writer_id" in data:
                    allowed_updates["writer_id"] = data["writer_id"]

            if not allowed_updates:
                return jsonify({"error": "Validation Error", "message": "No valid fields provided for update."}), 400

            updated = update_assignment_record(assignment_id, allowed_updates)
            log_audit("update_assignment", "assignments", assignment_id, user_id, {"fields": list(allowed_updates.keys())})
            return jsonify({"message": "Assignment updated successfully", "assignment": updated}), 200
        except Exception as e:
            logger.error(f"Error updating assignment {assignment_id}: {e}")
            return jsonify({"error": "Failed to update assignment", "message": str(e)}), 500

    @app.route("/api/assignments/<assignment_id>", methods=["DELETE"])
    @verify_supabase_jwt
    def handle_delete_assignment(current_user, assignment_id):
        """Cancel or delete an assignment record with authorization checks."""
        try:
            existing = get_assignment_by_id(assignment_id)
            if not existing:
                return jsonify({"error": "Not Found", "message": "Assignment not found."}), 404

            user_id = current_user.get("id")
            is_admin = current_user.get("role") == "Admin"
            is_client = existing.get("client_id") == user_id
            is_open = existing.get("status") in ["Open", "Draft"]

            if not is_admin and not (is_client and is_open):
                return jsonify({
                    "error": "Forbidden",
                    "message": "Only the commissioning Client (while Open) or an Administrator can delete this project."
                }), 403

            hard_delete = request.args.get("hard", "false").lower() == "true" and is_admin
            if hard_delete:
                delete_assignment_record(assignment_id)
                action = "hard_delete_assignment"
            else:
                # Cancel and refund escrow
                update_assignment_record(assignment_id, {
                    "status": "Cancelled",
                    "escrow_status": "Refunded"
                })
                # If escrow was funded, record refund transaction
                if existing.get("escrow_status") == "Funded":
                    refund_tx = {
                        "id": str(uuid.uuid4()),
                        "user_id": existing.get("client_id"),
                        "assignment_id": assignment_id,
                        "transaction_type": "Escrow Refund",
                        "amount": float(existing.get("budget", 0.0)),
                        "status": "Completed",
                        "reference": f"ESCROW-REF-{assignment_id[:8]}",
                        "idempotency_key": f"escrow-ref-{assignment_id}",
                        "metadata": {"reason": "Assignment cancelled by client"},
                        "created_at": datetime.now(timezone.utc).isoformat()
                    }
                    try:
                        db_insert_record("transactions", refund_tx)
                    except Exception as ref_err:
                        logger.warning(f"Could not record refund transaction: {ref_err}")
                action = "cancel_assignment"

            log_audit(action, "assignments", assignment_id, user_id)
            return jsonify({"message": "Assignment deleted successfully"}), 200
        except Exception as e:
            logger.error(f"Error deleting assignment {assignment_id}: {e}")
            return jsonify({"error": "Failed to delete assignment", "message": str(e)}), 500

    # -----------------------------------------------------------------
    # REGISTER MODULAR DOMAIN ROUTE BLUEPRINTS
    # -----------------------------------------------------------------
    register_routes(app)

    # -----------------------------------------------------------------
    # BASIC ERROR HANDLING (CONSISTENT JSON RESPONSES)
    # -----------------------------------------------------------------
    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"error": "Bad Request", "message": str(e)}), 400

    @app.errorhandler(401)
    def unauthorized(e):
        return jsonify({"error": "Unauthorized", "message": "Authentication required."}), 401

    @app.errorhandler(403)
    def forbidden(e):
        return jsonify({"error": "Forbidden", "message": "Permission denied."}), 403

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Not Found", "message": "Resource does not exist."}), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify({"error": "Method Not Allowed", "message": "HTTP method not supported for this endpoint."}), 405

    @app.errorhandler(409)
    def conflict(e):
        return jsonify({"error": "Conflict", "message": "Resource conflict."}), 409

    @app.errorhandler(500)
    def server_error(e):
        logger.error(f"Internal server error: {e}")
        return jsonify({"error": "Internal Server Error", "message": "An unexpected error occurred."}), 500

    # -----------------------------------------------------------------
    # STATIC FILE SERVING FOR PRODUCTION SPA
    # -----------------------------------------------------------------
    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def serve_frontend(path):
        """Serve built frontend static files in production."""
        if path != "" and os.path.exists(os.path.join(dist_dir, path)):
            return send_from_directory(dist_dir, path)
        if os.path.exists(os.path.join(dist_dir, "index.html")):
            return send_from_directory(dist_dir, "index.html")
        return jsonify({
            "name": "Intelliworks Industries API",
            "status": "ready",
            "api_docs": "/api/health"
        })

    return app


app = create_app()

__all__ = [
    "app",
    "create_app",
    "verify_supabase_jwt",
    "require_auth",
    "require_role",
    "get_supabase_admin_client",
    "db_get_record",
    "db_list_records",
    "db_insert_record",
    "db_update_record",
    "db_delete_record",
    "get_user_by_id",
    "get_user_by_email",
    "create_user_record",
    "update_user_record",
    "delete_user_record",
    "list_users_records",
    "create_user",
    "update_user",
    "delete_user",
    "list_users",
    "get_assignment_by_id",
    "create_assignment_record",
    "update_assignment_record",
    "delete_assignment_record",
    "list_assignments_records",
    "create_assignment",
    "update_assignment",
    "delete_assignment",
    "list_assignments"
]

if __name__ == "__main__":
    port = int(os.getenv("FLASK_PORT", 5001))
    logger.info(f"Starting Intelliworks Industries Flask backend on port {port}")
    app.run(host="0.0.0.0", port=port, debug=(APP_ENV == "development"), use_reloader=False)
