import os
import time
from datetime import datetime, timezone
from functools import wraps

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from werkzeug.utils import secure_filename

from services.auth_service import refresh_chain_session, set_current_user_password
from services.notification_service import get_my_notifications
from services.profile_service import (
    block_profile,
    bootstrap_profile_for_current_user,
    create_or_update_profile,
    favorite_profile,
    follow_profile,
    get_current_profile,
    get_profile_bundle,
    get_profile_by_username,
    get_profile_settings,
    is_profile_complete,
    like_profile,
    record_profile_view,
    report_profile,
    update_profile_setup,
)
from services.storage_service import upload_avatar, upload_cover, upload_verification_file

profile_bp = Blueprint("profile", __name__, url_prefix="/profile")

UPLOAD_MAP = {
    "avatar": "static/uploads/profile/avatars",
    "cover": "static/uploads/profile/covers",
    "verification": "static/uploads/profile/verifications",
}


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "auth_user_id" not in session:
            if session.get("refresh_token"):
                refresh_chain_session()
        if "auth_user_id" not in session:
            return redirect(url_for("auth.login", next=request.path))
        return f(*args, **kwargs)

    return decorated_function


def save_upload(file, folder):
    if not file or not file.filename:
        return None
    os.makedirs(folder, exist_ok=True)
    filename = secure_filename(file.filename)
    filename = f"{int(time.time())}_{filename}"
    path = os.path.join(folder, filename)
    file.save(path)
    return "/" + path


def _profile_form_defaults():
    return {
        "email": session.get("email"),
        "full_name": session.get("full_name", ""),
        "username": session.get("email", "").split("@")[0] if session.get("email") else "",
        "premium_tier": "free",
        "profile_type": "member",
    }


def _redirect_back(username=None):
    return redirect(request.referrer or (url_for("profile.public_profile", username=username) if username else url_for("profile.my_profile")))


@profile_bp.route("/")
@login_required
def my_profile():
    viewer = get_current_profile()
    if not viewer:
        return redirect(url_for("profile.create_profile"))
    if not is_profile_complete(viewer):
        return redirect(url_for("profile.onboarding"))

    bundle = get_profile_bundle(profile_id=viewer["id"], viewer=viewer)
    _, _, unread_count = get_my_notifications()
    return render_template("profile/index.html", unread_count=unread_count, viewer=viewer, **bundle)


@profile_bp.route("/create", methods=["GET", "POST"])
@login_required
def create_profile():
    return redirect(url_for("profile.onboarding"))


@profile_bp.route("/setup", methods=["GET", "POST"])
@login_required
def setup_profile():
    return redirect(url_for("profile.onboarding"))


@profile_bp.route("/edit", methods=["GET", "POST"])
@login_required
def edit_profile():
    viewer = get_current_profile()
    if not viewer:
        return redirect(url_for("profile.onboarding"))
    if not is_profile_complete(viewer):
        return redirect(url_for("profile.onboarding"))
    setup_mode = request.args.get("setup") == "1"

    if request.method == "POST":
        data = dict(request.form)
        
        # Avatar Upload
        avatar_file = request.files.get("avatar")
        if avatar_file and avatar_file.filename:
            res, err = upload_avatar(viewer["id"], avatar_file)
            if res:
                data["avatar_url"] = res["public_url"]
                data["avatar_upload_id"] = res["upload_id"]
            else:
                flash(f"Avatar upload failed: {err}", "error")

        # Cover Upload
        cover_file = request.files.get("cover")
        if cover_file and cover_file.filename:
            res, err = upload_cover(viewer["id"], cover_file)
            if res:
                data["cover_url"] = res["public_url"]
                data["cover_upload_id"] = res["upload_id"]
            else:
                flash(f"Cover upload failed: {err}", "error")

        ok, result = update_profile_setup(viewer["id"], data) if setup_mode else create_or_update_profile(data)
        if ok:
            return redirect(url_for("profile.my_profile"))
        return render_template("profile/edit.html", error=result, profile=viewer, form=request.form)

    progress = viewer.get("profile_completion", 0)
    return render_template("profile/edit.html", profile=viewer, form=viewer, setup_mode=setup_mode, progress=progress)


@profile_bp.route("/@<username>")
def public_profile(username):
    viewer = get_current_profile()
    bundle = get_profile_bundle(username=username, viewer=viewer)
    if not bundle:
        return render_template("profile/not_found.html", username=username), 404

    if not viewer or viewer.get("id") != bundle["profile"]["id"]:
        record_profile_view(bundle["profile"]["id"], viewer_profile_id=(viewer or {}).get("id"))

    return render_template("profile/public.html", viewer=viewer, **bundle)


@profile_bp.route("/@<username>/follow", methods=["POST"])
@login_required
def follow(username):
    follow_profile(username)
    return _redirect_back(username)


@profile_bp.route("/@<username>/like", methods=["POST"])
@login_required
def like(username):
    like_profile(username)
    return _redirect_back(username)


@profile_bp.route("/@<username>/favorite", methods=["POST"])
@login_required
def favorite(username):
    favorite_profile(username)
    return _redirect_back(username)


@profile_bp.route("/@<username>/report", methods=["POST"])
@login_required
def report(username):
    report_profile(username, reason=request.form.get("reason"))
    return _redirect_back(username)


@profile_bp.route("/@<username>/block", methods=["POST"])
@login_required
def block(username):
    block_profile(username)
    return _redirect_back(username)


@profile_bp.route("/@<username>/premium")
def premium(username):
    viewer = get_current_profile()
    bundle = get_profile_bundle(username=username, viewer=viewer)
    if not bundle:
        return render_template("profile/not_found.html", username=username), 404
    return render_template("profile/premium.html", viewer=viewer, **bundle)


@profile_bp.route("/@<username>/creator-tools")
@login_required
def creator_tools(username):
    viewer = get_current_profile()
    bundle = get_profile_bundle(username=username, viewer=viewer)
    if not bundle:
        return render_template("profile/not_found.html", username=username), 404
    return render_template("profile/creator_tools.html", viewer=viewer, **bundle)


@profile_bp.route("/settings")
@login_required
def settings():
    profile = get_current_profile()
    profile_settings = get_profile_settings(profile["id"])
    return render_template("profile/settings.html", profile=profile, profile_settings=profile_settings["settings"], account_security=profile_settings["security"])


@profile_bp.route("/onboarding", methods=["GET", "POST"])
@login_required
def onboarding():
    profile = get_current_profile()
    if not profile:
        ok, result = bootstrap_profile_for_current_user()
        if not ok:
            print("[profile_onboarding] bootstrap failed:", result)
            return render_template("auth/profile_error.html", error_detail=result), 200
        profile = get_current_profile()
        if not profile:
            return render_template("auth/profile_error.html", error_detail="Profile could not be loaded after account creation."), 200
    if request.method == "POST":
        data = dict(request.form)
        
        # Avatar Upload
        avatar_file = request.files.get("avatar") or request.files.get("camera_avatar")
        if avatar_file and avatar_file.filename:
            res, err = upload_avatar(profile["id"], avatar_file)
            if res:
                data["avatar_url"] = res["public_url"]
                data["avatar_upload_id"] = res["upload_id"]
            else:
                flash(f"Avatar upload failed: {err}", "error")

        # Cover Upload
        cover_file = request.files.get("cover")
        if cover_file and cover_file.filename:
            res, err = upload_cover(profile["id"], cover_file)
            if res:
                data["cover_url"] = res["public_url"]
                data["cover_upload_id"] = res["upload_id"]
            else:
                flash(f"Cover upload failed: {err}", "error")

        # Verification Selfie
        selfie_file = request.files.get("verification_selfie")
        if selfie_file and selfie_file.filename:
            res, err = upload_verification_file(profile["id"], selfie_file, upload_type='verification_doc')
            if res:
                data["verification_selfie_url"] = res["public_url"] or res["file_path"]
                data["verification_selfie_upload_id"] = res["upload_id"]
            else:
                flash(f"Verification selfie upload failed: {err}", "error")

        ok, result = update_profile_setup(profile["id"], data)
        if ok:
            flash("Profile setup saved.", "success")
            return redirect(url_for("profile.my_profile"))
        print("[profile_onboarding] save failed:", result)
        return render_template(
            "profile/onboarding.html",
            profile=profile,
            form=request.form,
            error="We could not finish your profile yet. Please check the highlighted fields.",
            error_detail=result,
            progress=profile.get("profile_completion", 0),
            setup_mode=True,
        )

    return render_template("profile/onboarding.html", profile=profile, form=profile, progress=profile.get("profile_completion", 0), setup_mode=True)


@profile_bp.route("/verification", methods=["GET", "POST"])
@login_required
def verification():
    profile = get_current_profile()
    if request.method == "POST":
        data = {}
        
        # Selfie Upload
        selfie_file = request.files.get("selfie")
        if selfie_file and selfie_file.filename:
            res, err = upload_verification_file(profile["id"], selfie_file, upload_type='verification_selfie')
            if res:
                data["selfie_url"] = res["public_url"] or res["file_path"]
                data["selfie_upload_id"] = res["upload_id"]
            else:
                flash(f"Selfie upload failed: {err}", "error")
                return redirect(url_for("profile.verification"))

        # ID Document Upload
        id_file = request.files.get("id_document")
        if id_file and id_file.filename:
            res, err = upload_verification_file(profile["id"], id_file, upload_type='verification_id')
            if res:
                data["id_document_url"] = res["public_url"] or res["file_path"]
                data["id_document_upload_id"] = res["upload_id"]
            else:
                flash(f"ID document upload failed: {err}", "error")
                return redirect(url_for("profile.verification"))

        if not data.get("selfie_upload_id") or not data.get("id_document_upload_id"):
            flash("Both selfie and ID document are required.", "error")
            return redirect(url_for("profile.verification"))

        # Save verification request
        from services.supabase_safe import safe_insert, safe_select, safe_update
        existing = safe_select("chain_user_verifications", filters={"profile_id": profile["id"]}, limit=1, order_by=None)
        
        payload = {
            "profile_id": profile["id"],
            "verification_status": "pending",
            "selfie_url": data.get("selfie_url"),
            "selfie_upload_id": data.get("selfie_upload_id"),
            "id_document_url": data.get("id_document_url"),
            "id_document_upload_id": data.get("id_document_upload_id"),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        if existing:
            safe_update("chain_user_verifications", payload, eq={"id": existing[0]["id"]})
        else:
            payload["created_at"] = datetime.now(timezone.utc).isoformat()
            safe_insert("chain_user_verifications", payload)
            
        flash("Verification request submitted successfully.", "success")
        return redirect(url_for("profile.my_profile"))

    from services.supabase_safe import safe_select
    verification_request = (safe_select("chain_user_verifications", filters={"profile_id": profile["id"]}, limit=1, order_by=None) or [None])[0]
    return render_template("profile/verification.html", profile=profile, verification=verification_request)


@profile_bp.route("/settings", methods=["POST"])
@login_required
def update_settings():
    profile = get_current_profile()
    settings = get_profile_settings(profile["id"])
    from services.supabase_safe import safe_insert, safe_update

    payload = {
        "allow_messages": request.form.get("allow_messages") == "on",
        "allow_video_calls": request.form.get("allow_video_calls") == "on",
        "show_online_status": request.form.get("show_online_status") == "on",
        "profile_visibility": request.form.get("profile_visibility", "public"),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if settings["settings"].get("id"):
        safe_update("chain_user_settings", payload, eq={"id": settings["settings"]["id"]})
    else:
        safe_insert("chain_user_settings", {"profile_id": profile["id"], **payload})
    flash("Settings updated.", "success")
    return redirect(url_for("profile.settings"))


@profile_bp.route("/security")
@login_required
def security():
    profile = get_current_profile()
    profile_settings = get_profile_settings(profile["id"])
    return render_template("profile/security.html", profile=profile, account_security=profile_settings["security"])


@profile_bp.route("/security/set-password", methods=["POST"])
@login_required
def set_password():
    password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")
    if len(password) < 8:
        flash("Password must be at least 8 characters.", "error")
        return redirect(url_for("profile.security"))
    if password != confirm_password:
        flash("Passwords do not match.", "error")
        return redirect(url_for("profile.security"))
    ok, result = set_current_user_password(password)
    flash(result, "success" if ok else "error")
    return redirect(url_for("profile.security"))


@profile_bp.route("/activity")
@login_required
def activity():
    viewer = get_current_profile()
    bundle = get_profile_bundle(profile_id=viewer["id"], viewer=viewer)
    return render_template("profile/index.html", viewer=viewer, **bundle)


@profile_bp.route("/live")
@login_required
def my_live():
    return redirect(url_for("live.live_channels"))


@profile_bp.route("/posts")
@login_required
def my_posts():
    return redirect(url_for("profile.my_profile"))


@profile_bp.route("/wallet")
@login_required
def my_wallet():
    return redirect(url_for("wallet.wallet_home"))


@profile_bp.route("/notifications")
@login_required
def my_notifications():
    return redirect(url_for("notifications.inbox"))


@profile_bp.route("/creator/ai-assist", methods=["POST"])
@login_required
def ai_assist():
    from services.creator_ai_service import get_caption_suggestions, generate_trending_hashtags
    data = request.json or {}
    c_type = data.get("type", "reel")
    topic = data.get("topic", "lifestyle")
    
    captions = get_caption_suggestions(c_type, topic)
    hashtags = generate_trending_hashtags(topic)
    
    return jsonify({
        "captions": captions,
        "hashtags": hashtags
    })

@profile_bp.route("/messages")
@login_required
def my_messages():
    return redirect(url_for("chat_v2.inbox"))
