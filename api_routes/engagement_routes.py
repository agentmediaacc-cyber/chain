from flask import Blueprint, request, jsonify, flash, redirect, url_for
from api_routes.profile_routes import login_required
from services.profile_service import get_current_profile
from services.engagement_service import (
    follow_profile,
    unfollow_profile,
    react_to_post,
    comment_on_post,
    react_to_live,
    comment_on_live,
    save_item
)

engagement_bp = Blueprint("engagement", __name__)

@engagement_bp.route("/follow/<profile_id>", methods=["POST"])
@login_required
def follow(profile_id):
    current = get_current_profile()
    ok, err = follow_profile(current["id"], profile_id)
    if not ok:
        return jsonify({"status": "error", "message": err}), 400
    return jsonify({"status": "success"})

@engagement_bp.route("/unfollow/<profile_id>", methods=["POST"])
@login_required
def unfollow(profile_id):
    current = get_current_profile()
    unfollow_profile(current["id"], profile_id)
    return jsonify({"status": "success"})

@engagement_bp.route("/posts/<post_id>/react", methods=["POST"])
@login_required
def post_react(post_id):
    current = get_current_profile()
    reaction_type = request.json.get("reaction_type", "like")
    react_to_post(current["id"], post_id, reaction_type)
    return jsonify({"status": "success"})

@engagement_bp.route("/posts/<post_id>/comment", methods=["POST"])
@login_required
def post_comment(post_id):
    current = get_current_profile()
    body = request.form.get("body") or request.json.get("body")
    res = comment_on_post(current["id"], post_id, body)
    if not res:
        return jsonify({"status": "error", "message": "Failed to post comment"}), 400
    return jsonify({"status": "success", "comment": res})

@engagement_bp.route("/live/<room_id>/react", methods=["POST"])
@login_required
def live_react(room_id):
    current = get_current_profile()
    reaction_type = request.json.get("reaction_type", "heart")
    react_to_live(room_id, current["id"], reaction_type)
    return jsonify({"status": "success"})

@engagement_bp.route("/live/<room_id>/comment", methods=["POST"])
@login_required
def live_comment_route(room_id):
    current = get_current_profile()
    body = request.form.get("body") or request.json.get("body")
    comment_on_live(room_id, current["id"], body)
    return jsonify({"status": "success"})

@engagement_bp.route("/save-item", methods=["POST"])
@login_required
def bookmark_item():
    current = get_current_profile()
    item_type = request.json.get("item_type")
    item_id = request.json.get("item_id")
    save_item(current["id"], item_type, item_id)
    return jsonify({"status": "success"})
