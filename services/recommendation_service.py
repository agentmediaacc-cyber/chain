from datetime import datetime, timezone, timedelta
from services.supabase_safe import safe_insert, safe_select, safe_update, safe_count
from utils.supabase_client import get_supabase_admin

def _utcnow_iso():
    return datetime.now(timezone.utc).isoformat()

def calculate_trending_scores():
    """
    Background logic (simplified):
    Iterate over rooms, profiles, posts and calculate a score.
    Score = (Reactions * 2) + (Comments * 5) + (Follows * 10) + (Gifts * 20) / (Hours since creation ^ 1.5)
    """
    # For now, we'll just mock this or do a simple select
    pass

def get_trending_profiles(limit=10):
    # For now, return verified profiles with high activity
    return safe_select("chain_profiles", filters={"is_verified": True}, limit=limit, order_by="created_at", desc=True)

def get_trending_live_rooms(limit=10):
    return safe_select("chain_live_rooms", filters={"status": "live"}, limit=limit, order_by="viewer_count", desc=True)

def get_trending_posts(limit=10):
    return safe_select("chain_posts", limit=limit, order_by="created_at", desc=True)

def get_recommended_profiles(profile_id, limit=10):
    # Basic logic: creators you don't follow yet
    # Exclude self and current follows
    return safe_select("chain_profiles", filters={"is_creator": True}, limit=limit, order_by="created_at", desc=True)

def get_recommended_posts(profile_id, limit=10):
    return safe_select("chain_posts", limit=limit, order_by="created_at", desc=True)
