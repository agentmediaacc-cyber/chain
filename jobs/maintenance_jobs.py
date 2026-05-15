from utils.supabase_client import get_supabase_admin

def close_stale_live_rooms():
    supabase = get_supabase_admin()
    try:
        # later: close rooms inactive for many hours
        print("[JOB] close_stale_live_rooms checked")
    except Exception as exc:
        print("[JOB] close stale live failed:", exc)


def refresh_profile_completion_scores():
    supabase = get_supabase_admin()
    try:
        rows = supabase.table("chain_profiles").select("*").limit(200).execute().data or []
        for p in rows:
            fields = [
                p.get("profile_photo"),
                p.get("cover_photo"),
                p.get("bio"),
                p.get("interests"),
                p.get("languages"),
                p.get("relationship_goal"),
                p.get("video_intro_url"),
            ]
            score = int((sum(1 for f in fields if f) / len(fields)) * 100)
            supabase.table("chain_profiles").update({"profile_completion": score}).eq("id", p["id"]).execute()
        print("[JOB] profile completion refreshed")
    except Exception as exc:
        print("[JOB] profile score failed:", exc)
