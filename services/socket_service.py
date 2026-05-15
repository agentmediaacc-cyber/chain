from datetime import datetime, timezone
from services.supabase_safe import safe_insert, safe_update
from utils.supabase_client import get_supabase_admin

def broadcast_live_event(room_id, event_type, payload):
    """
    Triggers a real-time event that the frontend listens to via Supabase Realtime.
    We use a dedicated 'chain_realtime_events' table for this.
    """
    supabase = get_supabase_admin()
    full_payload = {
        "room_id": room_id,
        "event_type": event_type, # 'chat', 'reaction', 'gift', 'goal_update', 'viewer_count'
        "data": payload,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    # In Supabase, simply inserting into a table with Realtime enabled broadcasts it.
    return safe_insert("chain_realtime_events", full_payload)

def send_typing_indicator(conversation_id, profile_id, is_typing=True):
    """Broadcasting typing status to a conversation"""
    payload = {
        "conversation_id": conversation_id,
        "profile_id": profile_id,
        "is_typing": is_typing,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    supabase = get_supabase_admin()
    return supabase.table("chain_typing_status").upsert(payload).execute()

def notify_online_status(profile_id, status='online'):
    """Updates presence and broadcasts status change"""
    from services.realtime_service import set_online, set_offline
    if status == 'online':
        return set_online(profile_id)
    else:
        return set_offline(profile_id)
