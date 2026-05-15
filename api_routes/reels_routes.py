from flask import Blueprint, render_template, request, jsonify
from services.profile_service import get_current_profile
from services.supabase_safe import safe_select, safe_insert, safe_update
from api_routes.profile_routes import login_required

reels_bp = Blueprint("reels", __name__, url_prefix="/reels")

@reels_bp.route("/")
def index():
    current = get_current_profile()
    reels = safe_select("chain_reels", limit=20, order_by="created_at", desc=True)
    # Enrich with profile info
    for reel in reels:
        profile = (safe_select("chain_profiles", filters={"id": reel["profile_id"]}, limit=1) or [{}])[0]
        reel["creator"] = profile
        
    return render_template("reels/index.html", reels=reels, current=current)

@reels_bp.route("/upload", methods=["POST"])
@login_required
def upload_reel():
    current = get_current_profile()
    data = request.form
    file = request.files.get("video")
    
    if not file:
        return jsonify({"error": "No video file provided"}), 400
        
    # In a real app, upload to Supabase Storage and get URL
    # For now, we simulate the record creation
    payload = {
        "profile_id": current["id"],
        "video_url": f"https://example.com/videos/{file.filename}", # Placeholder
        "caption": data.get("caption"),
        "is_private": data.get("is_private") == 'true'
    }
    safe_insert("chain_reels", payload)
    return jsonify({"status": "ok"})

@reels_bp.route("/<reel_id>/react", methods=["POST"])
@login_required
def react_reel(reel_id):
    current = get_current_profile()
    # Increment reaction count
    reel = (safe_select("chain_reels", filters={"id": reel_id}, limit=1) or [None])[0]
    if reel:
        safe_update("chain_reels", {"likes_count": reel.get("likes_count", 0) + 1}, eq={"id": reel_id})
        return jsonify({"status": "ok"})
    return jsonify({"error": "Reel not found"}), 404
