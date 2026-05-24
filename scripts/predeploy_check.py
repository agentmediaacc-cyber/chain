import os
import time
from html.parser import HTMLParser
from urllib.parse import urlparse

from app import app
from services.neon_service import get_neon_health


REQUIRED_ENV_KEYS = [
    "DATABASE_URL",
    "SUPABASE_URL",
    "SUPABASE_ANON_KEY",
    "SUPABASE_SERVICE_ROLE_KEY",
]

REQUIRED_FILES = [
    "static/img/favicon.ico",
    "static/img/icon-192.png",
    "static/img/default_avatar.png",
    "templates/chain_home.html",
    "templates/auth/login.html",
    "templates/auth/register.html",
    "templates/auth/profile_error.html",
]

HOME_BANNED = [
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

SAFE_STATUS_CODES = {200, 301, 302, 303, 307, 308}


class VisibleTextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.skip_depth = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.skip_depth += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style"} and self.skip_depth:
            self.skip_depth -= 1

    def handle_data(self, data):
        if self.skip_depth:
            return
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


def extract_links(html):
    hrefs = []
    marker = 'href="'
    start = 0
    while True:
        idx = html.find(marker, start)
        if idx == -1:
            break
        idx += len(marker)
        end = html.find('"', idx)
        if end == -1:
            break
        href = html[idx:end]
        start = end + 1
        if href.startswith(("http://", "https://", "mailto:", "tel:", "/static/")):
            continue
        if href in {"#", "javascript:void(0)"}:
            raise AssertionError(f"Broken visible link found: {href}")
        hrefs.append(href)
    return sorted(set(hrefs))


def main():
    missing_env = [key for key in REQUIRED_ENV_KEYS if not os.getenv(key)]
    assert not missing_env, f"Missing required env keys: {', '.join(missing_env)}"

    missing_files = [path for path in REQUIRED_FILES if not os.path.exists(path)]
    assert not missing_files, f"Missing required files: {', '.join(missing_files)}"

    neon_health = get_neon_health()
    assert neon_health.get("configured"), "Neon DATABASE_URL missing"
    assert neon_health.get("connected"), f"Neon unavailable: {neon_health.get('error')}"

    client = app.test_client()
    home_cold, cold_ms = fetch(client, "/")
    home_warm, warm_ms = fetch(client, "/")
    login_response, _ = fetch(client, "/auth/login")
    register_response, _ = fetch(client, "/auth/register")
    supabase_health, _ = fetch(client, "/health/supabase")

    assert home_cold.status_code == 200, home_cold.status_code
    assert home_warm.status_code == 200, home_warm.status_code
    assert cold_ms < 1000, f"Homepage cold too slow: {cold_ms:.1f}ms"
    assert warm_ms < 1000, f"Homepage warm too slow: {warm_ms:.1f}ms"
    assert login_response.status_code == 200, login_response.status_code
    assert register_response.status_code == 200, register_response.status_code
    assert supabase_health.status_code == 200, supabase_health.status_code

    home_html = home_cold.get_data(as_text=True)
    home_text = visible_text(home_html)
    login_text = visible_text(login_response.get_data(as_text=True))

    for term in HOME_BANNED:
        assert term not in home_text, f"Homepage contains banned text: {term}"
    assert "admin login" not in login_text, "Public login exposes admin login"

    links = extract_links(home_html)
    route_results = {}
    for link in links:
        path = urlparse(link).path or link
        response, _ = fetch(client, path)
        route_results[path] = response.status_code
        assert response.status_code in SAFE_STATUS_CODES, f"{path} returned {response.status_code}"

    print("predeploy result:")
    print(" - env keys present")
    print(f" - neon connected: {neon_health.get('connected')} ({neon_health.get('latency_ms')}ms)")
    print(" - supabase keys present")
    print(" - required static/templates present")
    print(f" - homepage cold: {cold_ms:.1f}ms")
    print(f" - homepage warm: {warm_ms:.1f}ms")
    print(f" - /auth/login: {login_response.status_code}")
    print(f" - /auth/register: {register_response.status_code}")
    print(" - no fake homepage content")
    print(" - no public admin login")
    print(" - no visible homepage link returns 404")
    for path, status in sorted(route_results.items()):
        print(f" - {path} -> {status}")


if __name__ == "__main__":
    main()
