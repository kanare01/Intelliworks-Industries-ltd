"""
INTELLIWORKS INDUSTRIES — POLICY & PLATFORM SETTINGS ROUTES
Academic integrity framework, permitted assistance, and public system parameters.
"""

import os
import sys
from flask import Blueprint, jsonify

# Ensure project root is in sys.path
PARENT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

from backend.config import logger
from backend.database import supabase, IS_SUPABASE_CONFIGURED

policy_bp = Blueprint("policy_bp", __name__)


@policy_bp.route("/api/academic-policy", methods=["GET"])
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


@policy_bp.route("/api/settings", methods=["GET"])
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
