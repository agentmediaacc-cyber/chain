from datetime import datetime, timezone
from services.supabase_safe import safe_select
from services.trending_service import get_trending_items

def get_personalized_feed(profile_id, limit=30):
    """
    Constructs a personalized feed for the user.
    Prioritizes:
    1. Followed creators (live rooms, then posts)
    2. Verified creators
    3. Trending content
    4. New content
    """
    feed = []
    seen_ids = set()

    # 1. Get following IDs
    following = safe_select("chain_follows", filters={"follower_profile_id": profile_id})
    following_ids = [f['following_profile_id'] for f in following]

    if following_ids:
        # Live rooms from following
        live_rooms = safe_select("chain_live_rooms", filters={"is_live": True, "host_profile_id": ("in", following_ids)}, limit=5)
        for room in live_rooms:
            if room['id'] not in seen_ids:
                feed.append({"type": "live_room", "data": room, "priority": 100})
                seen_ids.add(room['id'])

        # Posts from following
        posts = safe_select("chain_posts", filters={"profile_id": ("in", following_ids)}, limit=10, order_by="created_at", desc=True)
        for post in posts:
            if post['id'] not in seen_ids:
                feed.append({"type": "post", "data": post, "priority": 90})
                seen_ids.add(post['id'])

    # 2. Trending Live Rooms
    trending_rooms = get_trending_items('live_room', limit=5)
    if trending_rooms:
        room_ids = [t['entity_id'] for t in trending_rooms]
        rooms = safe_select("chain_live_rooms", filters={"id": ("in", room_ids)})
        for room in rooms:
            if room['id'] not in seen_ids:
                feed.append({"type": "live_room", "data": room, "priority": 80})
                seen_ids.add(room['id'])

    # 3. Marketplace Content (Featured/New)
    marketplace = safe_select("chain_marketplace_items", filters={"approval_status": "approved"}, limit=5, order_by="created_at", desc=True)
    for item in marketplace:
        if item['id'] not in seen_ids:
            feed.append({"type": "marketplace_item", "data": item, "priority": 70})
            seen_ids.add(item['id'])

    # 4. Fallback to general new posts
    remaining = limit - len(feed)
    if remaining > 0:
        general_posts = safe_select("chain_posts", limit=remaining, order_by="created_at", desc=True)
        for post in general_posts:
            if post['id'] not in seen_ids:
                feed.append({"type": "post", "data": post, "priority": 50})
                seen_ids.add(post['id'])

    # Sort by priority
    feed.sort(key=lambda x: x['priority'], reverse=True)
    return feed[:limit]
