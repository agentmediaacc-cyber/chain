from flask import Blueprint, jsonify, redirect, render_template, url_for
from services.notification_service import (
    get_unread_notification_count,
    get_my_notifications,
    mark_notification_read,
    mark_all_read,
)
from api_routes.profile_routes import login_required

notification_bp = Blueprint("notifications", __name__, url_prefix="/notifications")
notification_api_bp = Blueprint("notifications_api", __name__, url_prefix="/api/notifications")


@notification_bp.route("/")
@login_required
def inbox():
    notifications, current, unread = get_my_notifications()
    return render_template(
        "notifications/index.html",
        notifications=notifications,
        current=current,
        unread=unread,
    )


@notification_bp.route("/read/<notification_id>")
@login_required
def read_one(notification_id):
    mark_notification_read(notification_id)
    return redirect(url_for("notifications.inbox"))


@notification_bp.route("/open/<notification_id>")
@login_required
def open_notification(notification_id):
    notifications, current, unread = get_my_notifications(limit=100)

    target = "/notifications/"
    for n in notifications:
        if n["id"] == notification_id:
            target = n.get("target_url") or "/notifications/"
            break

    mark_notification_read(notification_id)
    return redirect(target)


@notification_bp.route("/read-all")
@login_required
def read_all():
    mark_all_read()
    return redirect(url_for("notifications.inbox"))


@notification_api_bp.route("/unread-count")
def unread_count():
    return jsonify({"count": get_unread_notification_count()})
