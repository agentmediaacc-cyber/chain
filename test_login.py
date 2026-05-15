import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

email = input("Email: ").strip()
password = input("Password: ").strip()

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_ANON_KEY")
)

try:
    res = supabase.auth.sign_in_with_password({
        "email": email,
        "password": password
    })

    print("\n✅ LOGIN OK")
    print("User ID:", res.user.id if res.user else None)
    print("Email:", res.user.email if res.user else None)
    print("Access token:", "FOUND" if res.session and res.session.access_token else "MISSING")
    print("Refresh token:", "FOUND" if res.session and res.session.refresh_token else "MISSING")

except Exception as e:
    print("\n❌ LOGIN FAILED")
    print(e)
