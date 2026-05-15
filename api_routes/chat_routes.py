from flask import Blueprint, flash, redirect, render_template, request, url_for, session
from api_routes.profile_routes import login_required
from services.profile_service import get_current_profile, get_profile_by_id
from services.chat_service import (
    get_or_create_direct_conversation,
    list_conversations,
    list_messages,
    send_text_message,
    send_media_message,
    mark_messages_read
)

chat_bp = Blueprint("chat_v2", __name__, url_prefix="/messages")

@chat_bp.route("/")
@login_required
def inbox():
    profile = get_current_profile()
    conversations = list_conversations(profile["id"])
    return render_template("messages/index.html", conversations=conversations, profile=profile)

@chat_bp.route("/<conversation_id>")
@login_required
def thread(conversation_id):
    profile = get_current_profile()
    messages, err = list_messages(conversation_id, profile["id"])
    if err:
        flash(err, "error")
        return redirect(url_for("chat_v2.inbox"))
    
    from services.supabase_safe import safe_select
    convo = safe_select("chain_conversations", filters={"id": conversation_id}, limit=1)
    if not convo:
        return redirect(url_for("chat_v2.inbox"))
    
    convo = convo[0]
    mark_messages_read(conversation_id, profile["id"])
    
    return render_template("messages/thread.html", convo=convo, messages=messages, profile=profile)

@chat_bp.route("/start/<profile_id>")
@login_required
def start_chat(profile_id):
    current = get_current_profile()
    convo, err = get_or_create_direct_conversation(current["id"], profile_id)
    if err:
        flash(err, "error")
        return redirect(request.referrer or url_for("chat_v2.inbox"))
    
    return redirect(url_for("chat_v2.thread", conversation_id=convo["id"]))

@chat_bp.route("/<conversation_id>/send", methods=["POST"])
@login_required
def send_message(conversation_id):
    profile = get_current_profile()
    body = request.form.get("body")
    res, err = send_text_message(conversation_id, profile["id"], body)
    if err:
        flash(err, "error")
    
    return redirect(url_for("chat_v2.thread", conversation_id=conversation_id))

@chat_bp.route("/<conversation_id>/send-media", methods=["POST"])
@login_required
def send_media(conversation_id):
    profile = get_current_profile()
    media_file = request.files.get("media")
    res, err = send_media_message(conversation_id, profile["id"], media_file)
    if err:
        flash(err, "error")
    
    return redirect(url_for("chat_v2.thread", conversation_id=conversation_id))
