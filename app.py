import os
import time
from datetime import datetime, timezone, timedelta
from flask import Flask, g, redirect, render_template, request, session
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

load_dotenv(dotenv_path=".env")

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
            "session": session
        }

    @app.route("/")
    def home():
        with timed("home"):
            return render_template("chain_home.html", **get_homepage_data())

    @app.route("/terms")
    def terms():
        return render_template("dashboard/legal.html", page_title="Terms of Service", page_intro="These terms explain how CHAIN works, what users can expect, and the standards for using premium live, chat, wallet, and discovery features.")

    @app.route("/privacy")
    def privacy():
        return render_template("dashboard/legal.html", page_title="Privacy Policy", page_intro="This page explains how CHAIN stores profile data, wallet activity, live interactions, and notifications when connected to Supabase.")

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
    app.run(debug=True)
