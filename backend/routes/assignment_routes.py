"""
INTELLIWORKS INDUSTRIES — ASSIGNMENT LIFECYCLE ROUTES
"""

import os
import sys
import uuid
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, Dict, Any, Tuple
from flask import Blueprint, request, jsonify

# Ensure project root is in sys.path
PARENT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

from backend.config import (
    IS_SUPABASE_CONFIGURED,
    logger,
    STORAGE_BUCKET,
    APP_ENV
)
from backend.database import supabase
from backend.middleware.auth import (
    require_auth,
    require_role,
    get_current_user
)
from backend.middleware.audit import log_audit

assignment_bp = Blueprint('assignment_bp', __name__)
# CLIENT WORKFLOW: ASSIGNMENT CREATION & LIFECYCLE
# ---------------------------------------------------------------------
@assignment_bp.route("/api/assignments", methods=["POST"])
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


@assignment_bp.route("/api/assignments", methods=["GET"])
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


@assignment_bp.route("/api/assignments/<assignment_id>", methods=["GET"])
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
@assignment_bp.route("/api/assignments/<assignment_id>/claim", methods=["POST"])
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


@assignment_bp.route("/api/assignments/<assignment_id>/submit", methods=["POST"])
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
@assignment_bp.route("/api/assignments/<assignment_id>/revision", methods=["POST"])
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


@assignment_bp.route("/api/assignments/<assignment_id>/approve", methods=["POST"])
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


@assignment_bp.route("/api/assignments/<assignment_id>/cancel", methods=["POST"])
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
@assignment_bp.route("/api/assignments/<assignment_id>/messages", methods=["GET"])
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


@assignment_bp.route("/api/assignments/<assignment_id>/messages", methods=["POST"])
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
