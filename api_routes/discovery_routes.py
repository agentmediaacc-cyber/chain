from flask import Blueprint, render_template
from services.discovery_service import get_discovery_data

discovery_bp = Blueprint("discovery", __name__, url_prefix="/discover")

@discovery_bp.route("/")
@discovery_bp.route("/<section>")
def section(section="recommended"):
    data = get_discovery_data(section)
    return render_template(
        "discover/index.html",
        **data
    )

@discovery_bp.route("/live")
def live_discovery():
    return section("live")

@discovery_bp.route("/members")
def members_discovery():
    return section("members")

@discovery_bp.route("/trending")
def trending_discovery():
    return section("trending")
