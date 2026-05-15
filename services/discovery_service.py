from engines.cache_engine import cache_key, get_cache, set_cache
from services.live_service import get_live_rooms
from services.profile_service import normalize_profile
from services.supabase_safe import safe_select


def get_discovery_data(section, viewer_id=None):
    try:
        key = cache_key("discovery", section)
        cached_data = get_cache(key)
        if cached_data is not None and not viewer_id:
            return cached_data
        
        data = []
        title = section.replace("-", " ").title()

        if section == "dating":
            # Dating swipe cards logic
            profiles = safe_select(
                "chain_profiles",
                limit=50,
                filters={"is_public": True, "dating_mode_enabled": True}
            )
            # Calculate compatibility scores
            viewer_profile = (safe_select("chain_profiles", filters={"id": viewer_id}, limit=1) or [{}])[0] if viewer_id else {}
            
            for p in profiles:
                if p['id'] == viewer_id: continue
                p = normalize_profile(p)
                p['compatibility_score'] = _calculate_compatibility(viewer_profile, p)
                data.append(p)
            
            data.sort(key=lambda x: x.get('compatibility_score', 0), reverse=True)
            title = "Dating Discovery"

        elif section == "live-now" or section == "live":
            data = get_live_rooms(limit=50)
            title = "Live Now"
        elif section == "members" or section == "recommended":
            data = [
                normalize_profile(profile)
                for profile in safe_select(
                    "chain_profiles",
                    columns="id,username,full_name,bio,current_location,avatar_url,is_premium,premium_tier,is_verified,age,country_origin,interests,cover_url",
                    limit=50,
                    filters={"is_public": True},
                )
            ]
            title = "Recommended Members"
        elif section == "trending":
            data = safe_select("chain_posts", columns="id,profile_id,body,caption,category,media_url,created_at,visibility", limit=50)
            title = "Trending Feed"
        elif section == "nearby":
            data = [
                normalize_profile(profile)
                for profile in safe_select(
                    "chain_profiles",
                    columns="id,username,full_name,bio,current_location,avatar_url,is_premium,premium_tier,is_verified,age,country_origin,interests,cover_url",
                    limit=50,
                    filters={"current_location": ("not.is", "null")},
                )
            ]
            title = "Nearby Members"
        else:
            data = [
                normalize_profile(profile)
                for profile in safe_select("chain_profiles", columns="id,username,full_name,bio,current_location,avatar_url,is_premium,premium_tier,is_verified,age,country_origin,interests,cover_url", limit=20)
            ]

        result = {
            "title": title,
            "section": section,
            "items": data
        }
        set_cache(key, result, ttl=45)
        return result
    except Exception as error:
        print(f"[discovery_service] get_discovery_data failed: {error}")
        return {"title": "Discovery", "section": section, "items": []}

def _calculate_compatibility(a, b):
    """Calculates a compatibility score between 0-100"""
    score = 50
    a_interests = set(a.get("interests") or [])
    b_interests = set(b.get("interests") or [])
    shared = a_interests.intersection(b_interests)
    score += len(shared) * 10
    
    if a.get("country_origin") == b.get("country_origin"):
        score += 15
    
    if b.get("is_premium"):
        score += 5
        
    return min(score, 99)
