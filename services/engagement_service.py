from datetime import datetime, timezone
from services.supabase_safe import safe_insert, safe_select, safe_update, safe_delete
from services.notification_service import create_notification

def _utcnow_iso():
    return datetime.now(timezone.utc).isoformat()

def follow_profile(follower_id, following_id):
    if follower_id == following_id:
        return False, "You cannot follow yourself."
    
    payload = {
        "follower_profile_id": follower_id,
        "following_profile_id": following_id,
        "created_at": _utcnow_iso()
    }
    res = safe_insert("chain_follows", payload)
    if res:
        # Notify
        create_notification(
            profile_id=following_id,
            actor_profile_id=follower_id,
            n_type="follow",
            title="New Follower",
            body="Someone started following you!",
            link_url=f"/profile/{follower_id}"
        )
        return True, None
    return False, "Already following or error."

def unfollow_profile(follower_id, following_id):
    safe_delete("chain_follows", eq={"follower_profile_id": follower_id, "following_profile_id": following_id})
    return True

def react_to_post(profile_id, post_id, reaction_type='like'):
    payload = {
        "profile_id": profile_id,
        "post_id": post_id,
        "reaction_type": reaction_type,
        "created_at": _utcnow_iso()
    }
    # For reactions, we usually want to toggle or upsert
    from utils.supabase_client import get_supabase_admin
    supabase = get_supabase_admin()
    supabase.table("chain_post_reactions").upsert(payload).execute()
    return True

def comment_on_post(profile_id, post_id, body):
    if not body or not body.strip():
        return False, "Comment cannot be empty."
        
    payload = {
        "profile_id": profile_id,
        "post_id": post_id,
        "body": body.strip(),
        "created_at": _utcnow_iso()
    }
    res = safe_insert("chain_post_comments", payload)
    return res[0] if res else None

def react_to_live(room_id, profile_id, reaction_type):
    payload = {
        "room_id": room_id,
        "profile_id": profile_id,
        "reaction_type": reaction_type,
        "created_at": _utcnow_iso()
    }
    safe_insert("chain_live_reactions", payload)
    return True

def comment_on_live(room_id, profile_id, body):
    payload = {
        "room_id": room_id,
        "profile_id": profile_id,
        "body": body,
        "created_at": _utcnow_iso()
    }
    safe_insert("chain_live_comments_v2", payload)
    return True

def save_item(profile_id, item_type, item_id):
    payload = {
        "profile_id": profile_id,
        "item_type": item_type,
        "item_id": item_id,
        "created_at": _utcnow_iso()
    }
    res = safe_insert("chain_saved_items", payload)
    return res is not None
