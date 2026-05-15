from flask import Blueprint, flash, redirect, render_template, request, url_for
from api_routes.profile_routes import login_required
from services.profile_service import get_current_profile
from services.live_media_service import (
    update_live_room_media,
    attach_mp3_to_live,
    set_youtube_embed,
    toggle_comments_gifts
)
from services.live_service import get_room

live_media_bp = Blueprint("live_media", __name__, url_prefix="/live/room")

@live_media_bp.route("/<room_id>/media")
@login_required
def media_controls(room_id):
    profile = get_current_profile()
    room = get_room(room_id)
    if not room or (room.get('host_profile_id') != profile['id'] and room.get('profile_id') != profile['id']):
        flash("Unauthorized access to room controls.", "error")
        return redirect(url_for("live.live_channels"))
    
    return render_template("live/media_controls.html", room=room, profile=profile)

@live_media_bp.route("/<room_id>/media/update", methods=["POST"])
@login_required
def update_media(room_id):
    profile = get_current_profile()
    res, err = update_live_room_media(room_id, profile["id"], request.form, request.files)
    if err:
        flash(err, "error")
    else:
        flash("Room media settings updated.", "success")
    return redirect(url_for("live_media.media_controls", room_id=room_id))

@live_media_bp.route("/<room_id>/music/upload", methods=["POST"])
@login_required
def upload_music(room_id):
    profile = get_current_profile()
    music_file = request.files.get("music")
    res, err = attach_mp3_to_live(room_id, profile["id"], music_file)
    if err:
        flash(err, "error")
    else:
        flash("Background music attached.", "success")
    return redirect(url_for("live_media.media_controls", room_id=room_id))

@live_media_bp.route("/<room_id>/youtube", methods=["POST"])
@login_required
def update_youtube(room_id):
    profile = get_current_profile()
    youtube_url = request.form.get("youtube_url")
    res, err = set_youtube_embed(room_id, profile["id"], youtube_url)
    if err:
        flash(err, "error")
    else:
        flash("YouTube embed updated.", "success")
    return redirect(url_for("live_media.media_controls", room_id=room_id))

@live_media_bp.route("/<room_id>/settings", methods=["POST"])
@login_required
def update_settings(room_id):
    profile = get_current_profile()
    comments_enabled = request.form.get("comments_enabled") == 'on'
    gifts_enabled = request.form.get("gifts_enabled") == 'on'
    res, err = toggle_comments_gifts(room_id, profile["id"], comments_enabled, gifts_enabled)
    if err:
        flash(err, "error")
    else:
        flash("Room interactions updated.", "success")
    return redirect(url_for("live_media.media_controls", room_id=room_id))
