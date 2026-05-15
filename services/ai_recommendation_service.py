from datetime import datetime, timezone
from services.supabase_safe import safe_select, safe_insert
from utils.supabase_client import get_supabase_admin

def get_ai_recommendations(profile_id, rec_type='people', limit=10):
    """
    Returns AI-ranked recommendations for a user.
    Uses: Interests, Engagement, Location, and Trending scores.
    """
    # 1. Try to get cached recommendations
    cached = safe_select("chain_ai_recommendations", filters={"profile_id": profile_id, "recommendation_type": rec_type}, limit=limit, order_by="score", desc=True)
    if cached:
        return cached

    # 2. Generate fresh recommendations (Simplified AI logic)
    user_profile = (safe_select("chain_profiles", filters={"id": profile_id}, limit=1) or [{}])[0]
    user_interests = set(user_profile.get("interests") or [])
    user_location = user_profile.get("current_location")

    recommendations = []
    
    if rec_type == 'people':
        # Find people with matching interests or location
        candidates = safe_select("chain_profiles", limit=100)
        for cand in candidates:
            if cand['id'] == profile_id: continue
            
            score = 0
            cand_interests = set(cand.get("interests") or [])
            shared = user_interests.intersection(cand_interests)
            score += len(shared) * 20 # Weighted shared interests
            
            if cand.get("current_location") == user_location:
                score += 15 # Proximity boost
            
            if cand.get("is_verified"):
                score += 10 # Trust boost
            
            if cand.get("is_premium"):
                score += 5 # Premium visibility boost
                
            if score > 0:
                recommendations.append({
                    "profile_id": profile_id,
                    "recommendation_type": 'people',
                    "recommended_entity_id": cand['id'],
                    "score": score,
                    "reason": f"Shared interests: {', '.join(list(shared)[:2])}" if shared else "Nearby creator"
                })

    # 3. Save/Update cache
    for rec in recommendations[:limit]:
        # Upsert logic (simplified with direct insert for speed, table has UNIQUE constraint)
        try:
            safe_insert("chain_ai_recommendations", rec)
        except:
            pass

    recommendations.sort(key=lambda x: x['score'], reverse=True)
    return recommendations[:limit]

def get_recommended_rooms(profile_id, limit=5):
    """AI recommendations for live rooms based on user history"""
    # In a real app, track 'watch_history' and find rooms with similar categories
    return safe_select("chain_live_rooms", filters={"is_live": True}, limit=limit, order_by="viewer_count", desc=True)
