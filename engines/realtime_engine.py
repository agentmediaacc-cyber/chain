"""
Realtime engine note:
Use Supabase Realtime on the frontend for:
- live comments
- live gifts
- viewer count
- messages
- notifications

This backend file keeps channel names consistent.
"""

def channel_for_live_room(room_id):
    return f"chain-live-room-{room_id}"


def channel_for_profile(profile_id):
    return f"chain-profile-{profile_id}"


def channel_for_chat(conversation_id):
    return f"chain-chat-{conversation_id}"
