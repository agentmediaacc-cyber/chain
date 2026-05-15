from services.supabase_safe import safe_select
from utils.supabase_client import get_supabase_admin

def smart_search(query, limit=20):
    if not query or not query.strip():
        return {"profiles": [], "live_rooms": [], "posts": [], "hashtags": [], "marketplace": [], "music": []}
    
    q = query.strip()
    results = {
        "profiles": [],
        "live_rooms": [],
        "posts": [],
        "hashtags": [],
        "marketplace": [],
        "music": []
    }
    
    supabase = get_supabase_admin()
    
    # 1. Search Profiles
    profiles = (
        supabase.table("chain_profiles")
        .select("*")
        .or_(f"username.ilike.%{q}%,full_name.ilike.%{q}%")
        .limit(limit)
        .execute()
        .data or []
    )
    results["profiles"] = profiles
    
    # 2. Search Live Rooms
    rooms = (
        supabase.table("chain_live_rooms")
        .select("*")
        .or_(f"title.ilike.%{q}%,category.ilike.%{q}%")
        .limit(limit)
        .execute()
        .data or []
    )
    results["live_rooms"] = rooms
    
    # 3. Search Posts & Hashtags
    posts = (
        supabase.table("chain_posts")
        .select("*")
        .or_(f"caption.ilike.%{q}%,body.ilike.%{q}%")
        .limit(limit)
        .execute()
        .data or []
    )
    results["posts"] = posts
    
    # 4. Search Marketplace
    marketplace = (
        supabase.table("chain_marketplace_items")
        .select("*")
        .or_(f"title.ilike.%{q}%,description.ilike.%{q}%")
        .eq("approval_status", "approved")
        .limit(limit)
        .execute()
        .data or []
    )
    results["marketplace"] = marketplace
    
    # 5. Search Music (Albums & Tracks)
    albums = (
        supabase.table("chain_music_albums")
        .select("*")
        .or_(f"title.ilike.%{q}%,genre.ilike.%{q}%")
        .limit(limit)
        .execute()
        .data or []
    )
    results["music"] = albums
    
    return results

def search_chain(query, limit=20):
    return smart_search(query, limit)

def instant_search_dropdown(query):
    """Simplified search for dropdown results"""
    results = smart_search(query, limit=5)
    
    dropdown = []
    for p in results['profiles']:
        dropdown.append({"title": p['full_name'], "subtitle": f"@{p['username']}", "type": "profile", "image": p.get('avatar_url'), "url": f"/profile/@{p['username']}"})
    
    for r in results['live_rooms']:
        dropdown.append({"title": r['title'], "subtitle": f"Live in {r['category']}", "type": "live", "image": r.get('cover_url'), "url": f"/live/room/{r['id']}"})
        
    return dropdown[:10]
