from datetime import datetime, timezone
from services.supabase_safe import safe_insert, safe_select, safe_update
from services.profile_service import get_current_profile

def _utcnow_iso():
    return datetime.now(timezone.utc).isoformat()

def start_call(conversation_id, caller_profile_id, receiver_profile_id, call_type):
    payload = {
        "conversation_id": conversation_id,
        "caller_profile_id": caller_profile_id,
        "receiver_profile_id": receiver_profile_id,
        "call_type": call_type, # 'audio', 'video'
        "call_status": 'ringing',
        "started_at": _utcnow_iso()
    }
    new_call = safe_insert("chain_call_sessions", payload)
    return new_call[0] if new_call else None

def answer_call(call_id, profile_id):
    # Verify receiver
    call = safe_select("chain_call_sessions", filters={"id": call_id}, limit=1)
    if not call or call[0]['receiver_profile_id'] != profile_id:
        return None, "Unauthorized."
    
    payload = {
        "call_status": 'answered',
        "answered_at": _utcnow_iso()
    }
    updated = safe_update("chain_call_sessions", payload, eq={"id": call_id})
    return updated[0] if updated else None, None

def end_call(call_id, profile_id):
    call_rows = safe_select("chain_call_sessions", filters={"id": call_id}, limit=1)
    if not call_rows:
        return None, "Call not found."
    
    call = call_rows[0]
    ended_at = datetime.now(timezone.utc)
    started_at = call.get('answered_at') or call.get('started_at')
    
    duration = 0
    if started_at:
        try:
            start_dt = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
            duration = int((ended_at - start_dt).total_seconds())
        except:
            pass
            
    payload = {
        "call_status": 'ended',
        "ended_at": ended_at.isoformat(),
        "duration_seconds": max(duration, 0)
    }
    updated = safe_update("chain_call_sessions", payload, eq={"id": call_id})
    return updated[0] if updated else None, None

def list_recent_calls(profile_id):
    # Calls where profile_id is caller or receiver
    calls = safe_select("chain_call_sessions", 
                        filters={"caller_profile_id": profile_id}, 
                        limit=50, order_by="started_at", desc=True)
    received = safe_select("chain_call_sessions", 
                           filters={"receiver_profile_id": profile_id}, 
                           limit=50, order_by="started_at", desc=True)
    
    all_calls = calls + received
    all_calls.sort(key=lambda x: x['started_at'], reverse=True)
    return all_calls[:50]
