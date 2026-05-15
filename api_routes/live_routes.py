from flask import Blueprint, jsonify, redirect, render_template, request, url_for
from services.live_service import (
    create_live_room,
    get_live_rooms,
    get_room,
    join_room,
    room_activity,
    add_comment,
    send_gift,
    end_live,
    request_cohost,
    get_cohost_requests,
    update_cohost_status,
)
from services.realtime_service import track_live_reaction
from api_routes.profile_routes import login_required
from services.profile_service import get_current_profile
from services.supabase_safe import safe_select

live_bp = Blueprint("live", __name__, url_prefix="/live")

@live_bp.route("/api/react/<room_id>", methods=["POST"])
@login_required
def react_api(room_id):
    current = get_current_profile()
    data = request.json or {}
    r_type = data.get("type", "heart")
    track_live_reaction(room_id, current["id"], r_type)
    return jsonify({"status": "ok"})


@live_bp.route("/")
def live_channels():
    rooms = get_live_rooms()
    return render_template("live/channels.html", rooms=rooms)


@live_bp.route("/studio", methods=["GET", "POST"])
@login_required
def studio():
    if request.method == "POST":
        room = create_live_room(request.form, request.files)
        if not room:
            return render_template("live/studio.html", error="We could not save this live room with the current Supabase schema.")
        return redirect(url_for("live.watch_room", room_id=room["id"]))
    return render_template("live/studio.html")


@live_bp.route("/room/<room_id>")
def watch_room(room_id):
    room = get_room(room_id)
    if not room:
        return "Live room not found", 404

    join_room(room_id, request.args.get("name"))
    gift_catalog = safe_select("chain_gift_catalog", filters={"is_active": True}, limit=8, order_by="coin_price", desc=False)
    return render_template("live/watch.html", room=room, activity=room_activity(room_id), gift_catalog=gift_catalog)


@live_bp.route("/room/<room_id>/activity")
def activity(room_id):
    return jsonify(room_activity(room_id))


@live_bp.route("/room/<room_id>/request-cohost", methods=["POST"])
def cohost_request(room_id):
    request_cohost(room_id, request.form.get("display_name"))
    return jsonify({"status": "requested"})


@live_bp.route("/room/<room_id>/cohost/<request_id>/<status>", methods=["POST"])
def cohost_status(room_id, request_id, status):
    update_cohost_status(request_id, status)
    return jsonify({"status": status})


@live_bp.route("/room/<room_id>/comment", methods=["POST"])
def comment(room_id):
    add_comment(room_id, request.form.get("body") or request.form.get("comment"), request.form.get("display_name"))
    return redirect(url_for("live.watch_room", room_id=room_id))


@live_bp.route("/room/<room_id>/gift", methods=["POST"])
def gift(room_id):
    send_gift(
        room_id,
        request.form.get("gift_icon") or request.form.get("emoji"),
        request.form.get("gift_name"),
        request.form.get("amount") or request.form.get("coins"),
        request.form.get("display_name"),
    )
    return redirect(url_for("live.watch_room", room_id=room_id))


@live_bp.route("/room/<room_id>/end", methods=["GET", "POST"])
def end(room_id):
    end_live(room_id)
    return redirect(url_for("live.live_channels"))
