from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from api_routes.profile_routes import login_required
from services.profile_service import get_current_profile
from services.post_service import create_post

post_bp = Blueprint("posts", __name__, url_prefix="/posts")

@post_bp.route("/create", methods=["GET", "POST"])
@login_required
def create():
    profile = get_current_profile()
    if request.method == "POST":
        caption = request.form.get("caption")
        media_file = request.files.get("media")
        
        if not caption and not media_file:
            flash("Please provide a caption or an image.")
            return render_template("posts/create.html", profile=profile)
            
        post, error = create_post(profile["id"], caption, media_file)
        if error:
            flash(f"Error: {error}")
            return render_template("posts/create.html", profile=profile)
            
        return redirect(url_for("profile.my_profile"))
        
    return render_template("posts/create.html", profile=profile)
