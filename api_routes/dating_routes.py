from flask import Blueprint, render_template

dating_bp = Blueprint("dating", __name__, url_prefix="/dating")

@dating_bp.route("/discover")
def discover():
    return render_template("dating/discover.html")
