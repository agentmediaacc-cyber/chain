from flask import Blueprint, flash, redirect, render_template, request

from api_routes.profile_routes import login_required
from services.marketplace_service import (
    create_album,
    create_marketplace_item,
    create_track,
    get_item_access,
    get_item,
    list_my_items,
    list_public_items,
    purchase_item,
)
from services.profile_service import get_current_profile
from services.storage_service import upload_marketplace_media, upload_cover, upload_music_track
from services.supabase_safe import safe_select

marketplace_bp = Blueprint("marketplace", __name__)


@marketplace_bp.route("/marketplace/")
def marketplace_home():
    return render_template("marketplace/index.html", items=list_public_items())


@marketplace_bp.route("/marketplace/create", methods=["GET", "POST"])
@login_required
def marketplace_create():
    current = get_current_profile()
    if request.method == "POST":
        media_url = None
        media_upload_id = None
        cover_url = None
        cover_upload_id = None
        
        # Media Upload
        media_file = request.files.get("media")
        if media_file and media_file.filename:
            res, err = upload_marketplace_media(current["id"], media_file)
            if res:
                media_url = res["public_url"]
                media_upload_id = res["upload_id"]
            else:
                flash(f"Media upload failed: {err}", "error")

        # Cover Upload
        cover_file = request.files.get("cover")
        if cover_file and cover_file.filename:
            res, err = upload_cover(current["id"], cover_file)
            if res:
                cover_url = res["public_url"]
                cover_upload_id = res["upload_id"]
            else:
                flash(f"Cover upload failed: {err}", "error")

        create_marketplace_item(
            current["id"],
            request.form.get("item_type"),
            request.form.get("title"),
            request.form.get("description"),
            media_url,
            cover_url,
            request.form.get("price_coins"),
            request.form.get("premium_locked"),
            media_upload_id=media_upload_id,
            cover_upload_id=cover_upload_id
        )
        flash("Marketplace item submitted for approval.", "success")
        return redirect("/marketplace/my-items")
    return render_template("marketplace/create.html", current=current)


@marketplace_bp.route("/marketplace/my-items")
@login_required
def marketplace_my_items():
    current = get_current_profile()
    return render_template("marketplace/my_items.html", current=current, items=list_my_items(current["id"]))


@marketplace_bp.route("/marketplace/item/<item_id>")
def marketplace_detail(item_id):
    viewer = get_current_profile()
    access = get_item_access((viewer or {}).get("id"), item_id)
    item = access.get("item")
    if not item:
        return "Marketplace item not found", 404
    return render_template("marketplace/detail.html", item=item, access=access, viewer=viewer)


@marketplace_bp.route("/marketplace/purchase/<item_id>", methods=["POST"])
@login_required
def marketplace_purchase(item_id):
    current = get_current_profile()
    ok, message = purchase_item(current["id"], item_id)
    flash("Purchase completed." if ok else message, "success" if ok else "error")
    return redirect(f"/marketplace/item/{item_id}")


@marketplace_bp.route("/marketplace/download/<purchase_id>")
@login_required
def marketplace_download(purchase_id):
    current = get_current_profile()
    rows = safe_select("chain_media_purchases", filters={"id": purchase_id}, limit=1, order_by=None)
    if not rows:
        return "This download is locked.", 404

    purchase = rows[0]
    if purchase.get("buyer_profile_id") != current.get("id"):
        return "This download is locked.", 403
    if purchase.get("purchase_status") != "completed" or not purchase.get("download_allowed", True):
        flash("This download is still locked.", "error")
        return redirect(f"/marketplace/item/{purchase.get('item_id')}")

    item = get_item(purchase.get("item_id"))
    if not item or not item.get("download_enabled") or not item.get("download_url"):
        flash("This media is not ready for download yet.", "error")
        return redirect(f"/marketplace/item/{purchase.get('item_id')}")
    return redirect(item.get("download_url"))


@marketplace_bp.route("/music/albums/create", methods=["GET", "POST"])
@login_required
def music_album_create():
    current = get_current_profile()
    if request.method == "POST":
        cover_url = None
        cover_upload_id = None
        cover_file = request.files.get("cover")
        if cover_file and cover_file.filename:
            res, err = upload_cover(current["id"], cover_file)
            if res:
                cover_url = res["public_url"]
                cover_upload_id = res["upload_id"]
            else:
                flash(f"Album cover upload failed: {err}", "error")
        
        create_album(current["id"], request.form.get("title"), request.form.get("description"), request.form.get("genre"), cover_url, request.form.get("price_coins"), cover_upload_id=cover_upload_id)
        flash("Album submitted for approval.", "success")
        return redirect("/marketplace/my-items")
    return render_template("music/create_album.html", current=current)


@marketplace_bp.route("/music/tracks/upload", methods=["GET", "POST"])
@login_required
def music_track_upload():
    current = get_current_profile()
    if request.method == "POST":
        audio_url = None
        audio_upload_id = None
        audio_file = request.files.get("audio")
        if audio_file and audio_file.filename:
            res, err = upload_music_track(current["id"], audio_file)
            if res:
                audio_url = res["public_url"]
                audio_upload_id = res["upload_id"]
            else:
                flash(f"Audio upload failed: {err}", "error")
        
        create_track(current["id"], request.form.get("album_id"), request.form.get("title"), audio_url, request.form.get("price_coins"), audio_upload_id=audio_upload_id)
        flash("Track submitted for approval.", "success")
        return redirect("/marketplace/my-items")
    return render_template("music/upload_track.html", current=current)
