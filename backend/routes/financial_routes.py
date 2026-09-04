"""
INTELLIWORKS INDUSTRIES — FINANCIAL & ESCROW LEDGER ROUTES
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

financial_bp = Blueprint('financial_bp', __name__)
# WITHDRAWALS (INTERNAL ACCOUNTING WORKFLOW)
# ---------------------------------------------------------------------
@financial_bp.route("/api/withdrawals", methods=["GET"])
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


@financial_bp.route("/api/withdrawals", methods=["POST"])
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
# TRANSACTIONS, NOTIFICATIONS & REFERRALS
# ---------------------------------------------------------------------
@financial_bp.route("/api/transactions", methods=["GET"])
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


