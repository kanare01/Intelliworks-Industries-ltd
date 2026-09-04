"""
INTELLIWORKS INDUSTRIES — USER & PROFILE ROUTES
User profiles, settings, notifications, and referral tracking.
"""

import os
import sys
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify

# Ensure project root is in sys.path
PARENT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

from backend.config import logger
from backend.database import supabase
from backend.middleware.auth import require_auth
from backend.middleware.audit import log_audit

user_bp = Blueprint("user_bp", __name__)


@user_bp.route("/api/me", methods=["GET"])
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


@user_bp.route("/api/profile", methods=["PUT"])
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


@user_bp.route("/api/notifications", methods=["GET"])
@require_auth
def get_notifications(user):
    """Retrieve persistent notifications."""
    try:
        res = supabase.table("notifications").select("*").eq("recipient_id", user["id"]).order("created_at", desc=True).limit(50).execute()
        return jsonify({"notifications": res.data or []})
    except Exception as e:
        logger.error(f"Error retrieving notifications: {e}")
        return jsonify({"error": "Failed to fetch notifications"}), 500


@user_bp.route("/api/notifications/<notif_id>/read", methods=["PUT"])
@require_auth
def mark_notification_read(user, notif_id):
    """Mark single notification as read."""
    try:
        supabase.table("notifications").update({"is_read": True}).eq("id", notif_id).eq("recipient_id", user["id"]).execute()
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@user_bp.route("/api/notifications/read-all", methods=["PUT"])
@require_auth
def mark_all_notifications_read(user):
    """Mark all notifications as read."""
    try:
        supabase.table("notifications").update({"is_read": True}).eq("recipient_id", user["id"]).execute()
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@user_bp.route("/api/referrals", methods=["GET"])
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
