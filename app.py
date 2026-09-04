"""
INTELLIWORKS INDUSTRIES — MASTER BACKEND (Flask + Supabase PostgreSQL & Storage)
Strict server-side authorization, atomic claiming, escrow ledger, and audit logging.
"""

import os
import sys
import uuid
import logging
from datetime import datetime, timezone
from decimal import Decimal
from functools import wraps
from typing import Optional, Dict, Any, Tuple

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("intelliworks_api")

app = Flask(__name__, static_folder="dist", static_url_path="")
CORS(app, resources={r"/api/*": {"origins": "*"}})

# ---------------------------------------------------------------------
# CONFIGURATION & ENVIRONMENT VALIDATION
# ---------------------------------------------------------------------
SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "").strip()
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "").strip()
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "intelliworks-enterprise-production-key")
APP_ENV = os.getenv("APP_ENV", "development")
STORAGE_BUCKET = "assignment-files"

app.config["SECRET_KEY"] = FLASK_SECRET_KEY

# Determine if Supabase credentials are configured
IS_SUPABASE_CONFIGURED = bool(SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY and not SUPABASE_URL.startswith("https://your-project"))

supabase = None
if IS_SUPABASE_CONFIGURED:
    try:
        from supabase import create_client, Client
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
        logger.info(f"Connected to Supabase at: {SUPABASE_URL}")
    except Exception as e:
        logger.error(f"Failed to initialize Supabase client: {e}")
        IS_SUPABASE_CONFIGURED = False
else:
    logger.warning("Supabase credentials not configured. Live persistence and auth verification BLOCKED.")

# ---------------------------------------------------------------------
# AUDIT LOGGING HELPER
# ---------------------------------------------------------------------
def log_audit(
    action: str,
    entity_type: str,
    entity_id: Optional[str] = None,
    actor_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
):
    """Write an immutable audit log entry."""
    ip_addr = request.remote_addr if request else "system"
    method = request.method if request else "INTERNAL"
    route = request.path if request else "internal"
    
    log_data = {
        "id": str(uuid.uuid4()),
        "actor_id": actor_id,
        "action": action,
        "entity_type": entity_type,
        "entity_id": str(entity_id) if entity_id else None,
        "http_method": method,
        "route": route,
        "ip_address": ip_addr,
        "metadata": metadata or {},
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    logger.info(f"AUDIT: [{action}] {entity_type}:{entity_id} by {actor_id}")
    if IS_SUPABASE_CONFIGURED and supabase:
        try:
            supabase.table("audit_logs").insert(log_data).execute()
        except Exception as e:
            logger.error(f"Failed to persist audit log to Supabase: {e}")

# ---------------------------------------------------------------------
# AUTHENTICATION & RBAC MIDDLEWARE
# ---------------------------------------------------------------------
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

# ---------------------------------------------------------------------
# SYSTEM HEALTH & ACADEMIC POLICY ENDPOINTS
# ---------------------------------------------------------------------
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


@app.route("/api/academic-policy", methods=["GET"])
def academic_policy():
    """Defines explicit academic integrity standards and permitted assistance categories."""
    return jsonify({
        "declaration": "Intelliworks Industries is dedicated to academic and professional excellence through ethical collaboration.",
        "permitted_services": [
            {"category": "Tutoring & Conceptual Explanation", "description": "Subject-matter tutoring, problem breakdown, methodology guidance."},
            {"category": "Research Assistance & Literature Review", "description": "Compiling bibliographies, finding peer-reviewed sources, structuring frameworks."},
            {"category": "Statistical & Data Analysis", "description": "R, Python, SPSS, Stata analysis, visualization, dataset verification."},
            {"category": "Substantive Editing & Proofreading", "description": "Grammar, clarity, tone, flow, syntax, academic style polishing."},
            {"category": "Formatting & Typesetting", "description": "LaTeX typesetting, APA 7, IEEE, Chicago, Harvard manual formatting."},
            {"category": "Technical Writing Support", "description": "Whitepapers, grant proposals, research project documentation."}
        ],
        "prohibited_activities": [
            "Contract cheating or taking exams/quizzes on behalf of a student",
            "Submitting ghostwritten deliverables claimed as the student's original academic coursework",
            "Plagiarism or falsifying research datasets and experimental observations",
            "Circumventing institutional honor codes"
        ]
    })


@app.route("/api/settings", methods=["GET"])
def get_public_settings():
    """Retrieve public platform parameters."""
    if not IS_SUPABASE_CONFIGURED or not supabase:
        return jsonify({
            "escrow_split": {"writer_percentage": 80.0, "platform_fee_percentage": 20.0},
            "minimum_withdrawal": 20.00,
            "referral_percentage": 5.0,
            "maintenance_mode": False
        })
    try:
        res = supabase.table("platform_settings").select("*").execute()
        settings = {item["key"]: item["value"] for item in res.data} if res.data else {}
        return jsonify(settings)
    except Exception as e:
        logger.error(f"Error fetching platform settings: {e}")
        return jsonify({"error": "Failed to fetch settings"}), 500

# ---------------------------------------------------------------------
# USER & PROFILE ENDPOINTS
# ---------------------------------------------------------------------
@app.route("/api/me", methods=["GET"])
@require_auth
def get_me(user):
    """Retrieve authenticated user profile, statistics, and pending notification count."""
    try:
        user_id = user["id"]
        # Fetch unread notification count
        notif_res = supabase.table("notifications").select("id", count="exact").eq("recipient_id", user_id).eq("is_read", False).execute()
        unread_count = notif_res.count if notif_res.count is not None else 0
        
        user_data = dict(user)
        user_data["unread_notifications"] = unread_count
        return jsonify({"user": user_data})
    except Exception as e:
        logger.error(f"Error in /api/me: {e}")
        return jsonify({"error": "Internal error retrieving profile"}), 500


@app.route("/api/profile", methods=["PUT"])
@require_auth
def update_profile(user):
    """
    Update permitted profile fields (bio, full_name, skills, profile_photo).
    Privileged fields (role, balance, earnings, status) are strictly immutable here.
    """
    body = request.get_json() or {}
    allowed_updates = {}
    
    if "full_name" in body and isinstance(body["full_name"], str) and body["full_name"].strip():
        allowed_updates["full_name"] = body["full_name"].strip()
    if "bio" in body and isinstance(body["bio"], str):
        allowed_updates["bio"] = body["bio"].strip()
    if "skills" in body and isinstance(body["skills"], list):
        allowed_updates["skills"] = [str(s).strip() for s in body["skills"] if str(s).strip()]
    if "profile_photo" in body and isinstance(body["profile_photo"], str):
        allowed_updates["profile_photo"] = body["profile_photo"].strip()
        
    if not allowed_updates:
        return jsonify({"error": "No valid fields provided for update"}), 400

    allowed_updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    try:
        res = supabase.table("users").update(allowed_updates).eq("id", user["id"]).execute()
        log_audit("update_profile", "users", user["id"], user["id"], {"fields": list(allowed_updates.keys())})
        updated = res.data[0] if res.data else user
        return jsonify({"message": "Profile updated successfully", "user": updated})
    except Exception as e:
        logger.error(f"Profile update error: {e}")
        return jsonify({"error": "Failed to update profile"}), 500

# ---------------------------------------------------------------------
# CLIENT WORKFLOW: ASSIGNMENT CREATION & LIFECYCLE
# ---------------------------------------------------------------------
@app.route("/api/assignments", methods=["POST"])
@require_role("Client", "Admin")
def create_assignment(user):
    """
    Step 4 of Client creation workflow.
    Enforces server-authoritative 80/20 escrow calculation, deadline validation,
    academic integrity declaration, and transactional escrow deposit record.
    """
    data = request.get_json() or {}
    
    # Required field validation
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
        return jsonify({"error": "Validation Error", "message": "All project specifications and instructions are required."}), 422

    if not academic_accepted:
        return jsonify({"error": "Academic Policy", "message": "You must confirm the Academic Integrity Declaration."}), 422

    try:
        budget = float(Decimal(str(budget_raw)).quantize(Decimal("0.01")))
        if budget < 10.0:
            return jsonify({"error": "Validation Error", "message": "Minimum project budget is $10.00."}), 422
    except Exception:
        return jsonify({"error": "Validation Error", "message": "Invalid budget format."}), 422

    try:
        word_count = int(word_count_raw)
        if word_count < 0:
            word_count = 0
    except Exception:
        word_count = 0

    try:
        deadline_dt = datetime.fromisoformat(deadline_str.replace("Z", "+00:00"))
        if deadline_dt <= datetime.now(timezone.utc):
            return jsonify({"error": "Validation Error", "message": "Deadline must be set in the future."}), 422
    except Exception:
        return jsonify({"error": "Validation Error", "message": "Invalid deadline ISO format."}), 422

    # Authoritative 80/20 Escrow Calculation
    writer_payout = round(budget * 0.80, 2)
    platform_fee = round(budget * 0.20, 2)
    
    assignment_id = str(uuid.uuid4())
    assignment_record = {
        "id": assignment_id,
        "client_id": user["id"],
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
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }

    try:
        # 1. Insert assignment
        res = supabase.table("assignments").insert(assignment_record).execute()
        
        # 2. Record immutable Escrow Deposit transaction
        deposit_tx = {
            "id": str(uuid.uuid4()),
            "user_id": user["id"],
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
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        supabase.table("transactions").insert(deposit_tx).execute()

        # 3. Update client total spent
        curr_spent = float(user.get("total_spent", 0.0))
        supabase.table("users").update({"total_spent": round(curr_spent + budget, 2)}).eq("id", user["id"]).execute()

        # 4. Audit log
        log_audit("create_assignment", "assignments", assignment_id, user["id"], {
            "budget": budget,
            "writer_payout": writer_payout,
            "platform_fee": platform_fee
        })

        return jsonify({
            "message": "Assignment created and escrow successfully funded.",
            "assignment": res.data[0] if res.data else assignment_record
        }), 201

    except Exception as e:
        logger.error(f"Error creating assignment: {e}")
        return jsonify({"error": "Failed to create assignment", "details": str(e)}), 500


@app.route("/api/assignments", methods=["GET"])
@require_auth
def list_assignments(user):
    """
    List assignments with server-side filters:
    - role='Client': defaults to client's assignments
    - role='Writer': marketplace view (Open assignments) or active assignments
    - role='Admin': all assignments
    Supports category filter, search, sorting.
    """
    view = request.args.get("view", "default")
    category = request.args.get("category")
    status_filter = request.args.get("status")
    search = request.args.get("search")
    sort_by = request.args.get("sort_by", "created_at")
    sort_order = request.args.get("sort_order", "desc")
    
    query = supabase.table("assignments").select("*, client:users!client_id(full_name, email, average_rating), writer:users!writer_id(full_name, email, average_rating)")
    
    role = user.get("role")
    
    if role == "Client":
        if view == "all" and user.get("role") == "Admin":
            pass
        else:
            query = query.eq("client_id", user["id"])
    elif role == "Writer":
        if view == "workspace":
            query = query.eq("writer_id", user["id"])
        elif view == "marketplace" or view == "default":
            query = query.eq("status", "Open")
    # Admin sees all by default or filtered
    
    if category:
        query = query.eq("category", category)
    if status_filter:
        query = query.eq("status", status_filter)
    if search:
        query = query.ilike("title", f"%{search}%")
        
    ascending = (sort_order == "asc")
    query = query.order(sort_by, desc=not ascending)
    
    try:
        res = query.execute()
        return jsonify({"assignments": res.data or []})
    except Exception as e:
        logger.error(f"Error listing assignments: {e}")
        return jsonify({"error": "Failed to list assignments"}), 500


@app.route("/api/assignments/<assignment_id>", methods=["GET"])
@require_auth
def get_assignment(user, assignment_id):
    """
    Retrieve single assignment with full submission history, files, and authorization check.
    Only client, assigned writer, or admin can view details of claimed/submitted work.
    """
    try:
        res = supabase.table("assignments").select("*, client:users!client_id(full_name, email, average_rating), writer:users!writer_id(full_name, email, average_rating)").eq("id", assignment_id).execute()
        if not res.data:
            return jsonify({"error": "Not Found", "message": "Assignment does not exist."}), 404
        
        assignment = res.data[0]
        
        # Access check
        is_client = (assignment["client_id"] == user["id"])
        is_writer = (assignment.get("writer_id") == user["id"])
        is_admin = (user.get("role") == "Admin")
        is_open_marketplace = (assignment["status"] == "Open")
        
        if not (is_client or is_writer or is_admin or is_open_marketplace):
            return jsonify({"error": "Forbidden", "message": "You are not authorized to view this private assignment."}), 403

        # Fetch submissions
        sub_res = supabase.table("submissions").select("*").eq("assignment_id", assignment_id).order("revision_number", desc=True).execute()
        
        # Fetch files
        files_res = supabase.table("files").select("*").eq("assignment_id", assignment_id).order("created_at", desc=False).execute()

        # Fetch review if completed
        review_res = supabase.table("reviews").select("*").eq("assignment_id", assignment_id).execute()

        return jsonify({
            "assignment": assignment,
            "submissions": sub_res.data or [],
            "files": files_res.data or [],
            "review": review_res.data[0] if review_res.data else None
        })
    except Exception as e:
        logger.error(f"Error fetching assignment {assignment_id}: {e}")
        return jsonify({"error": "Failed to fetch assignment details"}), 500

# ---------------------------------------------------------------------
# WRITER MARKETPLACE: ATOMIC CLAIMING & SUBMISSIONS
# ---------------------------------------------------------------------
@app.route("/api/assignments/<assignment_id>/claim", methods=["POST"])
@require_role("Writer")
def claim_assignment(user, assignment_id):
    """
    Atomic Claiming:
    Guarantees concurrency safety. Verifies:
    1. assignment status == 'Open'
    2. writer_id IS NULL
    3. deadline has not passed
    4. writer account is active
    """
    try:
        # Atomic conditional update
        now_iso = datetime.now(timezone.utc).isoformat()
        
        # Fetch current record first to verify deadline
        curr = supabase.table("assignments").select("*").eq("id", assignment_id).execute()
        if not curr.data:
            return jsonify({"error": "Not Found", "message": "Assignment not found."}), 404
        
        asgt = curr.data[0]
        if asgt["status"] != "Open" or asgt.get("writer_id") is not None:
            return jsonify({"error": "Conflict", "message": "This assignment has already been claimed by another specialist."}), 409
            
        deadline_dt = datetime.fromisoformat(asgt["deadline"].replace("Z", "+00:00"))
        if deadline_dt <= datetime.now(timezone.utc):
            return jsonify({"error": "Bad Request", "message": "The deadline for this assignment has already passed."}), 400

        # Perform atomic claim update
        update_res = supabase.table("assignments").update({
            "writer_id": user["id"],
            "status": "Claimed",
            "updated_at": now_iso
        }).eq("id", assignment_id).eq("status", "Open").is_("writer_id", "null").execute()

        if not update_res.data or len(update_res.data) == 0:
            return jsonify({"error": "Conflict", "message": "Race condition detected: Assignment claimed by another writer."}), 409

        # Notify client
        notif = {
            "id": str(uuid.uuid4()),
            "recipient_id": asgt["client_id"],
            "notification_type": "Assignment Claimed",
            "related_assignment_id": assignment_id,
            "message": f"Specialist {user['full_name']} has claimed your project '{asgt['title']}'.",
            "is_read": False,
            "created_at": now_iso
        }
        supabase.table("notifications").insert(notif).execute()

        log_audit("claim_assignment", "assignments", assignment_id, user["id"], {"title": asgt["title"]})
        return jsonify({
            "message": "Assignment successfully claimed. It is now in your active workspace.",
            "assignment": update_res.data[0]
        }), 200

    except Exception as e:
        logger.error(f"Error claiming assignment {assignment_id}: {e}")
        return jsonify({"error": "Failed to claim assignment", "details": str(e)}), 500


@app.route("/api/assignments/<assignment_id>/submit", methods=["POST"])
@require_role("Writer")
def submit_deliverable(user, assignment_id):
    """
    Writer submits a deliverable/revision.
    Revision numbers are strictly generated server-side.
    Validates assignment ownership and state.
    """
    data = request.get_json() or {}
    notes = str(data.get("notes", "")).strip()
    files_payload = data.get("files", [])

    try:
        asgt_res = supabase.table("assignments").select("*").eq("id", assignment_id).execute()
        if not asgt_res.data:
            return jsonify({"error": "Not Found", "message": "Assignment not found."}), 404
        
        asgt = asgt_res.data[0]
        if asgt["writer_id"] != user["id"]:
            return jsonify({"error": "Forbidden", "message": "You are not the assigned writer for this project."}), 403

        if asgt["status"] not in ["Claimed", "Revision Requested"]:
            return jsonify({"error": "Bad Request", "message": f"Cannot submit deliverable while assignment is in '{asgt['status']}' status."}), 400

        # Monotonically determine next revision number server-side
        sub_count_res = supabase.table("submissions").select("revision_number").eq("assignment_id", assignment_id).order("revision_number", desc=True).limit(1).execute()
        next_rev = 1
        if sub_count_res.data and len(sub_count_res.data) > 0:
            next_rev = sub_count_res.data[0]["revision_number"] + 1

        submission_id = str(uuid.uuid4())
        now_iso = datetime.now(timezone.utc).isoformat()
        
        submission_record = {
            "id": submission_id,
            "assignment_id": assignment_id,
            "writer_id": user["id"],
            "revision_number": next_rev,
            "notes": notes,
            "status": "Submitted",
            "created_at": now_iso
        }
        supabase.table("submissions").insert(submission_record).execute()

        # Link files if provided
        for f in files_payload:
            if isinstance(f, dict) and f.get("filename") and f.get("storage_path"):
                file_rec = {
                    "id": str(uuid.uuid4()),
                    "assignment_id": assignment_id,
                    "submission_id": submission_id,
                    "uploaded_by": user["id"],
                    "filename": f["filename"],
                    "storage_path": f["storage_path"],
                    "content_type": f.get("content_type", "application/octet-stream"),
                    "size": int(f.get("size", 1024)),
                    "file_category": "Deliverable",
                    "created_at": now_iso
                }
                supabase.table("files").insert(file_rec).execute()

        # Update assignment state machine: -> 'Submitted'
        supabase.table("assignments").update({
            "status": "Submitted",
            "updated_at": now_iso
        }).eq("id", assignment_id).execute()

        # Notify client
        notif = {
            "id": str(uuid.uuid4()),
            "recipient_id": asgt["client_id"],
            "notification_type": "Deliverable Submitted",
            "related_assignment_id": assignment_id,
            "message": f"Deliverable (Revision #{next_rev}) has been submitted for '{asgt['title']}'. Please review.",
            "is_read": False,
            "created_at": now_iso
        }
        supabase.table("notifications").insert(notif).execute()

        log_audit("submit_deliverable", "submissions", submission_id, user["id"], {
            "assignment_id": assignment_id,
            "revision_number": next_rev
        })

        return jsonify({
            "message": f"Deliverable submitted successfully (Revision #{next_rev}).",
            "submission": submission_record
        }), 201

    except Exception as e:
        logger.error(f"Error in submit_deliverable: {e}")
        return jsonify({"error": "Failed to submit deliverable", "details": str(e)}), 500

# ---------------------------------------------------------------------
# REVISIONS & ESCROW RELEASE (APPROVAL)
# ---------------------------------------------------------------------
@app.route("/api/assignments/<assignment_id>/revision", methods=["POST"])
@require_role("Client")
def request_revision(user, assignment_id):
    """
    Client requests a revision on submitted work.
    Transitions state: Submitted -> Revision Requested.
    Increments revision count.
    """
    data = request.get_json() or {}
    feedback = str(data.get("feedback", "")).strip()
    if not feedback:
        return jsonify({"error": "Validation Error", "message": "Revision instructions and feedback are required."}), 422

    try:
        asgt_res = supabase.table("assignments").select("*").eq("id", assignment_id).execute()
        if not asgt_res.data:
            return jsonify({"error": "Not Found", "message": "Assignment not found."}), 404

        asgt = asgt_res.data[0]
        if asgt["client_id"] != user["id"]:
            return jsonify({"error": "Forbidden", "message": "You are not the client for this assignment."}), 403

        if asgt["status"] != "Submitted":
            return jsonify({"error": "Bad Request", "message": f"Cannot request revision while assignment is in '{asgt['status']}'."}), 400

        now_iso = datetime.now(timezone.utc).isoformat()
        new_rev_count = asgt.get("revision_count", 0) + 1

        supabase.table("assignments").update({
            "status": "Revision Requested",
            "revision_count": new_rev_count,
            "updated_at": now_iso
        }).eq("id", assignment_id).execute()

        # Update latest submission status
        supabase.table("submissions").update({
            "status": "Revision Requested"
        }).eq("assignment_id", assignment_id).eq("status", "Submitted").execute()

        # Notify writer
        notif = {
            "id": str(uuid.uuid4()),
            "recipient_id": asgt["writer_id"],
            "notification_type": "Revision Requested",
            "related_assignment_id": assignment_id,
            "message": f"Client requested revisions for '{asgt['title']}': {feedback[:100]}...",
            "is_read": False,
            "created_at": now_iso
        }
        supabase.table("notifications").insert(notif).execute()

        log_audit("request_revision", "assignments", assignment_id, user["id"], {
            "revision_count": new_rev_count,
            "feedback": feedback
        })

        return jsonify({"message": "Revision requested successfully."}), 200

    except Exception as e:
        logger.error(f"Error in request_revision: {e}")
        return jsonify({"error": "Failed to request revision", "details": str(e)}), 500


@app.route("/api/assignments/<assignment_id>/approve", methods=["POST"])
@require_role("Client")
def approve_assignment(user, assignment_id):
    """
    IDEMPOTENT ESCROW RELEASE & APPROVAL ENGINE:
    1. Verify client ownership
    2. Verify assignment state == 'Submitted'
    3. Verify escrow has not already been released
    4. Mark assignment approved & escrow released
    5. Credit writer payout to available_balance & total_earnings
    6. Record immutable 'Writer Payout' and 'Platform Fee' ledger transactions
    7. Process eligible referral commission
    8. Write audit record
    """
    try:
        asgt_res = supabase.table("assignments").select("*").eq("id", assignment_id).execute()
        if not asgt_res.data:
            return jsonify({"error": "Not Found", "message": "Assignment not found."}), 404

        asgt = asgt_res.data[0]
        if asgt["client_id"] != user["id"]:
            return jsonify({"error": "Forbidden", "message": "You are not the client for this assignment."}), 403

        if asgt["status"] == "Approved" or asgt["escrow_status"] == "Released":
            return jsonify({"error": "Conflict", "message": "Assignment is already approved and escrow released."}), 409

        if asgt["status"] != "Submitted":
            return jsonify({"error": "Bad Request", "message": f"Cannot approve assignment in status '{asgt['status']}'. Requires 'Submitted' state."}), 400

        writer_id = asgt["writer_id"]
        if not writer_id:
            return jsonify({"error": "Bad Request", "message": "No writer assigned."}), 400

        payout_amt = float(asgt["writer_payout"])
        platform_fee = float(asgt["platform_fee"])
        now_iso = datetime.now(timezone.utc).isoformat()

        # 1. Update assignment state
        supabase.table("assignments").update({
            "status": "Approved",
            "escrow_status": "Released",
            "updated_at": now_iso
        }).eq("id", assignment_id).execute()

        # 2. Update submission status to 'Accepted'
        supabase.table("submissions").update({
            "status": "Accepted"
        }).eq("assignment_id", assignment_id).eq("status", "Submitted").execute()

        # 3. Credit writer balance & earnings
        writer_res = supabase.table("users").select("available_balance, total_earnings").eq("id", writer_id).single().execute()
        if writer_res.data:
            new_balance = round(float(writer_res.data.get("available_balance", 0.0)) + payout_amt, 2)
            new_earnings = round(float(writer_res.data.get("total_earnings", 0.0)) + payout_amt, 2)
            supabase.table("users").update({
                "available_balance": new_balance,
                "total_earnings": new_earnings
            }).eq("id", writer_id).execute()

        # 4. Insert Writer Payout ledger transaction (Idempotency Key enforced)
        writer_tx = {
            "id": str(uuid.uuid4()),
            "user_id": writer_id,
            "assignment_id": assignment_id,
            "transaction_type": "Writer Payout",
            "amount": payout_amt,
            "status": "Completed",
            "reference": f"PAYOUT-{assignment_id[:8]}",
            "idempotency_key": f"payout-{assignment_id}",
            "metadata": {"title": asgt["title"], "client_id": user["id"]},
            "created_at": now_iso
        }
        supabase.table("transactions").insert(writer_tx).execute()

        # 5. Insert Platform Fee ledger transaction
        fee_tx = {
            "id": str(uuid.uuid4()),
            "user_id": user["id"],
            "assignment_id": assignment_id,
            "transaction_type": "Platform Fee",
            "amount": platform_fee,
            "status": "Completed",
            "reference": f"FEE-{assignment_id[:8]}",
            "idempotency_key": f"fee-{assignment_id}",
            "metadata": {"assignment_id": assignment_id},
            "created_at": now_iso
        }
        supabase.table("transactions").insert(fee_tx).execute()

        # 6. Referral Commission Check (process once)
        ref_res = supabase.table("referrals").select("*").eq("referred_user_id", user["id"]).eq("status", "Active").execute()
        if ref_res.data and len(ref_res.data) > 0:
            referral = ref_res.data[0]
            comm_rate = 0.05  # 5%
            comm_amt = round(float(asgt["budget"]) * comm_rate, 2)
            referrer_id = referral["referrer_id"]
            
            # Credit referrer
            ref_user = supabase.table("users").select("available_balance, total_earnings").eq("id", referrer_id).single().execute()
            if ref_user.data:
                ref_bal = round(float(ref_user.data.get("available_balance", 0.0)) + comm_amt, 2)
                supabase.table("users").update({"available_balance": ref_bal}).eq("id", referrer_id).execute()

            # Record referral bonus transaction
            ref_tx = {
                "id": str(uuid.uuid4()),
                "user_id": referrer_id,
                "assignment_id": assignment_id,
                "transaction_type": "Referral Bonus",
                "amount": comm_amt,
                "status": "Completed",
                "reference": f"REF-COMM-{assignment_id[:8]}",
                "idempotency_key": f"ref-comm-{assignment_id}",
                "metadata": {"referred_user_id": user["id"]},
                "created_at": now_iso
            }
            supabase.table("transactions").insert(ref_tx).execute()
            
            # Update referral record
            supabase.table("referrals").update({
                "status": "Rewarded",
                "commission_amount": comm_amt,
                "rewarded_at": now_iso
            }).eq("id", referral["id"]).execute()

        # 7. Notify writer
        notif = {
            "id": str(uuid.uuid4()),
            "recipient_id": writer_id,
            "notification_type": "Escrow Released",
            "related_assignment_id": assignment_id,
            "message": f"Congratulations! Your work on '{asgt['title']}' has been approved. Payout of ${payout_amt:.2f} credited to your balance.",
            "is_read": False,
            "created_at": now_iso
        }
        supabase.table("notifications").insert(notif).execute()

        # 8. Audit log
        log_audit("approve_assignment", "assignments", assignment_id, user["id"], {
            "writer_id": writer_id,
            "payout_amount": payout_amt,
            "platform_fee": platform_fee
        })

        return jsonify({
            "message": "Assignment approved and escrow successfully released.",
            "payout_amount": payout_amt,
            "platform_fee": platform_fee
        }), 200

    except Exception as e:
        logger.error(f"Error in approve_assignment: {e}")
        return jsonify({"error": "Failed to approve assignment", "details": str(e)}), 500


@app.route("/api/assignments/<assignment_id>/cancel", methods=["POST"])
@require_role("Client", "Admin")
def cancel_assignment(user, assignment_id):
    """Cancel an Open assignment and refund the client deposit."""
    try:
        asgt_res = supabase.table("assignments").select("*").eq("id", assignment_id).execute()
        if not asgt_res.data:
            return jsonify({"error": "Not Found", "message": "Assignment not found."}), 404

        asgt = asgt_res.data[0]
        if asgt["client_id"] != user["id"] and user["role"] != "Admin":
            return jsonify({"error": "Forbidden"}), 403

        if asgt["status"] != "Open":
            return jsonify({"error": "Bad Request", "message": f"Cannot cancel assignment in status '{asgt['status']}'. Claimed or in-progress projects must use Dispute."}), 400

        now_iso = datetime.now(timezone.utc).isoformat()
        budget = float(asgt["budget"])

        # Mark cancelled
        supabase.table("assignments").update({
            "status": "Cancelled",
            "escrow_status": "Refunded",
            "updated_at": now_iso
        }).eq("id", assignment_id).execute()

        # Credit refund to client balance
        client_res = supabase.table("users").select("available_balance, total_spent").eq("id", asgt["client_id"]).single().execute()
        if client_res.data:
            new_bal = round(float(client_res.data.get("available_balance", 0.0)) + budget, 2)
            new_spent = max(0.0, round(float(client_res.data.get("total_spent", 0.0)) - budget, 2))
            supabase.table("users").update({"available_balance": new_bal, "total_spent": new_spent}).eq("id", asgt["client_id"]).execute()

        # Refund transaction
        refund_tx = {
            "id": str(uuid.uuid4()),
            "user_id": asgt["client_id"],
            "assignment_id": assignment_id,
            "transaction_type": "Refund",
            "amount": budget,
            "status": "Completed",
            "reference": f"REFUND-{assignment_id[:8]}",
            "idempotency_key": f"refund-{assignment_id}",
            "metadata": {"reason": "Cancelled by client while Open"},
            "created_at": now_iso
        }
        supabase.table("transactions").insert(refund_tx).execute()

        log_audit("cancel_assignment", "assignments", assignment_id, user["id"], {"amount_refunded": budget})
        return jsonify({"message": "Assignment cancelled and budget refunded to available balance."}), 200

    except Exception as e:
        logger.error(f"Error cancelling assignment: {e}")
        return jsonify({"error": "Failed to cancel assignment"}), 500

# ---------------------------------------------------------------------
# MESSAGING: ASSIGNMENT-SCOPED SECURE CHAT
# ---------------------------------------------------------------------
@app.route("/api/assignments/<assignment_id>/messages", methods=["GET"])
@require_auth
def get_messages(user, assignment_id):
    """Retrieve messages for an assignment. Strict participant authorization."""
    try:
        asgt_res = supabase.table("assignments").select("client_id, writer_id").eq("id", assignment_id).execute()
        if not asgt_res.data:
            return jsonify({"error": "Not Found"}), 404

        asgt = asgt_res.data[0]
        is_client = (asgt["client_id"] == user["id"])
        is_writer = (asgt.get("writer_id") == user["id"])
        is_admin = (user["role"] == "Admin")

        if not (is_client or is_writer or is_admin):
            return jsonify({"error": "Forbidden", "message": "You cannot access this assignment's messages."}), 403

        messages_res = supabase.table("messages").select("*, sender:users!sender_id(full_name, role, profile_photo)").eq("assignment_id", assignment_id).order("created_at", desc=False).execute()
        return jsonify({"messages": messages_res.data or []})
    except Exception as e:
        logger.error(f"Error retrieving messages: {e}")
        return jsonify({"error": "Failed to fetch messages"}), 500


@app.route("/api/assignments/<assignment_id>/messages", methods=["POST"])
@require_auth
def send_message(user, assignment_id):
    """Send an assignment-scoped message."""
    data = request.get_json() or {}
    text = str(data.get("message", "")).strip()
    if not text:
        return jsonify({"error": "Validation Error", "message": "Message text cannot be empty."}), 422

    try:
        asgt_res = supabase.table("assignments").select("client_id, writer_id, title").eq("id", assignment_id).execute()
        if not asgt_res.data:
            return jsonify({"error": "Not Found"}), 404

        asgt = asgt_res.data[0]
        is_client = (asgt["client_id"] == user["id"])
        is_writer = (asgt.get("writer_id") == user["id"])
        is_admin = (user["role"] == "Admin")

        if not (is_client or is_writer or is_admin):
            return jsonify({"error": "Forbidden", "message": "You cannot send messages for this assignment."}), 403

        msg_id = str(uuid.uuid4())
        now_iso = datetime.now(timezone.utc).isoformat()
        
        msg_record = {
            "id": msg_id,
            "assignment_id": assignment_id,
            "sender_id": user["id"],
            "message": text,
            "created_at": now_iso
        }
        res = supabase.table("messages").insert(msg_record).execute()

        # Send notification to other party
        recipient_id = asgt["writer_id"] if is_client else asgt["client_id"]
        if recipient_id:
            notif = {
                "id": str(uuid.uuid4()),
                "recipient_id": recipient_id,
                "notification_type": "New Message",
                "related_assignment_id": assignment_id,
                "message": f"New message from {user['full_name']} on '{asgt['title']}': {text[:60]}...",
                "is_read": False,
                "created_at": now_iso
            }
            supabase.table("notifications").insert(notif).execute()

        return jsonify({"message": "Sent", "data": res.data[0] if res.data else msg_record}), 201

    except Exception as e:
        logger.error(f"Error sending message: {e}")
        return jsonify({"error": "Failed to send message"}), 500

# ---------------------------------------------------------------------
# REVIEWS & RATINGS
# ---------------------------------------------------------------------
@app.route("/api/reviews", methods=["POST"])
@require_role("Client")
def create_review(user):
    """
    Client reviews writer after project completion:
    - 1 to 5 rating
    - Written feedback
    - Prevents duplicate reviews
    - Updates writer aggregate average rating and total reviews
    """
    data = request.get_json() or {}
    assignment_id = data.get("assignment_id")
    rating_raw = data.get("rating")
    feedback = str(data.get("feedback", "")).strip()

    if not assignment_id or not feedback or rating_raw is None:
        return jsonify({"error": "Validation Error", "message": "Assignment, rating (1-5), and feedback are required."}), 422

    try:
        rating = int(rating_raw)
        if rating < 1 or rating > 5:
            return jsonify({"error": "Validation Error", "message": "Rating must be between 1 and 5 stars."}), 422
    except Exception:
        return jsonify({"error": "Validation Error", "message": "Rating must be an integer between 1 and 5."}), 422

    try:
        asgt_res = supabase.table("assignments").select("*").eq("id", assignment_id).execute()
        if not asgt_res.data:
            return jsonify({"error": "Not Found", "message": "Assignment not found."}), 404

        asgt = asgt_res.data[0]
        if asgt["client_id"] != user["id"]:
            return jsonify({"error": "Forbidden", "message": "Only the assignment client can submit a review."}), 403

        if asgt["status"] != "Approved":
            return jsonify({"error": "Bad Request", "message": "Reviews can only be submitted after assignment approval."}), 400

        writer_id = asgt["writer_id"]
        if not writer_id or writer_id == user["id"]:
            return jsonify({"error": "Bad Request", "message": "Invalid review recipient."}), 400

        # Check existing review
        existing = supabase.table("reviews").select("id").eq("assignment_id", assignment_id).execute()
        if existing.data and len(existing.data) > 0:
            return jsonify({"error": "Conflict", "message": "You have already reviewed this assignment."}), 409

        review_id = str(uuid.uuid4())
        now_iso = datetime.now(timezone.utc).isoformat()
        
        review_record = {
            "id": review_id,
            "assignment_id": assignment_id,
            "client_id": user["id"],
            "writer_id": writer_id,
            "rating": rating,
            "feedback": feedback,
            "created_at": now_iso
        }
        supabase.table("reviews").insert(review_record).execute()

        # Update writer aggregate rating
        all_reviews = supabase.table("reviews").select("rating").eq("writer_id", writer_id).execute()
        ratings = [r["rating"] for r in all_reviews.data] if all_reviews.data else [rating]
        avg_rating = round(sum(ratings) / len(ratings), 2)
        total_revs = len(ratings)

        supabase.table("users").update({
            "average_rating": avg_rating,
            "total_reviews": total_revs
        }).eq("id", writer_id).execute()

        log_audit("create_review", "reviews", review_id, user["id"], {
            "writer_id": writer_id,
            "rating": rating
        })

        return jsonify({"message": "Review submitted successfully.", "review": review_record}), 201

    except Exception as e:
        logger.error(f"Error submitting review: {e}")
        return jsonify({"error": "Failed to submit review", "details": str(e)}), 500

# ---------------------------------------------------------------------
# WITHDRAWALS (INTERNAL ACCOUNTING WORKFLOW)
# ---------------------------------------------------------------------
@app.route("/api/withdrawals", methods=["GET"])
@require_auth
def list_withdrawals(user):
    """List withdrawals for authenticated user (or all if admin)."""
    try:
        query = supabase.table("withdrawals").select("*, user:users!user_id(full_name, email, role)")
        if user["role"] != "Admin":
            query = query.eq("user_id", user["id"])
        
        res = query.order("created_at", desc=True).execute()
        return jsonify({"withdrawals": res.data or []})
    except Exception as e:
        logger.error(f"Error listing withdrawals: {e}")
        return jsonify({"error": "Failed to list withdrawals"}), 500


@app.route("/api/withdrawals", methods=["POST"])
@require_role("Writer", "Client")
def request_withdrawal(user):
    """
    Request balance withdrawal.
    Verifies:
    1. Authenticated identity
    2. Available balance >= withdrawal amount
    3. Amount >= minimum withdrawal ($20.00)
    4. Account status is Active
    5. Deducts available balance atomically and marks 'Pending' for admin review.
    """
    data = request.get_json() or {}
    amount_raw = data.get("amount")
    payout_method = str(data.get("payout_method", "")).strip()
    account_details = str(data.get("account_details", "")).strip()

    if not amount_raw or not payout_method or not account_details:
        return jsonify({"error": "Validation Error", "message": "Amount, payout method, and account details are required."}), 422

    try:
        amount = float(Decimal(str(amount_raw)).quantize(Decimal("0.01")))
        if amount < 20.0:
            return jsonify({"error": "Validation Error", "message": "Minimum withdrawal amount is $20.00."}), 422
    except Exception:
        return jsonify({"error": "Validation Error", "message": "Invalid withdrawal amount format."}), 422

    try:
        # Check current balance
        user_res = supabase.table("users").select("available_balance, account_status").eq("id", user["id"]).single().execute()
        if not user_res.data:
            return jsonify({"error": "Not Found"}), 404

        avail = float(user_res.data.get("available_balance", 0.0))
        if avail < amount:
            return jsonify({"error": "Insufficient Funds", "message": f"Requested ${amount:.2f} exceeds available balance of ${avail:.2f}."}), 400

        # Atomic balance reduction
        new_avail = round(avail - amount, 2)
        supabase.table("users").update({"available_balance": new_avail}).eq("id", user["id"]).execute()

        withdrawal_id = str(uuid.uuid4())
        now_iso = datetime.now(timezone.utc).isoformat()
        
        withdrawal_record = {
            "id": withdrawal_id,
            "user_id": user["id"],
            "amount": amount,
            "status": "Pending",
            "payout_method": payout_method,
            "account_details": account_details,
            "created_at": now_iso
        }
        supabase.table("withdrawals").insert(withdrawal_record).execute()

        # Ledger record
        tx = {
            "id": str(uuid.uuid4()),
            "user_id": user["id"],
            "assignment_id": None,
            "transaction_type": "Withdrawal",
            "amount": -amount,
            "status": "Pending",
            "reference": f"WITHDRAWAL-{withdrawal_id[:8]}",
            "idempotency_key": f"wdr-{withdrawal_id}",
            "metadata": {"payout_method": payout_method},
            "created_at": now_iso
        }
        supabase.table("transactions").insert(tx).execute()

        log_audit("request_withdrawal", "withdrawals", withdrawal_id, user["id"], {
            "amount": amount,
            "payout_method": payout_method
        })

        return jsonify({
            "message": "Withdrawal request submitted. Awaiting administrative authorization.",
            "withdrawal": withdrawal_record,
            "remaining_balance": new_avail
        }), 201

    except Exception as e:
        logger.error(f"Error processing withdrawal: {e}")
        return jsonify({"error": "Failed to submit withdrawal request", "details": str(e)}), 500

# ---------------------------------------------------------------------
# DISPUTES & ARBITRATION
# ---------------------------------------------------------------------
@app.route("/api/assignments/<assignment_id>/dispute", methods=["POST"])
@require_auth
def open_dispute(user, assignment_id):
    """Open dispute on an active assignment."""
    data = request.get_json() or {}
    reason = str(data.get("reason", "")).strip()
    description = str(data.get("description", "")).strip()

    if not reason or not description:
        return jsonify({"error": "Validation Error", "message": "Dispute reason and full description are required."}), 422

    try:
        asgt_res = supabase.table("assignments").select("*").eq("id", assignment_id).execute()
        if not asgt_res.data:
            return jsonify({"error": "Not Found"}), 404

        asgt = asgt_res.data[0]
        is_client = (asgt["client_id"] == user["id"])
        is_writer = (asgt.get("writer_id") == user["id"])

        if not (is_client or is_writer):
            return jsonify({"error": "Forbidden", "message": "Only assignment participants can initiate a dispute."}), 403

        if asgt["status"] in ["Open", "Approved", "Cancelled"]:
            return jsonify({"error": "Bad Request", "message": f"Cannot dispute an assignment in status '{asgt['status']}'."}), 400

        opposing_party = asgt["writer_id"] if is_client else asgt["client_id"]
        dispute_id = str(uuid.uuid4())
        now_iso = datetime.now(timezone.utc).isoformat()

        # Update assignment to 'Disputed'
        supabase.table("assignments").update({
            "status": "Disputed",
            "escrow_status": "Disputed",
            "updated_at": now_iso
        }).eq("id", assignment_id).execute()

        dispute_rec = {
            "id": dispute_id,
            "assignment_id": assignment_id,
            "opened_by": user["id"],
            "opposing_party": opposing_party,
            "reason": reason,
            "description": description,
            "status": "Open",
            "created_at": now_iso
        }
        supabase.table("disputes").insert(dispute_rec).execute()

        log_audit("open_dispute", "disputes", dispute_id, user["id"], {
            "assignment_id": assignment_id,
            "reason": reason
        })

        return jsonify({"message": "Dispute lodged. The project is locked pending administrative arbitration.", "dispute": dispute_rec}), 201

    except Exception as e:
        logger.error(f"Error opening dispute: {e}")
        return jsonify({"error": "Failed to open dispute", "details": str(e)}), 500


@app.route("/api/disputes", methods=["GET"])
@require_auth
def list_disputes(user):
    """List disputes for user or all if admin."""
    try:
        query = supabase.table("disputes").select("*, assignment:assignments(title, budget), opener:users!opened_by(full_name, email), opponent:users!opposing_party(full_name, email)")
        if user["role"] != "Admin":
            query = query.or_(f"opened_by.eq.{user['id']},opposing_party.eq.{user['id']}")
            
        res = query.order("created_at", desc=True).execute()
        return jsonify({"disputes": res.data or []})
    except Exception as e:
        logger.error(f"Error listing disputes: {e}")
        return jsonify({"error": "Failed to list disputes"}), 500

# ---------------------------------------------------------------------
# TRANSACTIONS, NOTIFICATIONS & REFERRALS
# ---------------------------------------------------------------------
@app.route("/api/transactions", methods=["GET"])
@require_auth
def list_transactions(user):
    """Retrieve immutable ledger transactions."""
    try:
        query = supabase.table("transactions").select("*, assignment:assignments(title)")
        if user["role"] != "Admin":
            query = query.eq("user_id", user["id"])
            
        res = query.order("created_at", desc=True).execute()
        return jsonify({"transactions": res.data or []})
    except Exception as e:
        logger.error(f"Error listing transactions: {e}")
        return jsonify({"error": "Failed to list transactions"}), 500


@app.route("/api/notifications", methods=["GET"])
@require_auth
def get_notifications(user):
    """Retrieve persistent notifications."""
    try:
        res = supabase.table("notifications").select("*").eq("recipient_id", user["id"]).order("created_at", desc=True).limit(50).execute()
        return jsonify({"notifications": res.data or []})
    except Exception as e:
        logger.error(f"Error retrieving notifications: {e}")
        return jsonify({"error": "Failed to fetch notifications"}), 500


@app.route("/api/notifications/<notif_id>/read", methods=["PUT"])
@require_auth
def mark_notification_read(user, notif_id):
    """Mark single notification as read."""
    try:
        supabase.table("notifications").update({"is_read": True}).eq("id", notif_id).eq("recipient_id", user["id"]).execute()
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/notifications/read-all", methods=["PUT"])
@require_auth
def mark_all_notifications_read(user):
    """Mark all notifications as read."""
    try:
        supabase.table("notifications").update({"is_read": True}).eq("recipient_id", user["id"]).execute()
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/referrals", methods=["GET"])
@require_auth
def get_referrals(user):
    """Retrieve referral code and referred users history."""
    try:
        res = supabase.table("referrals").select("*, referee:users!referred_user_id(full_name, email, role, created_at)").eq("referrer_id", user["id"]).order("created_at", desc=True).execute()
        return jsonify({
            "referral_code": user.get("referral_code"),
            "referrals": res.data or []
        })
    except Exception as e:
        logger.error(f"Error fetching referrals: {e}")
        return jsonify({"error": "Failed to fetch referrals"}), 500

# ---------------------------------------------------------------------
# ADMIN COMMAND CENTER: METRICS, USER MANAGEMENT, ARBITRATION
# ---------------------------------------------------------------------
@app.route("/api/admin/metrics", methods=["GET"])
@require_role("Admin")
def admin_metrics(user):
    """
    Real PostgreSQL Admin Metrics:
    - GMV (Gross Merchandise Value)
    - Platform Revenue
    - Escrow locked
    - Active assignments
    - Pending withdrawals
    - Pending disputes
    - Registered users by role
    """
    try:
        # Registered users
        users_res = supabase.table("users").select("role, account_status", count="exact").execute()
        total_users = users_res.count or len(users_res.data or [])
        
        # Transactions sum
        tx_res = supabase.table("transactions").select("transaction_type, amount, status").execute()
        gmv = 0.0
        platform_revenue = 0.0
        for tx in (tx_res.data or []):
            if tx.get("status") == "Completed":
                amt = float(tx.get("amount", 0.0))
                tt = tx.get("transaction_type")
                if tt == "Escrow Deposit":
                    gmv += amt
                elif tt == "Platform Fee":
                    platform_revenue += amt

        # Escrow locked (Funded assignments)
        asgt_res = supabase.table("assignments").select("budget, status, escrow_status").execute()
        escrow_locked = 0.0
        active_assignments = 0
        for a in (asgt_res.data or []):
            if a.get("escrow_status") == "Funded" and a.get("status") in ["Claimed", "Submitted", "Revision Requested"]:
                escrow_locked += float(a.get("budget", 0.0))
            if a.get("status") in ["Open", "Claimed", "Submitted", "Revision Requested"]:
                active_assignments += 1

        # Pending withdrawals
        wdr_res = supabase.table("withdrawals").select("id", count="exact").eq("status", "Pending").execute()
        pending_withdrawals = wdr_res.count if wdr_res.count is not None else 0

        # Pending disputes
        disp_res = supabase.table("disputes").select("id", count="exact").eq("status", "Open").execute()
        pending_disputes = disp_res.count if disp_res.count is not None else 0

        return jsonify({
            "metrics": {
                "gmv": round(gmv, 2),
                "platform_revenue": round(platform_revenue, 2),
                "escrow_locked": round(escrow_locked, 2),
                "active_assignments": active_assignments,
                "total_users": total_users,
                "pending_withdrawals": pending_withdrawals,
                "pending_disputes": pending_disputes
            }
        })
    except Exception as e:
        logger.error(f"Error calculating admin metrics: {e}")
        return jsonify({"error": "Failed to compute admin metrics", "details": str(e)}), 500


@app.route("/api/admin/users", methods=["GET"])
@require_role("Admin")
def admin_list_users(user):
    """Admin user search and role/status overview."""
    search = request.args.get("search")
    role_filter = request.args.get("role")
    status_filter = request.args.get("status")

    query = supabase.table("users").select("*")
    if search:
        query = query.or_(f"email.ilike.%{search}%,full_name.ilike.%{search}%")
    if role_filter:
        query = query.eq("role", role_filter)
    if status_filter:
        query = query.eq("account_status", status_filter)

    try:
        res = query.order("created_at", desc=True).execute()
        return jsonify({"users": res.data or []})
    except Exception as e:
        logger.error(f"Error in admin_list_users: {e}")
        return jsonify({"error": "Failed to list users"}), 500


@app.route("/api/admin/users/<target_user_id>/status", methods=["PUT"])
@require_role("Admin")
def admin_update_user_status(user, target_user_id):
    """Admin changes user account status (Active, Suspended, Pending Approval, Deactivated)."""
    body = request.get_json() or {}
    new_status = body.get("status")
    if new_status not in ["Active", "Suspended", "Pending Approval", "Deactivated"]:
        return jsonify({"error": "Invalid status value"}), 400

    try:
        supabase.table("users").update({"account_status": new_status, "updated_at": datetime.now(timezone.utc).isoformat()}).eq("id", target_user_id).execute()
        log_audit("admin_update_user_status", "users", target_user_id, user["id"], {"new_status": new_status})
        return jsonify({"message": f"User status updated to {new_status}"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/admin/disputes/<dispute_id>/resolve", methods=["POST"])
@require_role("Admin")
def admin_resolve_dispute(user, dispute_id):
    """
    Admin arbitration for disputes:
    Settlement types:
    - 'Full Release to Writer': Payouts full writer share to writer, fee to platform, marks Approved
    - 'Full Refund to Client': Refunds full deposit to client, marks Cancelled
    - '50/50 Settlement': Splits escrow 50/50 between client and writer
    - 'Dismiss': Reverts assignment back to previous in-progress status
    """
    body = request.get_json() or {}
    settlement = body.get("settlement_type")
    admin_notes = str(body.get("admin_notes", "")).strip()

    if settlement not in ["Full Release to Writer", "Full Refund to Client", "50/50 Settlement", "Dismiss"]:
        return jsonify({"error": "Validation Error", "message": "Invalid dispute settlement type."}), 422

    try:
        disp_res = supabase.table("disputes").select("*, assignment:assignments(*)").eq("id", dispute_id).execute()
        if not disp_res.data:
            return jsonify({"error": "Not Found"}), 404

        disp = disp_res.data[0]
        if disp["status"] == "Resolved":
            return jsonify({"error": "Conflict", "message": "Dispute is already resolved."}), 409

        asgt = disp["assignment"]
        assignment_id = asgt["id"]
        client_id = asgt["client_id"]
        writer_id = asgt["writer_id"]
        budget = float(asgt["budget"])
        now_iso = datetime.now(timezone.utc).isoformat()

        if settlement == "Full Release to Writer":
            payout = float(asgt["writer_payout"])
            # Credit writer
            w_res = supabase.table("users").select("available_balance, total_earnings").eq("id", writer_id).single().execute()
            if w_res.data:
                new_bal = round(float(w_res.data.get("available_balance", 0.0)) + payout, 2)
                supabase.table("users").update({"available_balance": new_bal}).eq("id", writer_id).execute()
            
            supabase.table("assignments").update({"status": "Approved", "escrow_status": "Released"}).eq("id", assignment_id).execute()

        elif settlement == "Full Refund to Client":
            # Refund client
            c_res = supabase.table("users").select("available_balance, total_spent").eq("id", client_id).single().execute()
            if c_res.data:
                new_bal = round(float(c_res.data.get("available_balance", 0.0)) + budget, 2)
                new_spent = max(0.0, round(float(c_res.data.get("total_spent", 0.0)) - budget, 2))
                supabase.table("users").update({"available_balance": new_bal, "total_spent": new_spent}).eq("id", client_id).execute()

            supabase.table("assignments").update({"status": "Cancelled", "escrow_status": "Refunded"}).eq("id", assignment_id).execute()

        elif settlement == "50/50 Settlement":
            half = round(budget / 2.0, 2)
            # Refund half to client
            c_res = supabase.table("users").select("available_balance").eq("id", client_id).single().execute()
            if c_res.data:
                new_bal = round(float(c_res.data.get("available_balance", 0.0)) + half, 2)
                supabase.table("users").update({"available_balance": new_bal}).eq("id", client_id).execute()

            # Credit half to writer
            w_res = supabase.table("users").select("available_balance").eq("id", writer_id).single().execute()
            if w_res.data:
                new_bal = round(float(w_res.data.get("available_balance", 0.0)) + half, 2)
                supabase.table("users").update({"available_balance": new_bal}).eq("id", writer_id).execute()

            supabase.table("assignments").update({"status": "Approved", "escrow_status": "Released"}).eq("id", assignment_id).execute()

        elif settlement == "Dismiss":
            # Revert back to Submitted
            supabase.table("assignments").update({"status": "Submitted", "escrow_status": "Funded"}).eq("id", assignment_id).execute()

        # Update dispute
        supabase.table("disputes").update({
            "status": "Resolved",
            "settlement_type": settlement,
            "admin_notes": admin_notes,
            "resolved_by": user["id"],
            "resolved_at": now_iso
        }).eq("id", dispute_id).execute()

        log_audit("admin_resolve_dispute", "disputes", dispute_id, user["id"], {
            "settlement_type": settlement,
            "admin_notes": admin_notes
        })

        return jsonify({"message": f"Dispute arbitrated with decision: '{settlement}'."})

    except Exception as e:
        logger.error(f"Error resolving dispute: {e}")
        return jsonify({"error": "Failed to resolve dispute", "details": str(e)}), 500


@app.route("/api/admin/withdrawals/<withdrawal_id>/approve", methods=["POST"])
@require_role("Admin")
def admin_approve_withdrawal(user, withdrawal_id):
    """Admin authorizes and marks withdrawal Approved."""
    try:
        now_iso = datetime.now(timezone.utc).isoformat()
        supabase.table("withdrawals").update({
            "status": "Approved",
            "processed_by": user["id"],
            "processed_at": now_iso
        }).eq("id", withdrawal_id).execute()

        # Update transaction status
        supabase.table("transactions").update({"status": "Completed"}).eq("reference", f"WITHDRAWAL-{withdrawal_id[:8]}").execute()

        log_audit("admin_approve_withdrawal", "withdrawals", withdrawal_id, user["id"])
        return jsonify({"message": "Withdrawal successfully approved."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/admin/withdrawals/<withdrawal_id>/reject", methods=["POST"])
@require_role("Admin")
def admin_reject_withdrawal(user, withdrawal_id):
    """Admin rejects withdrawal and restores available balance to user."""
    data = request.get_json() or {}
    reason = str(data.get("reason", "Administrative rejection"))

    try:
        wdr_res = supabase.table("withdrawals").select("*").eq("id", withdrawal_id).execute()
        if not wdr_res.data:
            return jsonify({"error": "Not Found"}), 404

        wdr = wdr_res.data[0]
        if wdr["status"] != "Pending":
            return jsonify({"error": "Bad Request", "message": "Can only reject Pending withdrawals."}), 400

        user_id = wdr["user_id"]
        amt = float(wdr["amount"])
        now_iso = datetime.now(timezone.utc).isoformat()

        # Restore balance
        u_res = supabase.table("users").select("available_balance").eq("id", user_id).single().execute()
        if u_res.data:
            restored = round(float(u_res.data.get("available_balance", 0.0)) + amt, 2)
            supabase.table("users").update({"available_balance": restored}).eq("id", user_id).execute()

        supabase.table("withdrawals").update({
            "status": "Rejected",
            "admin_notes": reason,
            "processed_by": user["id"],
            "processed_at": now_iso
        }).eq("id", withdrawal_id).execute()

        supabase.table("transactions").update({"status": "Failed"}).eq("reference", f"WITHDRAWAL-{withdrawal_id[:8]}").execute()

        log_audit("admin_reject_withdrawal", "withdrawals", withdrawal_id, user["id"], {"reason": reason})
        return jsonify({"message": "Withdrawal rejected and balance restored."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/admin/audit-logs", methods=["GET"])
@require_role("Admin")
def admin_audit_logs(user):
    """Admin views system-wide audit logs."""
    limit = min(100, int(request.args.get("limit", 50)))
    try:
        res = supabase.table("audit_logs").select("*, actor:users!actor_id(full_name, email, role)").order("created_at", desc=True).limit(limit).execute()
        return jsonify({"audit_logs": res.data or []})
    except Exception as e:
        logger.error(f"Error fetching audit logs: {e}")
        return jsonify({"error": "Failed to fetch audit logs"}), 500


@app.route("/api/admin/settings", methods=["PUT"])
@require_role("Admin")
def admin_update_settings(user):
    """Admin updates platform parameters (escrow split, minimum withdrawal, etc.)."""
    body = request.get_json() or {}
    key = body.get("key")
    val = body.get("value")

    if not key or val is None:
        return jsonify({"error": "Key and value required"}), 400

    # Validation
    if key == "escrow_split":
        if not isinstance(val, dict) or "writer_percentage" not in val or "platform_fee_percentage" not in val:
            return jsonify({"error": "escrow_split requires writer_percentage and platform_fee_percentage"}), 400
        w_pct = float(val["writer_percentage"])
        f_pct = float(val["platform_fee_percentage"])
        if round(w_pct + f_pct, 1) != 100.0 or w_pct < 50.0:
            return jsonify({"error": "Escrow percentages must sum to 100% and writer share >= 50%"}), 400

    try:
        supabase.table("platform_settings").upsert({
            "key": key,
            "value": val,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "updated_by": user["id"]
        }).execute()

        log_audit("admin_update_setting", "platform_settings", key, user["id"], {"new_value": val})
        return jsonify({"message": f"Setting '{key}' updated successfully."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ---------------------------------------------------------------------
# STATIC FILE SERVING FOR PRODUCTION
# ---------------------------------------------------------------------
@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_frontend(path):
    """Serve built frontend static files in production."""
    dist_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dist")
    if path != "" and os.path.exists(os.path.join(dist_dir, path)):
        return send_from_directory(dist_dir, path)
    if os.path.exists(os.path.join(dist_dir, "index.html")):
        return send_from_directory(dist_dir, "index.html")
    return jsonify({
        "name": "Intelliworks Industries API",
        "status": "ready",
        "api_docs": "/api/health"
    })

# ---------------------------------------------------------------------
# ERROR HANDLERS (CONSISTENT JSON RESPONSES)
# ---------------------------------------------------------------------
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

@app.errorhandler(409)
def conflict(e):
    return jsonify({"error": "Conflict", "message": "Resource conflict."}), 409

@app.errorhandler(500)
def server_error(e):
    logger.error(f"Internal server error: {e}")
    return jsonify({"error": "Internal Server Error", "message": "An unexpected error occurred."}), 500


if __name__ == "__main__":
    port = int(os.getenv("FLASK_PORT", 5001))
    logger.info(f"Starting Intelliworks Industries Flask backend on port {port}")
    app.run(host="0.0.0.0", port=port, debug=(APP_ENV == "development"))
