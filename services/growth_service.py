import random
import string
from datetime import datetime, timezone
from services.supabase_safe import safe_insert, safe_select

def generate_referral_code(profile_id):
    """Generates a unique viral code for a creator"""
    chars = string.ascii_uppercase + string.digits
    code = ''.join(random.choice(chars) for _ in range(8))
    # In a real app, store this in chain_profiles or a separate table
    return code

def track_share(profile_id, entity_type, entity_id, platform):
    """Records a viral share event"""
    payload = {
        "profile_id": profile_id,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "platform": platform,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    return safe_insert("chain_share_events", payload)

def process_referral(referred_profile_id, referral_code):
    """Links a new user to their referrer"""
    # 1. Find referrer by code
    # For now, simulate lookup
    referrer_id = "00000000-0000-0000-0000-000000000000" 
    
    payload = {
        "referrer_profile_id": referrer_id,
        "referred_profile_id": referred_profile_id,
        "referral_code": referral_code,
        "reward_status": "pending",
        "reward_coins": 50, # 50 coins for successful referral
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    return safe_insert("chain_referrals", payload)

def log_analytics_event(profile_id, event_name, entity_type=None, entity_id=None, metadata=None):
    """Standard logging for platform analytics"""
    payload = {
        "profile_id": profile_id,
        "event_name": event_name,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "metadata": metadata or {},
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    return safe_insert("chain_analytics_events", payload)
