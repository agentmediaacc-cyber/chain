import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import create_app


REQUIRED_ROUTES = {
    "/profile/settings",
    "/profile/onboarding",
    "/profile/security",
    "/profile/security/set-password",
}

REQUIRED_SQL_FIELDS = {
    "phone",
    "residential_address",
    "town",
    "region",
    "country_of_birth",
    "date_of_birth",
    "current_residential_location",
    "profile_completed",
    "onboarding_step",
    "password_set",
    "auth_provider",
    "linked_providers",
    "last_login_at",
    "login_count",
}


def main():
    app = create_app()
    rules = {rule.rule for rule in app.url_map.iter_rules()}
    print("CHAIN onboarding auth audit")
    print("=" * 64)

    print("Missing onboarding/security routes")
    print("-" * 64)
    missing_routes = sorted(REQUIRED_ROUTES - rules)
    print("\n".join(missing_routes) if missing_routes else "none")

    print("\nTemplate checks")
    print("-" * 64)
    template_paths = [
        ROOT / "templates/profile/edit.html",
        ROOT / "templates/profile/settings.html",
        ROOT / "templates/profile/onboarding.html",
        ROOT / "templates/profile/security.html",
    ]
    template_failed = False
    for path in template_paths:
        if path.exists():
            print(f"{path.relative_to(ROOT)}: OK")
        else:
            template_failed = True
            print(f"{path.relative_to(ROOT)}: MISSING")

    print("\nEndpoint scan")
    print("-" * 64)
    bad_refs = []
    for path in list(ROOT.rglob("*.py")) + list(ROOT.rglob("*.html")):
        if "__pycache__" in path.parts or "venv" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if re.search(r"url_for\(\s*['\"]profile\.profile['\"]|['\"]profile\.profile['\"]", text):
            bad_refs.append(path.relative_to(ROOT))
    if bad_refs:
        for path in bad_refs:
            print(path)
    else:
        print("none")

    print("\nOAuth button checks")
    print("-" * 64)
    login_html = (ROOT / "templates/auth/login.html").read_text(encoding="utf-8", errors="ignore")
    register_html = (ROOT / "templates/auth/register.html").read_text(encoding="utf-8", errors="ignore")
    callback_link_found = any(
        snippet in login_html or snippet in register_html
        for snippet in ["/auth/google/callback", "/auth/facebook/callback"]
    )
    direct_start_ok = '/auth/google' in login_html and '/auth/facebook' in login_html and '/auth/google' in register_html and '/auth/facebook' in register_html
    print("callback links present" if callback_link_found else "callback links absent")
    print("start links OK" if direct_start_ok else "start links missing")

    print("\nSQL field checks")
    print("-" * 64)
    sql_path = ROOT / "supabase_chain_onboarding_auth_upgrade.sql"
    sql_text = sql_path.read_text(encoding="utf-8", errors="ignore") if sql_path.exists() else ""
    missing_fields = sorted(field for field in REQUIRED_SQL_FIELDS if field not in sql_text)
    print("\n".join(missing_fields) if missing_fields else "none")

    failed = bool(missing_routes or template_failed or bad_refs or callback_link_found or not direct_start_ok or missing_fields)
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
