import os
from dotenv import load_dotenv

load_dotenv()

print("\n=== ENV CHECK ===")
print("SUPABASE_URL:", os.getenv("SUPABASE_URL"))
print("SUPABASE_ANON_KEY:", "FOUND" if os.getenv("SUPABASE_ANON_KEY") else "MISSING")
print("SUPABASE_SERVICE_ROLE_KEY:", "FOUND" if os.getenv("SUPABASE_SERVICE_ROLE_KEY") else "MISSING")
print("SECRET_KEY:", "FOUND" if os.getenv("SECRET_KEY") else "MISSING")
print("=================\n")
