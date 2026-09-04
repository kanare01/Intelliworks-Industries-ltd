"""
INTELLIWORKS INDUSTRIES — AUDIT LOGGING SERVICE
Immutable audit trail capturing all administrative, financial, and lifecycle state transitions.
"""

import os
import sys
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from flask import request

# Ensure project root is in sys.path
PARENT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

from backend.config import logger
from backend.database import supabase, IS_SUPABASE_CONFIGURED


def log_audit(
    action: str,
    entity_type: str,
    entity_id: Optional[str] = None,
    actor_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
):
    """Write an immutable audit log entry."""
    ip_addr = request.remote_addr if request else "system"
    method = request.method if request else "INTERNAL"
    route = request.path if request else "internal"
    
    log_data = {
        "id": str(uuid.uuid4()),
        "actor_id": actor_id,
        "action": action,
        "entity_type": entity_type,
        "entity_id": str(entity_id) if entity_id else None,
        "http_method": method,
        "route": route,
        "ip_address": ip_addr,
        "metadata": metadata or {},
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    logger.info(f"AUDIT: [{action}] {entity_type}:{entity_id} by {actor_id}")
    if IS_SUPABASE_CONFIGURED and supabase:
        try:
            supabase.table("audit_logs").insert(log_data).execute()
        except Exception as e:
            logger.error(f"Failed to persist audit log to Supabase: {e}")
