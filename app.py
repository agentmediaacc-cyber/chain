import os
import time
from datetime import datetime, timezone, timedelta
from flask import Flask, g, jsonify, redirect, render_template, request, session, send_from_directory
from engines.cache_engine import init_cache
from engines.performance_engine import timed
from engines.scheduler_engine import init_scheduler
from dotenv import load_dotenv

from api_routes.auth_routes import auth_bp
from api_routes.profile_routes import profile_bp
from api_routes.matching_routes import matching_bp
from api_routes.dating_routes import dating_bp
from api_routes.chat_routes import chat_bp
from api_routes.call_routes import call_bp
from api_routes.notification_routes import notification_api_bp, notification_bp
from api_routes.live_routes import live_bp
from api_routes.wallet_routes import wallet_bp
from api_routes.admin_routes import admin_bp, developer_bp
from api_routes.discovery_routes import discovery_bp
from api_routes.activity_routes import activity_bp
from api_routes.search_routes import search_api_bp, search_bp
from api_routes.marketplace_routes import marketplace_bp
from api_routes.status_routes import status_bp
from api_routes.live_media_routes import live_media_bp
from api_routes.realtime_routes import realtime_bp
from api_routes.reels_routes import reels_bp
from api_routes.mobile_api_routes import mobile_api_bp
from api_routes.engagement_routes import engagement_bp

from services.homepage_service import get_homepage_data
from services.profile_service import get_current_profile, get_profile_by_username
from services.notification_service import get_my_notifications
from services.auth_service import get_current_user, refresh_chain_session
from api_routes.profile_routes import login_required
from services.neon_service import get_neon_health, prime_neon_runtime
from utils.supabase_client import SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_URL, get_supabase, get_supabase_admin

load_dotenv(dotenv_path=".env")
_SUPABASE_HEALTH_CACHE = {"expires_at": 0.0, "payload": None}

def create_app():
    app = Flask(__name__)
    app.secret_key = os.getenv("SECRET_KEY", "chain-premium-default-secret")
    
    # Production Security Settings
    app.config.update(
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        PERMANENT_SESSION_LIFETIME=timedelta(days=7)
    )
    
    init_cache(app)
    init_scheduler(app)
    app.config.from_object("config.settings.Config")
    try:
        prime_neon_runtime(
            [
                "chain_profiles",
                "chain_posts",
                "chain_stories",
                "chain_status_posts",
                "chain_reels",
                "chain_live_rooms",
                "chain_media_uploads",
            ]
        )
    except Exception as error:
        print(f"[app] Neon warm-up skipped: {error}")

    app.register_blueprint(auth_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(matching_bp)
    app.register_blueprint(dating_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(call_bp)
    app.register_blueprint(notification_bp)
    app.register_blueprint(notification_api_bp)
    app.register_blueprint(live_bp)
    app.register_blueprint(wallet_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(developer_bp)
    app.register_blueprint(discovery_bp)
    app.register_blueprint(activity_bp)
    app.register_blueprint(search_bp)
    app.register_blueprint(search_api_bp)
    app.register_blueprint(marketplace_bp)
    app.register_blueprint(status_bp)
    app.register_blueprint(live_media_bp)
    app.register_blueprint(realtime_bp)
    app.register_blueprint(reels_bp)
    app.register_blueprint(mobile_api_bp)
    app.register_blueprint(engagement_bp)

    @app.before_request
    def track_request_start():
        g.request_started_at = time.perf_counter()
        if session.get("refresh_token") and not session.get("access_token") and request.endpoint != "static":
            refresh_chain_session()

    @app.context_processor
    def inject_global_data():
        current_profile = None
        unread_count = 0
        wallet_balance = 0
        available_routes = {rule.rule for rule in app.url_map.iter_rules()}
        feature_candidates = {
            "home": ["/"],
            "discover": ["/discover/"],
            "live": ["/live/"],
            "messages": ["/messages/"],
            "wallet": ["/wallet/"],
            "profile": ["/profile/"],
            "login": ["/auth/login"],
            "register": ["/auth/register"],
            "friends": ["/friends/", "/discover/"],
            "reels": ["/reels/", "/discover/"],
            "notifications": ["/notifications/", "/profile/"],
            "dating": ["/dating/discover", "/discover/"],
            "create_post": ["/features/create-post", "/posts/create", "/post/create", "/create-post", "/profile/"],
            "create_story": ["/status/create", "/profile/"],
            "upload_reel": ["/features/upload-reel", "/reels/", "/profile/"],
            "upload_video": ["/features/upload-video", "/upload/video", "/media/upload", "/profile/"],
            "go_live": ["/live/studio", "/live/"],
            "settings": ["/profile/settings", "/discover/"],
            "help": ["/discover/"],
        }

        def safe_link(feature_name, logged_in=None):
            signed_in = current_profile is not None if logged_in is None else bool(logged_in)
            fallback_logged_in = "/profile/" if signed_in else "/auth/login"
            fallback_logged_out = "/auth/login"
            candidates = feature_candidates.get(feature_name, [])
            for candidate in candidates:
                if candidate in available_routes:
                    if not signed_in and candidate.startswith(("/messages/", "/wallet/", "/profile/", "/notifications/")):
                        return fallback_logged_out
                    return candidate
            return fallback_logged_in if signed_in else fallback_logged_out
        
        # Priority: auth_user_id in session
        if "auth_user_id" in session:
            current_profile = get_current_profile()
        
        if current_profile:
            _, _, unread_count = get_my_notifications()
            # Fetch wallet
            from services.wallet_service import ensure_wallet
            wallet = ensure_wallet(current_profile["id"])
            if wallet:
                wallet_balance = wallet.get("coin_balance", 0)

        return {
            "g_current": current_profile,
            "g_unread_count": unread_count,
            "g_wallet_balance": wallet_balance,
            "session": session,
            "safe_link": safe_link,
        }

    @app.route("/")
    def home():
        with timed("home"):
            return render_template("chain_home.html", **get_homepage_data())

    @app.route("/login")
    def legacy_login():
        return redirect("/auth/login", code=302)

    @app.route("/register")
    def legacy_register():
        return redirect("/auth/register", code=302)

    @app.route("/terms")
    def terms():
        return render_template("dashboard/legal.html", page_title="Terms of Service", page_intro="These terms explain how CHAIN works, what users can expect, and the standards for using premium live, chat, wallet, and discovery features.")

    @app.route("/privacy")
    def privacy():
        return render_template("dashboard/legal.html", page_title="Privacy Policy", page_intro="This page explains how CHAIN stores profile data, wallet activity, live interactions, and notifications when connected to Supabase.")

    @app.route("/health/db")
    def health_db():
        health = get_neon_health()
        status = 200 if health.get("connected") else 503
        return jsonify({"service": "neon", **health}), status

    @app.route("/health/supabase")
    def health_supabase():
        now = time.monotonic()
        cached = _SUPABASE_HEALTH_CACHE.get("payload")
        if cached is not None and _SUPABASE_HEALTH_CACHE.get("expires_at", 0) > now:
            return jsonify(cached), 200
        health = {
            "service": "supabase",
            "url_present": bool(SUPABASE_URL),
            "anon_key_present": bool(SUPABASE_ANON_KEY),
            "service_role_present": bool(SUPABASE_SERVICE_ROLE_KEY),
            "client_ready": False,
            "admin_ready": False,
            "auth_ready": False,
            "storage_ready": False,
            "error": None,
        }
        try:
            client = get_supabase()
            admin = get_supabase_admin()
            health["client_ready"] = True
            health["admin_ready"] = True
            health["auth_ready"] = hasattr(client, "auth")
            storage = getattr(admin, "storage", None)
            health["storage_ready"] = storage is not None
            if storage is not None and hasattr(storage, "list_buckets"):
                try:
                    storage.list_buckets()
                    health["storage_reachable"] = True
                except Exception as error:
                    health["storage_reachable"] = False
                    health["storage_error"] = str(error)
        except Exception as error:
            health["error"] = str(error)
        _SUPABASE_HEALTH_CACHE["payload"] = dict(health)
        _SUPABASE_HEALTH_CACHE["expires_at"] = now + 30
        status = 200 if health["url_present"] and health["anon_key_present"] and health["service_role_present"] else 503
        return jsonify(health), status

    @app.route("/features/create-post")
    @login_required
    def feature_create_post():
        return render_template(
            "dashboard/feature_page.html",
            title="Create Post",
            section="feature",
            message="Post creation is being connected to the live CHAIN publishing flow.",
        )

    @app.route("/features/upload-reel")
    @login_required
    def feature_upload_reel():
        return render_template(
            "dashboard/feature_page.html",
            title="Upload Reel",
            section="feature",
            message="Reel upload is being connected to the live CHAIN media flow.",
        )

    @app.route("/features/upload-video")
    @login_required
    def feature_upload_video():
        return render_template(
            "dashboard/feature_page.html",
            title="Upload Video",
            section="feature",
            message="Video upload is being connected to the live CHAIN media flow.",
        )

    @app.route("/favicon.ico")
    def favicon():
        favicon_path = os.path.join(app.static_folder or "static", "img", "favicon.ico")
        if os.path.exists(favicon_path):
            return send_from_directory(os.path.join(app.static_folder, "img"), "favicon.ico")
        return ("", 204)

    @app.errorhandler(404)
    def page_not_found(e):
        return render_template("dashboard/feature_page.html", title="404 - Not Found", section="error"), 404

    @app.after_request
    def apply_response_headers(response):
        started = getattr(g, "request_started_at", None)
        if started is not None:
            elapsed_ms = (time.perf_counter() - started) * 1000
            response.headers["X-Response-Time-ms"] = f"{elapsed_ms:.1f}"
            if elapsed_ms >= app.config.get("SLOW_REQUEST_MS", 1500):
                print(f"[slow-request] {request.method} {request.path} -> {elapsed_ms:.1f}ms")

        response.headers.setdefault("Vary", "Accept-Encoding, Cookie")
        if request.path.startswith("/static/"):
            response.headers["Cache-Control"] = "public, max-age=86400"
        elif request.method == "GET" and request.path in {"/", "/search", "/discover/", "/discover/live", "/discover/members", "/live/"}:
            response.headers["Cache-Control"] = "public, max-age=30"
        elif request.method == "GET" and request.path.startswith(("/auth/", "/profile/", "/chat/", "/wallet/", "/notifications/")):
            response.headers["Cache-Control"] = "no-store"
        return response

    return app

app = create_app()

if __name__ == "__main__":
    is_production = os.getenv("FLASK_ENV") == "production" or os.getenv("ENV") == "production"
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=not is_production, use_reloader=not is_production)
