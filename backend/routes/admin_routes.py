"""
INTELLIWORKS INDUSTRIES — ADMIN COMMAND CENTER ROUTES
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

admin_bp = Blueprint('admin_bp', __name__)
# ADMIN COMMAND CENTER: METRICS, USER MANAGEMENT, ARBITRATION
# ---------------------------------------------------------------------
@admin_bp.route("/api/admin/metrics", methods=["GET"])
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


@admin_bp.route("/api/admin/users", methods=["GET"])
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


@admin_bp.route("/api/admin/users/<target_user_id>/status", methods=["PUT"])
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


@admin_bp.route("/api/admin/disputes/<dispute_id>/resolve", methods=["POST"])
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


@admin_bp.route("/api/admin/withdrawals/<withdrawal_id>/approve", methods=["POST"])
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


@admin_bp.route("/api/admin/withdrawals/<withdrawal_id>/reject", methods=["POST"])
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


@admin_bp.route("/api/admin/audit-logs", methods=["GET"])
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


@admin_bp.route("/api/admin/settings", methods=["PUT"])
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

