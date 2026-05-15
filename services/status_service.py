from datetime import datetime, timezone, timedelta
from services.supabase_safe import safe_insert, safe_select, safe_update, safe_delete
from services.storage_service import upload_status_media, upload_chat_media

def _utcnow_iso():
    return datetime.now(timezone.utc).isoformat()

def create_status(profile_id, caption, media_file=None, music_file=None):
    media_url = None
    media_upload_id = None
    music_url = None
    music_upload_id = None
    
    if media_file:
        res, err = upload_status_media(profile_id, media_file)
        if res:
            media_url = res['public_url']
            media_upload_id = res['upload_id']
            
    if music_file:
        # Re-use chat media or specific music upload for status
        res, err = upload_chat_media(profile_id, music_file)
        if res:
            music_url = res['public_url']
            music_upload_id = res['upload_id']
            
    payload = {
        "profile_id": profile_id,
        "caption": caption,
        "media_url": media_url,
        "media_upload_id": media_upload_id,
        "music_url": music_url,
        "music_upload_id": music_upload_id,
        "status_type": 'story',
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat(),
        "created_at": _utcnow_iso()
    }
    new_status = safe_insert("chain_status_posts", payload)
    return new_status[0] if new_status else None

def list_active_statuses(profile_id=None):
    now = _utcnow_iso()
    filters = {"expires_at": ("gt", now)}
    if profile_id:
        filters["profile_id"] = profile_id
        
    statuses = safe_select("chain_status_posts", filters=filters, limit=100, order_by="created_at", desc=True)
    return statuses

def expire_old_statuses():
    now = _utcnow_iso()
    # In a real app, this would be a background job or we just filter in select
    # For now, we can try to delete but safe_delete might need a filter
    pass
