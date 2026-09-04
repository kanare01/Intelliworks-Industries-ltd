"""
INTELLIWORKS INDUSTRIES — REVIEWS & RATINGS ROUTES
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

review_bp = Blueprint('review_bp', __name__)
# REVIEWS & RATINGS
# ---------------------------------------------------------------------
@review_bp.route("/api/reviews", methods=["POST"])
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
