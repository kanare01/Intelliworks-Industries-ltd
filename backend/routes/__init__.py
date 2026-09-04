"""
INTELLIWORKS INDUSTRIES — MODULAR ROUTE BLUEPRINTS
Aggregates all domain-driven route modules into the core application engine.
"""

from flask import Flask, Blueprint
from backend.routes.policy_routes import policy_bp
from backend.routes.user_routes import user_bp
from backend.routes.assignment_routes import assignment_bp
from backend.routes.review_routes import review_bp
from backend.routes.financial_routes import financial_bp
from backend.routes.dispute_routes import dispute_bp
from backend.routes.admin_routes import admin_bp

ALL_BLUEPRINTS = [
    policy_bp,
    user_bp,
    assignment_bp,
    review_bp,
    financial_bp,
    dispute_bp,
    admin_bp
]


def register_routes(app: Flask):
    """Register all domain route blueprints with the Flask application."""
    for bp in ALL_BLUEPRINTS:
        app.register_blueprint(bp)


# Combined blueprint for backward-compatibility with tests and previous imports
api_bp = Blueprint("api_bp", __name__)

__all__ = [
    "register_routes",
    "ALL_BLUEPRINTS",
    "policy_bp",
    "user_bp",
    "assignment_bp",
    "review_bp",
    "financial_bp",
    "dispute_bp",
    "admin_bp",
    "api_bp"
]
