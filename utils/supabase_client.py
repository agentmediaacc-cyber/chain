import os
from functools import lru_cache
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

@lru_cache(maxsize=1)
def get_supabase():
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_ANON_KEY in .env")
    return create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

@lru_cache(maxsize=1)
def get_supabase_admin():
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in .env")
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
