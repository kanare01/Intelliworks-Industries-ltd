"""
INTELLIWORKS INDUSTRIES — DISPUTE & ARBITRATION ROUTES
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

dispute_bp = Blueprint('dispute_bp', __name__)
# DISPUTES & ARBITRATION
# ---------------------------------------------------------------------
@dispute_bp.route("/api/assignments/<assignment_id>/dispute", methods=["POST"])
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


@dispute_bp.route("/api/disputes", methods=["GET"])
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
