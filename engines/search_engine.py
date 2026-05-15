from utils.supabase_client import get_supabase_admin

def search_profiles(query, limit=20):
    query = (query or "").strip()
    if not query:
        return []

    supabase = get_supabase_admin()
    try:
        res = (
            supabase.table("chain_profiles")
            .select("*")
            .or_(f"username.ilike.%{query}%,full_name.ilike.%{query}%,current_location.ilike.%{query}%,country_origin.ilike.%{query}%")
            .eq("is_public", True)
            .limit(limit)
            .execute()
        )
        return res.data or []
    except Exception as exc:
        print("[SEARCH ENGINE] profile search failed:", exc)
        return []
