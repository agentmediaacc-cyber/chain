from flask import Blueprint, request, jsonify
from api_routes.profile_routes import login_required
from services.profile_service import get_current_profile
from services.realtime_service import set_online, set_offline, update_typing

realtime_bp = Blueprint("realtime_v2", __name__, url_prefix="/realtime")

@realtime_bp.route("/presence/online", methods=["POST"])
@login_required
def presence_online():
    profile = get_current_profile()
    set_online(profile["id"])
    return jsonify({"status": "success"})

@realtime_bp.route("/presence/offline", methods=["POST"])
@login_required
def presence_offline():
    profile = get_current_profile()
    set_offline(profile["id"])
    return jsonify({"status": "success"})

@realtime_bp.route("/typing", methods=["POST"])
@login_required
def typing_status():
    profile = get_current_profile()
    conversation_id = request.json.get("conversation_id")
    is_typing = request.json.get("is_typing", False)
    update_typing(conversation_id, profile["id"], is_typing)
    return jsonify({"status": "success"})
