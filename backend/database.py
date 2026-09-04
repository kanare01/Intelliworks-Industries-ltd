"""
INTELLIWORKS INDUSTRIES — DATABASE & SUPABASE CLIENT
Client initialization, connection verification, and query helper abstractions.
"""

import os
import sys

# Ensure project root is in sys.path
PARENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

from backend.config import (
    SUPABASE_URL,
    SUPABASE_SERVICE_ROLE_KEY,
    IS_SUPABASE_CONFIGURED,
    logger
)

supabase = None

if IS_SUPABASE_CONFIGURED:
    try:
        from supabase import create_client, Client
        supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
        logger.info(f"Connected to Supabase PostgreSQL at: {SUPABASE_URL}")
    except Exception as e:
        logger.error(f"Failed to initialize Supabase client: {e}")
        IS_SUPABASE_CONFIGURED = False
else:
    logger.warning("Supabase credentials not configured. Live persistence and auth verification BLOCKED.")


def get_db():
    """Retrieve the authoritative Supabase client instance."""
    return supabase


def is_db_connected() -> bool:
    """Check if live database connection is configured and available."""
    return bool(IS_SUPABASE_CONFIGURED and supabase is not None)
