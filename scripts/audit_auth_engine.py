import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import create_app
import services.auth_service as auth_service


REQUIRED_ROUTES = {
    "/auth/login",
    "/auth/register",
    "/auth/logout",
    "/auth/google",
    "/auth/google/callback",
    "/auth/facebook",
    "/auth/facebook/callback",
    "/auth/forgot-password",
    "/profile/",
}

REQUIRED_FUNCTIONS = {
    "register_chain_user",
    "login_chain_user",
    "get_oauth_url",
    "handle_oauth_callback",
    "sync_oauth_profile",
    "get_current_user",
    "get_current_profile",
    "logout_chain_user",
    "refresh_chain_session",
}


def main():
    app = create_app()
    rules = {rule.rule for rule in app.url_map.iter_rules()}

    print("CHAIN auth engine audit")
    print("=" * 64)

    missing_routes = sorted(REQUIRED_ROUTES - rules)
    print("Missing auth/profile routes")
    print("-" * 64)
    print("\n".join(missing_routes) if missing_routes else "none")

    missing_functions = sorted(name for name in REQUIRED_FUNCTIONS if not hasattr(auth_service, name))
    print("\nMissing auth service functions")
    print("-" * 64)
    print("\n".join(missing_functions) if missing_functions else "none")

    print("\nStatic checks")
    print("-" * 64)
    checks = {
        "login template": ROOT / "templates/auth/login.html",
        "register template": ROOT / "templates/auth/register.html",
        "forgot password template": ROOT / "templates/auth/forgot_password.html",
        "auth SQL upgrade": ROOT / "supabase_chain_auth_engine_upgrade.sql",
    }
    failed = False
    for label, path in checks.items():
        if path.exists():
            print(f"{label}: OK")
        else:
            failed = True
            print(f"{label}: MISSING")

    profile_profile_refs = []
    bad_ref_pattern = re.compile(r"url_for\(\s*['\"]profile\.profile['\"]|['\"]profile\.profile['\"]")
    for path in list(ROOT.rglob("*.py")) + list(ROOT.rglob("*.html")):
        if "__pycache__" in path.parts or "venv" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if bad_ref_pattern.search(text):
            profile_profile_refs.append(path.relative_to(ROOT))

    print("\nWrong endpoint references")
    print("-" * 64)
    if profile_profile_refs:
        failed = True
        for path in profile_profile_refs:
            print(path)
    else:
        print("none")

    if missing_routes or missing_functions or failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
