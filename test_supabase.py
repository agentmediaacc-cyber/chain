import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_ANON_KEY")

print("Connecting to Supabase...")
supabase = create_client(url, key)

try:
    result = supabase.table("chain_profiles").select("id,email").limit(1).execute()
    print("✅ Supabase connected")
    print(result.data)
except Exception as e:
    print("❌ Supabase error:")
    print(e)
