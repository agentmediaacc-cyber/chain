from better_profanity import profanity
from services.supabase_safe import safe_insert, safe_update
from datetime import datetime, timezone

def screen_text(text):
    """Returns True if text is clean, False if it contains profanity"""
    if not text: return True
    return not profanity.contains_profanity(text)

def flag_for_moderation(entity_type, entity_id, reporter_id, reason, ai_score=0.5):
    """Adds an item to the moderation queue for admin review"""
    payload = {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "reporter_profile_id": reporter_id,
        "reason": reason,
        "ai_score": ai_score,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    return safe_insert("chain_moderation_queue", payload)

def auto_moderate_content(text, entity_type, entity_id, profile_id):
    """
    Automated check for content. If highly suspicious, flag immediately.
    """
    if profanity.contains_profanity(text):
        flag_for_moderation(entity_type, entity_id, None, "Auto-flag: Profanity detected", ai_score=0.9)
        return False # Should probably hide content
        
    # Check for scam keywords
    scam_keywords = ["whatsapp me", "crypto profit", "send money first", "gift card"]
    for word in scam_keywords:
        if word in text.lower():
            flag_for_moderation(entity_type, entity_id, None, f"Auto-flag: Scam keyword '{word}'", ai_score=0.8)
            return True # Flag but keep for now
            
    return True

def resolve_moderation(report_id, admin_id, action):
    """Updates report status and takes action (e.g., 'deleted', 'safe')"""
    payload = {
        "status": "resolved",
        "action_taken": action,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    return safe_update("chain_moderation_queue", payload, eq={"id": report_id})
