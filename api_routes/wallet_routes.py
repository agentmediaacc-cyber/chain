from flask import Blueprint, flash, redirect, render_template, request, url_for

from api_routes.profile_routes import login_required
from services.profile_service import get_current_profile
from services.storage_service import upload_payment_proof, upload_verification_file
from services.wallet_action_service import (
    create_pin_reset_request,
    create_topup_request,
    create_withdrawal_request,
    get_or_create_wallet,
    list_wallet_transactions,
    set_wallet_pin,
)
from services.wallet_service import get_gift_page, get_wallet_home, send_gift_to_username

wallet_bp = Blueprint("wallet", __name__, url_prefix="/wallet")


@wallet_bp.route("/")
@login_required
def wallet_home():
    current, wallet, gifts, transactions = get_wallet_home()
    wallet = get_or_create_wallet(current["id"]) if current else wallet
    transactions = list_wallet_transactions(current["id"]) if current else transactions
    topups = [] if not current else []
    withdrawals = [] if not current else []
    if current:
        from services.supabase_safe import safe_select
        topups = safe_select("chain_wallet_topups", filters={"profile_id": current["id"]}, limit=10)
        withdrawals = safe_select("chain_wallet_withdrawals", filters={"profile_id": current["id"]}, limit=10)
    return render_template("wallet/index.html", current=current, wallet=wallet, gifts=gifts, transactions=transactions, topups=topups, withdrawals=withdrawals)


@wallet_bp.route("/top-up", methods=["GET", "POST"])
@login_required
def top_up():
    current = get_current_profile()
    if request.method == "POST":
        proof_url = None
        proof_upload_id = None
        proof_file = request.files.get("proof")
        if proof_file and proof_file.filename:
            res, err = upload_payment_proof(current["id"], proof_file)
            if res:
                proof_url = res["public_url"] or res["file_path"]
                proof_upload_id = res["upload_id"]
            else:
                flash(f"Proof upload failed: {err}", "error")

        ok, result = create_topup_request(current["id"], request.form.get("amount_nad"), request.form.get("payment_method"), proof_url=proof_url, proof_upload_id=proof_upload_id)
        flash(result.get("reference") if ok and isinstance(result, dict) else result, "success" if ok else "error")
        return redirect(url_for("wallet.wallet_home"))
    wallet = get_or_create_wallet(current["id"])
    return render_template("wallet/topup.html", current=current, wallet=wallet)


@wallet_bp.route("/withdraw", methods=["GET", "POST"])
@login_required
def withdraw():
    current = get_current_profile()
    if request.method == "POST":
        ok, result = create_withdrawal_request(
            current["id"],
            request.form.get("coins"),
            {
                "destination_method": request.form.get("destination_method"),
                "destination_reference": request.form.get("destination_reference"),
            },
        )
        flash("Withdrawal request submitted." if ok else result, "success" if ok else "error")
        return redirect(url_for("wallet.wallet_home"))
    wallet = get_or_create_wallet(current["id"])
    return render_template("wallet/withdraw.html", current=current, wallet=wallet)


@wallet_bp.route("/pin", methods=["GET", "POST"])
@login_required
def wallet_pin():
    current = get_current_profile()
    if request.method == "POST":
        ok, message = set_wallet_pin(current["id"], request.form.get("pin"))
        flash("Wallet PIN saved." if ok else message, "success" if ok else "error")
        return redirect(url_for("wallet.wallet_home"))
    wallet = get_or_create_wallet(current["id"])
    return render_template("wallet/pin.html", current=current, wallet=wallet)


@wallet_bp.route("/pin/reset", methods=["GET", "POST"])
@login_required
def wallet_pin_reset():
    current = get_current_profile()
    if request.method == "POST":
        id_copy_url = None
        id_copy_upload_id = None
        id_file = request.files.get("id_copy")
        if id_file and id_file.filename:
            res, err = upload_verification_file(current["id"], id_file, upload_type='pin_reset_id')
            if res:
                id_copy_url = res["public_url"] or res["file_path"]
                id_copy_upload_id = res["upload_id"]
            else:
                flash(f"ID copy upload failed: {err}", "error")

        ok, result = create_pin_reset_request(current["id"], id_copy_url, request.form.get("reason"), id_copy_upload_id=id_copy_upload_id)
        flash("PIN reset request submitted." if ok else result, "success" if ok else "error")
        return redirect(url_for("wallet.wallet_home"))
    wallet = get_or_create_wallet(current["id"])
    return render_template("wallet/pin.html", current=current, wallet=wallet, reset_mode=True)


@wallet_bp.route("/gift/<username>", methods=["GET", "POST"])
@login_required
def gift_user(username):
    if request.method == "POST":
        send_gift_to_username(username, request.form.get("gift_id"))
        return redirect(url_for("wallet.wallet_home"))

    current, receiver, wallet, gifts = get_gift_page(username)
    return render_template("wallet/gift.html", current=current, receiver=receiver, wallet=wallet, gifts=gifts)
