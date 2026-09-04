"""
INTELLIWORKS INDUSTRIES — BACKEND CONFIGURATION
Environment loading, logging configuration, and Supabase client initialization.
"""

import os
import sys
import logging
from dotenv import load_dotenv

# Load environment variables from .env in project root or current working directory
load_dotenv()

# Setup structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("intelliworks_backend")

# Supabase Credentials & Settings
SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "").strip()
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "").strip()
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "intelliworks-enterprise-production-key")
APP_ENV = os.getenv("APP_ENV", "development")
STORAGE_BUCKET = "assignment-files"

# Determine if Supabase credentials are configured
IS_SUPABASE_CONFIGURED = bool(
    SUPABASE_URL
    and SUPABASE_SERVICE_ROLE_KEY
    and not SUPABASE_URL.startswith("https://your-project")
)

supabase = None
if IS_SUPABASE_CONFIGURED:
    try:
        from supabase import create_client, Client
        supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
        logger.info(f"Connected to Supabase at: {SUPABASE_URL}")
    except Exception as e:
        logger.error(f"Failed to initialize Supabase client: {e}")
        IS_SUPABASE_CONFIGURED = False
else:
    logger.warning("Supabase credentials not configured. Live persistence and auth verification BLOCKED.")
