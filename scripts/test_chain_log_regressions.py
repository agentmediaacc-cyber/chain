import time

from app import app
import api_routes.profile_routes as profile_routes


def fetch(client, path, follow_redirects=False):
    started = time.perf_counter()
    response = client.get(path, follow_redirects=follow_redirects)
    elapsed_ms = (time.perf_counter() - started) * 1000
    return response, elapsed_ms


def main():
    client = app.test_client()

    home_cold, cold_ms = fetch(client, "/")
    home_warm, warm_ms = fetch(client, "/")
    login_normal, _ = fetch(client, "/auth/login")
    login_error, _ = fetch(client, "/auth/login?oauth_error=1")
    favicon, _ = fetch(client, "/favicon.ico")
    icon, _ = fetch(client, "/static/img/icon-192.png")
    avatar, _ = fetch(client, "/static/img/default_avatar.png")

    assert home_cold.status_code == 200, home_cold.status_code
    assert home_warm.status_code == 200, home_warm.status_code
    assert cold_ms < 1500, f"Homepage cold response too slow: {cold_ms:.1f}ms"
    assert warm_ms < 1000, f"Homepage warm response too slow: {warm_ms:.1f}ms"
    assert login_normal.status_code == 200, login_normal.status_code
    assert login_error.status_code == 200, login_error.status_code
    assert favicon.status_code in {200, 204}, favicon.status_code
    assert icon.status_code == 200, icon.status_code
    assert avatar.status_code == 200, avatar.status_code

    normal_text = login_normal.get_data(as_text=True).lower()
    error_text = login_error.get_data(as_text=True).lower()
    home_html = home_cold.get_data(as_text=True).lower()

    assert "we could not complete social login" not in normal_text, "Normal login still shows OAuth warning"
    assert "we could not complete social login. please try again or use email login." in error_text
    assert "/live/room/" not in home_html, "Homepage still emits broken live room detail links"

    original_get_current_profile = profile_routes.get_current_profile
    original_bootstrap = profile_routes.bootstrap_profile_for_current_user
    try:
        profile_routes.get_current_profile = lambda: None
        profile_routes.bootstrap_profile_for_current_user = lambda: (False, "Profile could not be saved yet.")
        with client.session_transaction() as session:
            session["auth_user_id"] = "test-auth-user"
            session["email"] = "test@example.com"
            session["username"] = "testuser"
        onboarding_response, _ = fetch(client, "/profile/onboarding")
        onboarding_html = onboarding_response.get_data(as_text=True).lower()
        assert onboarding_response.status_code == 200, onboarding_response.status_code
        assert "your account was created, but your profile could not be saved yet" in onboarding_html
        assert "/auth/register" not in onboarding_response.headers.get("Location", ""), onboarding_response.headers.get("Location", "")
    finally:
        profile_routes.get_current_profile = original_get_current_profile
        profile_routes.bootstrap_profile_for_current_user = original_bootstrap

    print("route/test results:")
    print(f" - / cold -> {home_cold.status_code} in {cold_ms:.1f}ms")
    print(f" - / warm -> {home_warm.status_code} in {warm_ms:.1f}ms")
    print(f" - /auth/login -> {login_normal.status_code}")
    print(f" - /auth/login?oauth_error=1 -> {login_error.status_code}")
    print(f" - /favicon.ico -> {favicon.status_code}")
    print(f" - /static/img/icon-192.png -> {icon.status_code}")
    print(f" - /static/img/default_avatar.png -> {avatar.status_code}")
    print(" - /profile/onboarding bootstrap failure -> 200 error page")


if __name__ == "__main__":
    main()
