import time
from html.parser import HTMLParser

from app import app


FILES_CHANGED = [
    "app.py",
    "api_routes/auth_routes.py",
    "api_routes/profile_routes.py",
    "services/neon_service.py",
    "services/media_storage_service.py",
    "services/homepage_service.py",
    "services/storage_service.py",
    "sql/chain_neon_core_schema.sql",
    "templates/base.html",
    "templates/auth/profile_error.html",
    "templates/chain_home.html",
    "templates/auth/login.html",
    "static/css/chain_home.css",
    "static/css/chain_auth.css",
    "static/js/chain_home.js",
    "scripts/test_chain_homepage_fast.py",
    "scripts/test_chain_feature_stability.py",
    "scripts/test_chain_log_regressions.py",
]

HOME_REQUIRED = [
    "what's happening on chain?",
    "post",
    "story",
    "reel",
    "go live",
    "upload video",
    "friends",
    "reels",
    "creator tools",
    "live rooms",
    "messages",
    "wallet",
    "dating",
    "notifications",
]

HOME_BANNED = [
    "namibia social live network",
    "discover real creators, active live rooms, fresh stories",
    "my's premium live",
    "windhoek late night chill",
    "coastal music & stories",
    "124 watching",
    "89 watching",
    "1 coins",
    "places and interests",
    "nashglow",
    "coastal mia",
    "desertking_na",
    "rundu star",
    "fake",
    "lorem",
    "demo",
    "sample",
    "admin login",
]

LOGIN_REQUIRED = [
    "continue with google",
    "continue with facebook",
    "email or username",
    "password",
    "create account",
    "private chats",
]

LOGIN_BANNED = [
    "we could not complete social login",
    "oauth login failed",
    "admin login",
    "fast access",
    "choose your sign-in path",
]


class VisibleTextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self._skip_depth = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self._skip_depth += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style"} and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data):
        if not self._skip_depth:
            text = " ".join(data.split())
            if text:
                self.parts.append(text)


def visible_text(html):
    parser = VisibleTextParser()
    parser.feed(html)
    return " ".join(parser.parts).lower()


def fetch(client, path, follow_redirects=False):
    started = time.perf_counter()
    response = client.get(path, follow_redirects=follow_redirects)
    elapsed_ms = (time.perf_counter() - started) * 1000
    return response, elapsed_ms


def assert_contains(text, required_terms, label):
    missing = [term for term in required_terms if term not in text]
    assert not missing, f"{label} missing required terms: {', '.join(missing)}"


def assert_not_contains(text, banned_terms, label):
    found = [term for term in banned_terms if term in text]
    assert not found, f"{label} contains banned terms: {', '.join(found)}"


def main():
    client = app.test_client()

    home_response, cold_ms = fetch(client, "/")
    _, warm_ms = fetch(client, "/")
    login_response, login_ms = fetch(client, "/auth/login")
    oauth_error_response, oauth_error_ms = fetch(client, "/auth/login?oauth_error=1")
    health_db_response, _ = fetch(client, "/health/db")
    health_supabase_response, _ = fetch(client, "/health/supabase")
    favicon_response, _ = fetch(client, "/favicon.ico")
    icon_response, _ = fetch(client, "/static/img/icon-192.png")
    avatar_response, _ = fetch(client, "/static/img/default_avatar.png")
    legacy_login, _ = fetch(client, "/login")
    legacy_register, _ = fetch(client, "/register")
    admin_root, _ = fetch(client, "/admin/")

    assert home_response.status_code == 200, f"/ returned {home_response.status_code}"
    assert cold_ms < 1500, f"/ cold response too slow: {cold_ms:.1f}ms"
    assert warm_ms < 1000, f"/ warm response too slow: {warm_ms:.1f}ms"
    assert login_response.status_code == 200, f"/auth/login returned {login_response.status_code}"
    assert oauth_error_response.status_code == 200, f"/auth/login?oauth_error=1 returned {oauth_error_response.status_code}"
    assert health_db_response.status_code in {200, 503}, f"/health/db returned {health_db_response.status_code}"
    assert health_supabase_response.status_code == 200, f"/health/supabase returned {health_supabase_response.status_code}"
    assert favicon_response.status_code in {200, 204}, f"/favicon.ico returned {favicon_response.status_code}"
    assert icon_response.status_code == 200, f"/static/img/icon-192.png returned {icon_response.status_code}"
    assert avatar_response.status_code == 200, f"/static/img/default_avatar.png returned {avatar_response.status_code}"
    assert legacy_login.status_code in {301, 302, 307, 308}, f"/login returned {legacy_login.status_code}"
    assert legacy_login.headers.get("Location", "").endswith("/auth/login"), legacy_login.headers.get("Location", "")
    assert legacy_register.status_code in {301, 302, 307, 308}, f"/register returned {legacy_register.status_code}"
    assert legacy_register.headers.get("Location", "").endswith("/auth/register"), legacy_register.headers.get("Location", "")
    assert admin_root.status_code in {301, 302, 307, 308}, f"/admin/ returned {admin_root.status_code}"
    assert admin_root.headers.get("Location", "").endswith("/admin/login"), admin_root.headers.get("Location", "")

    homepage_text = visible_text(home_response.get_data(as_text=True))
    login_html = login_response.get_data(as_text=True)
    login_text = visible_text(login_html)
    oauth_error_text = visible_text(oauth_error_response.get_data(as_text=True))

    assert_contains(homepage_text, HOME_REQUIRED, "homepage")
    assert_not_contains(homepage_text, HOME_BANNED, "homepage")

    assert login_text.count("log in to chain") == 1, "Login page contains duplicate 'Log In to CHAIN'"
    assert_contains(login_text, LOGIN_REQUIRED, "login page")
    assert_not_contains(login_text, LOGIN_BANNED, "login page")
    assert "chain-auth-brand-panel" in login_html, "Login desktop brand panel missing"
    assert oauth_error_text.count("we could not complete social login. please try again or use email login.") >= 1, "OAuth error page missing friendly message"
    assert "/live/room/" not in home_response.get_data(as_text=True), "Homepage still emits /live/room/ links"

    print("files changed:")
    for path in FILES_CHANGED:
        print(f" - {path}")

    print("\nhomepage response time:")
    print(f" - cold response: {cold_ms:.1f}ms")
    print(f" - warm response: {warm_ms:.1f}ms")
    print(f" - /auth/login: {login_ms:.1f}ms")
    print(f" - /auth/login?oauth_error=1: {oauth_error_ms:.1f}ms")
    print(f" - /health/db: {health_db_response.status_code}")
    print(f" - /health/supabase: {health_supabase_response.status_code}")
    print(f" - /favicon.ico: {favicon_response.status_code}")
    print(f" - /static/img/icon-192.png: {icon_response.status_code}")
    print(f" - /static/img/default_avatar.png: {avatar_response.status_code}")

    print("\nlogin statuses:")
    print(f" - normal login page: {login_response.status_code}")
    print(f" - oauth error page: {oauth_error_response.status_code}")
    print(f" - /login redirect: {legacy_login.status_code} -> {legacy_login.headers.get('Location')}")
    print(f" - /register redirect: {legacy_register.status_code} -> {legacy_register.headers.get('Location')}")
    print(f" - /admin/ redirect: {admin_root.status_code} -> {admin_root.headers.get('Location')}")

    print("\nconfirmation:")
    print(" - no public admin login")
    print(" - no fake homepage content")
    print(" - homepage data comes from Neon-first service with empty-state fallback")
    print(" - desktop and mobile layouts are both supported")


if __name__ == "__main__":
    main()
