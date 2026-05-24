from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for

from services.auth_service import (
    get_current_profile,
    get_current_user,
    get_oauth_url,
    handle_oauth_callback,
    check_account_availability,
    login_chain_user,
    logout_chain_user,
    refresh_chain_session,
    register_chain_user,
    set_current_user_password,
    send_password_reset,
)


auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

def _queue_oauth_error():
    session["oauth_error_message"] = "We could not complete social login. Please try again or use email login."


def _clear_oauth_error_state():
    session.pop("oauth_error_message", None)
    flashes = session.get("_flashes", [])
    if flashes:
        session["_flashes"] = [item for item in flashes if item[0] != "oauth_error"]
        if not session["_flashes"]:
            session.pop("_flashes", None)


def _should_show_oauth_error():
    if request.args.get("oauth_error"):
        return True
    if request.args.get("error"):
        return True
    if request.args.get("error_description"):
        return True
    if request.args.get("oauth") == "failed":
        return True
    return False


def _next_target(default="/profile/"):
    candidate = request.args.get("next") or session.get("auth_next") or default
    if not candidate.startswith("/"):
        return default
    return candidate


def _post_login_redirect(result):
    target = result if isinstance(result, str) and result.startswith("/") else "/profile/"
    if target == "/profile/":
        requested = session.pop("auth_next", None)
        if requested and requested.startswith("/"):
            return requested
    session.pop("auth_next", None)
    return target


def _existing_session_redirect():
    user = get_current_user()
    if not user:
        return None
    profile = get_current_profile()
    if not profile:
        return "/profile/onboarding"
    if profile.get("profile_completed"):
        return "/profile/"
    return "/profile/onboarding"


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    existing_target = _existing_session_redirect()
    if request.method == "GET" and existing_target:
        return redirect(existing_target)
    error = None
    oauth_error = None
    if request.method == "POST":
        ok, result = login_chain_user(request.form.get("login_id"), request.form.get("password"))
        if ok:
            return redirect(_post_login_redirect(result))
        error = result
    if request.args.get("next"):
        session["auth_next"] = request.args.get("next")
    if request.method == "GET":
        if _should_show_oauth_error():
            oauth_error = session.pop("oauth_error_message", None) or "We could not complete social login. Please try again or use email login."
        else:
            _clear_oauth_error_state()
    return render_template("auth/login.html", error=error, oauth_error=oauth_error, next_path=session.get("auth_next"))


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    existing_target = _existing_session_redirect()
    if request.method == "GET" and existing_target:
        return redirect(existing_target)
    error = None
    if request.method == "POST":
        password = request.form.get("password") or ""
        confirm_password = request.form.get("confirm_password") or ""
        if password != confirm_password:
            error = "Passwords do not match."
            return render_template("auth/register.html", error=error)
        ok, result = register_chain_user(
            request.form.get("email"),
            request.form.get("password"),
            request.form.get("username"),
            request.form.get("full_name"),
            extra={
                "phone": request.form.get("phone"),
                "country_origin": request.form.get("country_origin"),
                "current_location": request.form.get("town") or request.form.get("current_location"),
                "town": request.form.get("town"),
                "region": request.form.get("region"),
                "profile_type": request.form.get("profile_type"),
                "dating_mode_enabled": request.form.get("dating_mode_enabled"),
                "premium_mode_enabled": request.form.get("premium_mode_enabled"),
                "terms_accepted": request.form.get("terms"),
                "human_confirmed": request.form.get("human_confirmed"),
            },
        )
        if ok:
            return redirect(_post_login_redirect(result))
        error = result
    return render_template("auth/register.html", error=error)


@auth_bp.route("/check-availability")
def check_availability():
    field = request.args.get("field")
    value = request.args.get("value")
    town = request.args.get("town")
    return jsonify(check_account_availability(field, value, town=town))


@auth_bp.route("/google")
def google_login():
    session["auth_provider"] = "google"
    session["auth_next"] = _next_target()
    url = get_oauth_url("google")
    if url:
        return redirect(url)
    _queue_oauth_error()
    return redirect(url_for("auth.login", oauth_error=1))


@auth_bp.route("/facebook")
def facebook_login():
    session["auth_provider"] = "facebook"
    session["auth_next"] = _next_target()
    url = get_oauth_url("facebook")
    if url:
        return redirect(url)
    _queue_oauth_error()
    return redirect(url_for("auth.login", oauth_error=1))


@auth_bp.route("/google/callback")
@auth_bp.route("/facebook/callback")
def oauth_callback():
    provider = request.path.split("/")[2]
    if not request.args.get("code"):
        print(f"[auth.oauth_callback] {provider} callback missing code: {dict(request.args)}")
        _queue_oauth_error()
        return redirect(url_for("auth.login", oauth_error=1))
    ok, result = handle_oauth_callback(provider, request.args)
    if ok:
        session["auth_provider"] = provider
        return redirect(_post_login_redirect(result))
    _queue_oauth_error()
    return redirect(url_for("auth.login", oauth_error=1))


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    error = None
    success = None
    if request.method == "POST":
        ok, result = send_password_reset(request.form.get("email", ""))
        if ok:
            success = result
        else:
            error = result
    return render_template("auth/forgot_password.html", error=error, success=success)


@auth_bp.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    error = None
    success = None
    if request.method == "POST":
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        if len(password) < 8:
            error = "Password must be at least 8 characters."
        elif password != confirm_password:
            error = "Passwords do not match."
        else:
            ok, result = set_current_user_password(password)
            if ok:
                success = result
            else:
                error = result
    return render_template("auth/reset_password.html", error=error, success=success)


@auth_bp.route("/logout")
def logout():
    logout_chain_user()
    return redirect("/")


@auth_bp.route("/me")
def me():
    user = get_current_user()
    profile = get_current_profile()
    if not user:
        refresh_chain_session()
        user = get_current_user()
        profile = get_current_profile()
    if not user:
        return {"error": "Unauthorized"}, 401
    return {
        "auth_user_id": getattr(user, "id", None),
        "email": getattr(user, "email", None),
        "username": (profile or {}).get("username"),
        "profile_id": (profile or {}).get("id"),
    }
