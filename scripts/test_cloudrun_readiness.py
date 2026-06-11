import os
import sys
from pathlib import Path

def check(name, condition, error_msg="Failed"):
    if condition:
        print(f"[PASS] {name}")
        return True
    else:
        print(f"[FAIL] {name}: {error_msg}")
        return False

def run_readiness_test():
    print("--- CHAIN Cloud Run Readiness Test ---")
    all_pass = True

    # 1. Check Files
    all_pass &= check("Dockerfile exists", Path("Dockerfile").exists())
    all_pass &= check(".dockerignore exists", Path(".dockerignore").exists())
    all_pass &= check("cloudrun.yaml exists", Path("cloudrun.yaml").exists())

    # 2. Check app.py for health routes
    with open("app.py", "r") as f:
        content = f.read()
        all_pass &= check("healthz route exists", "@app.route(\"/healthz\")" in content or "@app.get(\"/healthz\")" in content)
        all_pass &= check("health/db route exists", "/health/db" in content)
        all_pass &= check("health/redis route exists", "/health/redis" in content)
        all_pass &= check("health/supabase route exists", "/health/supabase" in content)
        all_pass &= check("PORT env support", "os.getenv(\"PORT\"" in content)
        all_pass &= check("0.0.0.0 binding", "0.0.0.0" in content)

    # 3. Check .dockerignore content
    if Path(".dockerignore").exists():
        with open(".dockerignore", "r") as f:
            di_content = f.read()
            all_pass &= check(".dockerignore ignores venv", "venv" in di_content)
            all_pass &= check(".dockerignore ignores .git", ".git" in di_content)
            all_pass &= check(".dockerignore ignores backups", "backups" in di_content)
            all_pass &= check(".dockerignore ignores secrets", "secrets" in di_content)
            all_pass &= check(".dockerignore ignores static/uploads", "static/uploads" in di_content)

    # 4. Check requirements for gunicorn
    with open("requirements.txt", "r") as f:
        reqs = f.read()
        all_pass &= check("gunicorn in requirements.txt", "gunicorn" in reqs)
        all_pass &= check("gevent in requirements.txt", "gevent" in reqs)

    # 5. Check Supabase Storage Router
    if Path("services/supabase_storage_router.py").exists():
        with open("services/supabase_storage_router.py", "r") as f:
            ssr = f.read()
            all_pass &= check("Supabase storage router uses ENV/FLASK_ENV", "is_production" in ssr)

    print("---------------------------------------")
    if all_pass:
        print("RESULT: Cloud Run Readiness PASS")
        sys.exit(0)
    else:
        print("RESULT: Cloud Run Readiness FAIL")
        sys.exit(1)

if __name__ == "__main__":
    run_readiness_test()
