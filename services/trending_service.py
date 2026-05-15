from datetime import datetime, timezone
from services.supabase_safe import safe_select, safe_insert, safe_update
from utils.supabase_client import get_supabase_admin

def _utcnow_iso():
    return datetime.now(timezone.utc).isoformat()

def calculate_trending_scores():
    """
    Background job logic to update trending scores.
    For now, we simulate by picking active/popular items.
    """
    supabase = get_supabase_admin()
    
    # Trending Live Rooms (by viewer count)
    rooms = safe_select("chain_live_rooms", filters={"is_live": True}, limit=20, order_by="viewer_count", desc=True)
    for i, room in enumerate(rooms):
        score = room.get("viewer_count", 0) * 10 + (room.get("reaction_count", 0) * 2)
        _update_trending_score('live_room', room['id'], score)
        
    # Trending Posts (by reaction count)
    # Note: Requires a way to count reactions. For now, we take recent posts.
    posts = safe_select("chain_posts", limit=20, order_by="created_at", desc=True)
    for post in posts:
        # In a real app, count from chain_post_reactions
        _update_trending_score('post', post['id'], 50) 
        
    # Trending Creators
    profiles = safe_select("chain_profiles", filters={"is_verified": True}, limit=10)
    for profile in profiles:
        _update_trending_score('profile', profile['id'], 100)

def _update_trending_score(entity_type, entity_id, score):
    supabase = get_supabase_admin()
    payload = {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "score": score,
        "updated_at": _utcnow_iso()
    }
    # Simple upsert logic
    existing = safe_select("chain_trending_scores", filters={"entity_type": entity_type, "entity_id": entity_id}, limit=1)
    if existing:
        safe_update("chain_trending_scores", payload, eq={"id": existing[0]['id']})
    else:
        safe_insert("chain_trending_scores", payload)

def get_trending_items(entity_type, limit=10):
    return safe_select("chain_trending_scores", filters={"entity_type": entity_type}, limit=limit, order_by="score", desc=True)
