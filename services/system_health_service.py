import time
from services.supabase_safe import safe_count, safe_select

def get_platform_health_snapshot():
    """
    Returns a technical snapshot of the platform's current state.
    """
    start = time.perf_counter()
    # Simple query to test DB latency
    safe_count("chain_users")
    db_latency = (time.perf_counter() - start) * 1000
    
    return {
        "status": "healthy" if db_latency < 500 else "degraded",
        "db_latency_ms": round(db_latency, 2),
        "active_connections": safe_count("chain_presence", filters={"status": "online"}),
        "active_streams": safe_count("chain_live_rooms", filters={"is_live": True}),
        "pending_payouts": safe_count("chain_wallet_payouts", filters={"status": "pending"}),
        "failed_uploads_24h": 0, # Placeholder
        "failed_payments_24h": 0 # Placeholder
    }

def log_system_event(event_type, severity, message, metadata=None):
    """Logs a system-level event for technical auditing"""
    from services.supabase_safe import safe_insert
    from datetime import datetime, timezone
    payload = {
        "actor_type": "system",
        "action": event_type,
        "metadata": {
            "severity": severity,
            "message": message,
            "extra": metadata or {}
        },
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    # We reuse the enterprise audit log table
    return safe_insert("chain_enterprise_audit_log", payload)
