from app import app
from services.neon_service import get_neon_health


def main():
    neon_health = get_neon_health()
    assert neon_health["configured"], "DATABASE_URL is missing"
    assert neon_health["connected"], f"Neon connection failed: {neon_health.get('error')}"

    client = app.test_client()
    db_response = client.get("/health/db")
    supabase_response = client.get("/health/supabase")

    assert db_response.status_code == 200, f"/health/db returned {db_response.status_code}"
    assert supabase_response.status_code == 200, f"/health/supabase returned {supabase_response.status_code}"

    db_payload = db_response.get_json() or {}
    supabase_payload = supabase_response.get_json() or {}

    assert db_payload.get("connected") is True, f"/health/db payload: {db_payload}"
    assert supabase_payload.get("url_present") is True, f"/health/supabase payload: {supabase_payload}"
    assert supabase_payload.get("anon_key_present") is True, f"/health/supabase payload: {supabase_payload}"
    assert supabase_payload.get("service_role_present") is True, f"/health/supabase payload: {supabase_payload}"

    print("Neon connection result:")
    print(f" - connected: {neon_health.get('connected')}")
    print(f" - latency_ms: {neon_health.get('latency_ms')}")
    print(f" - database_name: {neon_health.get('database_name')}")

    print("\nSupabase storage/auth result:")
    print(f" - url_present: {supabase_payload.get('url_present')}")
    print(f" - anon_key_present: {supabase_payload.get('anon_key_present')}")
    print(f" - service_role_present: {supabase_payload.get('service_role_present')}")
    print(f" - auth_ready: {supabase_payload.get('auth_ready')}")
    print(f" - storage_ready: {supabase_payload.get('storage_ready')}")
    if "storage_reachable" in supabase_payload:
        print(f" - storage_reachable: {supabase_payload.get('storage_reachable')}")


if __name__ == "__main__":
    main()
