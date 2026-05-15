from datetime import datetime, timezone

from flask import has_request_context

from engines.cache_engine import cache_key, get_cache, set_cache
from services.notification_service import get_my_notifications, normalize_notification
from services.profile_service import get_current_profile
from services.supabase_safe import safe_count, safe_select, table_exists
from services.wallet_service import ensure_wallet
from services.recommendation_service import (
    get_trending_profiles,
    get_trending_live_rooms,
    get_trending_posts,
    get_recommended_profiles,
    get_recommended_posts
)
from utils.supabase_client import get_supabase_admin


FALLBACK_CATEGORIES = [
    "Live Music",
    "Dating",
    "Chill Room",
    "Creators",
    "Namibia Nightlife",
    "Talent",
    "Stories",
]


def _log(message):
    print(f"[homepage_service] {message}")


def _utcnow():
    return datetime.now(timezone.utc)


def _safe_number(value, default=0):
    try:
        if value in (None, "", False):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value, default=0):
    try:
        if value in (None, "", False):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _boolish(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return value != 0
    return str(value).strip().lower() in {"1", "true", "yes", "on", "live", "online", "verified", "active"}


def _clean_text(value, fallback=""):
    if value is None:
        return fallback
    text = str(value).strip()
    return text or fallback


def _first_present(record, keys, default=None):
    for key in keys:
        value = record.get(key)
        if value not in (None, ""):
            return value
    return default


def _format_relative(value):
    if not value:
        return "Just now"

    parsed = None
    if isinstance(value, datetime):
        parsed = value
    else:
        raw = str(value).strip()
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return raw[:16].replace("T", " ")

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    delta = _utcnow() - parsed.astimezone(timezone.utc)
    seconds = max(int(delta.total_seconds()), 0)
    if seconds < 60:
        return "Just now"
    if seconds < 3600:
        return f"{seconds // 60}m ago"
    if seconds < 86400:
        return f"{seconds // 3600}h ago"
    if seconds < 604800:
        return f"{seconds // 86400}d ago"
    return parsed.strftime("%d %b")


def _apply_filters(query, filters):
    if not filters:
        return query

    for column, raw_value in filters.items():
        operator = "eq"
        value = raw_value
        if isinstance(raw_value, tuple) and len(raw_value) == 2:
            operator, value = raw_value

        if operator == "eq":
            query = query.eq(column, value)
        elif operator == "in":
            query = query.in_(column, value)
        elif operator == "gte":
            query = query.gte(column, value)
        elif operator == "is":
            query = query.is_(column, value)
        else:
            query = query.eq(column, value)
    return query


def _query_attempts(table, column_attempts, limit=20, filters=None, order_by="created_at", desc=True):
    if not table_exists(table):
        return [], f"missing table `{table}`"

    admin = get_supabase_admin()
    last_error = None

    for columns in column_attempts:
        try:
            query = admin.table(table).select(columns)
            query = _apply_filters(query, filters)
            if order_by:
                query = query.order(order_by, desc=desc)
            if limit is not None:
                query = query.limit(limit)
            result = query.execute().data or []
            return result, None
        except Exception as error:
            last_error = error

    _log(f"{table} query failed after {len(column_attempts)} attempts: {last_error}")
    return [], f"{table} columns unavailable"


def _profile_attempts():
    return [
        "id,user_id,auth_user_id,username,full_name,display_name,avatar_url,profile_photo,photo_url,current_location,location,town,region,country,country_origin,is_verified,verified,is_online,created_at,is_creator,creator_category",
        "id,user_id,auth_user_id,username,full_name,avatar_url,profile_photo,current_location,town,region,country_origin,is_verified,is_creator,created_at",
        "*",
    ]


def _live_attempts():
    return [
        "id,host_id,creator_id,profile_id,host_profile_id,title,room_title,category,access_type,is_live,status,viewer_count,viewers,cover_url,thumbnail_url,mp3_url,youtube_url,entry_fee,coins_required,created_at,host_name,welcome_message",
        "id,profile_id,title,category,access_type,is_live,status,viewer_count,cover_url,entry_fee,created_at,host_name,welcome_message",
        "*",
    ]


def _post_attempts():
    return [
        "id,profile_id,caption,content,body,media_url,image_url,video_url,created_at,likes_count,comments_count,category",
        "id,profile_id,caption,body,media_url,created_at,category",
        "*",
    ]


def _story_attempts():
    return [
        "id,profile_id,caption,media_url,image_url,video_url,created_at,expires_at,status",
        "id,profile_id,media_url,created_at",
        "*",
    ]


def _notification_attempts():
    return [
        "id,profile_id,title,body,message,type,notification_type,target_url,link_url,is_read,created_at",
        "*",
    ]


def _gift_attempts():
    return [
        "id,sender_profile_id,receiver_profile_id,host_profile_id,gift_name,emoji,gift_icon,coins,amount,created_at",
        "*",
    ]


def _viewer_attempts():
    return [
        "id,room_id,profile_id,display_name,joined_at,left_at,created_at",
        "*",
    ]


def _load_profiles(limit=18):
    rows, issue = _query_attempts(
        "chain_profiles",
        _profile_attempts(),
        limit=limit,
        filters={"is_public": True},
    )
    if not rows:
        fallback_rows, fallback_issue = _query_attempts("chain_profiles", _profile_attempts(), limit=limit)
        rows = fallback_rows
        issue = issue or fallback_issue
    return rows, issue


def _load_profiles_by_ids(profile_ids):
    unique_ids = [profile_id for profile_id in dict.fromkeys(profile_ids) if profile_id]
    if not unique_ids:
        return {}

    rows, _ = _query_attempts(
        "chain_profiles",
        _profile_attempts(),
        limit=len(unique_ids),
        filters={"id": ("in", unique_ids)},
        order_by=None,
    )
    return {row.get("id"): _normalize_profile(row) for row in rows if row.get("id")}


def _normalize_profile(profile):
    if not profile:
        return None

    username = _clean_text(_first_present(profile, ["username"]), "")
    display_name = _clean_text(_first_present(profile, ["display_name", "full_name", "username"]), "Creator")
    avatar_url = _first_present(profile, ["avatar_url", "profile_photo", "photo_url"])
    location_parts = [
        _clean_text(_first_present(profile, ["town", "location"]), ""),
        _clean_text(_first_present(profile, ["region", "country", "country_origin", "current_location"]), ""),
    ]
    compact_location = ", ".join([part for part in location_parts if part])
    return {
        "id": _first_present(profile, ["id", "user_id", "auth_user_id"]),
        "username": username,
        "display_name": display_name,
        "full_name": _clean_text(_first_present(profile, ["full_name", "display_name", "username"]), display_name),
        "avatar_url": avatar_url,
        "location": compact_location or _clean_text(_first_present(profile, ["current_location", "country", "country_origin"]), "Namibia"),
        "town": _clean_text(_first_present(profile, ["town", "location"]), "Windhoek"),
        "country": _clean_text(_first_present(profile, ["country", "country_origin"]), "Namibia"),
        "verified": _boolish(_first_present(profile, ["verified", "is_verified"])),
        "is_online": _boolish(profile.get("is_online")),
        "creator_category": _clean_text(_first_present(profile, ["creator_category", "profile_type"]), "Creator"),
        "created_at": profile.get("created_at"),
        "joined_label": _format_relative(profile.get("created_at")),
        "initial": display_name[:1].upper(),
        "profile_url": f"/profile/@{username}" if username else "/profile/",
        "message_url": f"/chat/start/{username}" if username else "/chat/",
    }


def _normalize_live_room(room, profile_map=None, viewer_map=None):
    if not room:
        return None

    profile_id = _first_present(room, ["host_id", "creator_id", "profile_id", "host_profile_id"])
    related_profile = (profile_map or {}).get(profile_id) if profile_id else None
    title = _clean_text(_first_present(room, ["title", "room_title"]), "Untitled live room")
    access_type = _clean_text(_first_present(room, ["access_type"]), "public").lower()
    if access_type not in {"public", "private", "vip", "premium"}:
        access_type = "public"

    is_live = _boolish(room.get("is_live")) or _clean_text(room.get("status"), "").lower() == "live"
    room_id = room.get("id")
    live_viewers = _safe_int(_first_present(room, ["viewer_count", "viewers"]), 0)
    if room_id and viewer_map and room_id in viewer_map:
        live_viewers = max(live_viewers, viewer_map[room_id])

    entry_fee = _safe_number(_first_present(room, ["entry_fee", "coins_required"]), 0)
    creator_name = _clean_text(_first_present(room, ["host_name"]), "") or (
        (related_profile or {}).get("display_name") or "Chain Creator"
    )

    return {
        "id": room_id,
        "profile_id": profile_id,
        "title": title,
        "category": _clean_text(room.get("category"), "Live"),
        "access_type": access_type,
        "access_label": "VIP" if access_type in {"vip", "premium"} else access_type.title(),
        "is_live": is_live,
        "status": "live" if is_live else _clean_text(room.get("status"), "offline"),
        "viewer_count": live_viewers,
        "cover_url": _first_present(room, ["cover_url", "thumbnail_url"]),
        "mp3_url": room.get("mp3_url"),
        "youtube_url": room.get("youtube_url"),
        "entry_fee": entry_fee,
        "entry_fee_label": f"{int(entry_fee)} coins" if entry_fee > 0 else "Free entry",
        "creator_name": creator_name,
        "creator_avatar": (related_profile or {}).get("avatar_url"),
        "creator_username": (related_profile or {}).get("username"),
        "creator_verified": (related_profile or {}).get("verified", False),
        "creator_location": (related_profile or {}).get("town", "Windhoek"),
        "welcome_message": _clean_text(room.get("welcome_message"), "Join the next room lighting up the night."),
        "created_at": room.get("created_at"),
        "created_label": _format_relative(room.get("created_at")),
        "watch_url": f"/live/room/{room_id}" if room_id else "/live/",
    }


def _normalize_post(post, profile_map=None):
    if not post:
        return None

    related_profile = (profile_map or {}).get(post.get("profile_id")) or {}
    caption = _clean_text(_first_present(post, ["caption", "content", "body"]), "")
    media_url = _first_present(post, ["media_url", "image_url", "video_url"])
    return {
        "id": post.get("id"),
        "profile_id": post.get("profile_id"),
        "display_name": related_profile.get("display_name", "Chain Creator"),
        "username": related_profile.get("username", ""),
        "avatar_url": related_profile.get("avatar_url"),
        "verified": related_profile.get("verified", False),
        "caption": caption,
        "excerpt": caption[:160] + ("..." if len(caption) > 160 else ""),
        "media_url": media_url,
        "has_video": bool(post.get("video_url") and post.get("video_url") == media_url),
        "likes_count": _safe_int(post.get("likes_count"), 0),
        "comments_count": _safe_int(post.get("comments_count"), 0),
        "category": _clean_text(post.get("category"), "Creators"),
        "created_at": post.get("created_at"),
        "created_label": _format_relative(post.get("created_at")),
        "profile_url": related_profile.get("profile_url", "/discover/"),
    }


def _normalize_story(story, profile_map=None):
    if not story:
        return None

    related_profile = (profile_map or {}).get(story.get("profile_id")) or {}
    media_url = _first_present(story, ["media_url", "image_url", "video_url"])
    return {
        "id": story.get("id"),
        "profile_id": story.get("profile_id"),
        "display_name": related_profile.get("display_name", "Creator"),
        "username": related_profile.get("username", ""),
        "avatar_url": related_profile.get("avatar_url"),
        "verified": related_profile.get("verified", False),
        "is_online": related_profile.get("is_online", False),
        "media_url": media_url,
        "created_at": story.get("created_at"),
        "created_label": _format_relative(story.get("created_at")),
        "expires_at": story.get("expires_at"),
        "caption": _clean_text(story.get("caption"), "Fresh moment"),
        "profile_url": related_profile.get("profile_url", "/discover/"),
    }


def _normalize_notifications(rows):
    normalized = []
    for row in rows:
        item = normalize_notification(row)
        normalized.append(
            {
                "id": item.get("id"),
                "title": _clean_text(item.get("title"), "Fresh activity"),
                "body": _clean_text(item.get("body"), "Creator activity will arrive here as your world expands."),
                "type": _clean_text(item.get("type"), "info"),
                "target_url": item.get("target_url") or "/notifications/",
                "is_read": _boolish(item.get("is_read")),
                "created_at": item.get("created_at"),
                "created_label": _format_relative(item.get("created_at")),
            }
        )
    return normalized


def _derive_categories(live_rooms, posts):
    seen = set()
    categories = []

    for item in list(live_rooms) + list(posts):
        label = _clean_text(item.get("category"), "")
        key = label.lower()
        if not label or key in seen:
            continue
        seen.add(key)
        categories.append(
            {
                "name": label,
                "href": f"/search?q={label.replace(' ', '+')}",
                "source": "live" if item in live_rooms else "feed",
            }
        )

    if categories:
        return categories[:8]

    return [{"name": label, "href": f"/search?q={label.replace(' ', '+')}", "source": "prompt"} for label in FALLBACK_CATEGORIES]


def _load_viewer_counts(live_rooms):
    room_ids = [room.get("id") for room in live_rooms if room.get("id")]
    if not room_ids or not table_exists("chain_live_viewers"):
        return {}

    viewer_rows, _ = _query_attempts(
        "chain_live_viewers",
        _viewer_attempts(),
        limit=250,
        filters={"room_id": ("in", room_ids)},
        order_by=None,
    )
    counts = {}
    for row in viewer_rows:
        room_id = row.get("room_id")
        if not room_id:
            continue
        if row.get("left_at") not in (None, "", False):
            counts.setdefault(room_id, 0)
            continue
        counts[room_id] = counts.get(room_id, 0) + 1
    return counts


def _wallet_snapshot(current):
    base = {
        "coin_balance": 0,
        "gift_earnings": 0,
        "total_received": 0,
        "total_spent": 0,
        "label_balance": "0",
    }
    if not current:
        return base

    wallet = ensure_wallet(current["id"]) or {}
    base.update(
        {
            "coin_balance": _safe_int(wallet.get("coin_balance"), 0),
            "gift_earnings": _safe_int(wallet.get("gift_earnings"), 0),
            "total_received": _safe_int(wallet.get("total_received"), 0),
            "total_spent": _safe_int(wallet.get("total_spent"), 0),
        }
    )
    base["label_balance"] = f"{base['coin_balance']:,}"
    return base


def _gift_snapshot():
    candidates = ["chain_gifts", "chain_gift_events", "chain_live_gifts"]
    rows = []
    source = None
    for table in candidates:
        if not table_exists(table):
            continue
        rows, _ = _query_attempts(table, _gift_attempts(), limit=20)
        source = table
        if rows:
            break

    total_coins = 0
    for row in rows:
        total_coins += _safe_int(_first_present(row, ["coins", "amount"]), 0)

    return {
        "source": source,
        "count": len(rows),
        "total_coins": total_coins,
        "highlight": rows[0] if rows else None,
    }


def _safe_current_profile():
    if not has_request_context():
        return None
    try:
        return get_current_profile()
    except Exception as error:
        _log(f"current profile unavailable: {error}")
        return None


def _safe_notifications(current):
    if not has_request_context() or not current:
        return [], 0
    try:
        notifications, _, unread_count = get_my_notifications(limit=6)
        return notifications, unread_count
    except Exception as error:
        _log(f"notifications unavailable: {error}")
        return [], 0


def get_homepage_data():
    current = _safe_current_profile()
    notifications, unread_count = _safe_notifications(current)

    homepage_key = cache_key("homepage_data_v2", "public")
    cached = get_cache(homepage_key)
    if cached is None:
        issues = []
        queried_tables = []

        profile_rows, profile_issue = _load_profiles(limit=18)
        queried_tables.append("chain_profiles")
        if profile_issue:
            issues.append(profile_issue)

        live_rows, live_issue = _query_attempts("chain_live_rooms", _live_attempts(), limit=12)
        queried_tables.append("chain_live_rooms")
        if live_issue:
            issues.append(live_issue)

        post_rows, post_issue = _query_attempts("chain_posts", _post_attempts(), limit=8)
        queried_tables.append("chain_posts")
        if post_issue:
            issues.append(post_issue)

        story_rows, story_issue = _query_attempts("chain_stories", _story_attempts(), limit=10)
        queried_tables.append("chain_stories")
        if story_issue:
            issues.append(story_issue)

        public_notification_rows, notification_issue = _query_attempts("chain_notifications", _notification_attempts(), limit=6)
        queried_tables.append("chain_notifications")
        if notification_issue:
            issues.append(notification_issue)

        viewer_counts = _load_viewer_counts(live_rows)
        if table_exists("chain_live_viewers"):
            queried_tables.append("chain_live_viewers")

        profile_ids = []
        profile_ids.extend([row.get("profile_id") for row in live_rows])
        profile_ids.extend([_first_present(row, ["host_id", "creator_id", "host_profile_id"]) for row in live_rows])
        profile_ids.extend([row.get("profile_id") for row in post_rows])
        profile_ids.extend([row.get("profile_id") for row in story_rows])
        referenced_profiles = _load_profiles_by_ids(profile_ids)

        normalized_profiles = [_normalize_profile(row) for row in profile_rows]
        normalized_profiles = [profile for profile in normalized_profiles if profile]
        for profile in normalized_profiles:
            referenced_profiles.setdefault(profile["id"], profile)

        normalized_live_rooms = [
            _normalize_live_room(row, profile_map=referenced_profiles, viewer_map=viewer_counts)
            for row in live_rows
        ]
        normalized_live_rooms = [room for room in normalized_live_rooms if room and room.get("is_live")]

        normalized_posts = [_normalize_post(row, profile_map=referenced_profiles) for row in post_rows]
        normalized_posts = [post for post in normalized_posts if post]

        normalized_stories = [_normalize_story(row, profile_map=referenced_profiles) for row in story_rows]
        normalized_stories = [story for story in normalized_stories if story]

        notification_preview = _normalize_notifications(public_notification_rows)
        categories = _derive_categories(normalized_live_rooms, normalized_posts)
        gifts = _gift_snapshot()
        if gifts.get("source"):
            queried_tables.append(gifts["source"])

        stats = {
            "profiles": safe_count("chain_profiles"),
            "live_rooms": safe_count("chain_live_rooms", filters={"status": "live"}) or len(normalized_live_rooms),
            "posts": safe_count("chain_posts"),
            "stories": safe_count("chain_stories"),
            "gifts": gifts["count"],
            "gift_coins": gifts["total_coins"],
            "viewers": sum(room["viewer_count"] for room in normalized_live_rooms),
        }

        cached = {
            "stats": stats,
            "live_rooms": normalized_live_rooms[:6],
            "profiles": normalized_profiles[:8],
            "posts": normalized_posts[:6],
            "stories": normalized_stories[:10],
            "notifications": notification_preview[:6],
            "trending_profiles": get_trending_profiles(limit=6),
            "trending_rooms": get_trending_live_rooms(limit=6),
            "trending_posts": get_trending_posts(limit=6),
            "categories": categories,
            "hero_room": normalized_live_rooms[0] if normalized_live_rooms else None,
            "hero_profile": normalized_profiles[0] if normalized_profiles else None,
            "gift_summary": gifts,
            "queried_tables": list(dict.fromkeys(queried_tables)),
            "missing_sources": issues,
        }
        set_cache(homepage_key, cached, ttl=45)

    homepage_notifications = _normalize_notifications(notifications) if notifications else cached.get("notifications", [])
    wallet = _wallet_snapshot(current)
    hero_room = cached.get("hero_room")
    hero_profile = cached.get("hero_profile")

    recommended_profiles = get_recommended_profiles(current["id"]) if current else []
    recommended_posts = get_recommended_posts(current["id"]) if current else []

    return {
        "current": current,
        "unread_count": unread_count,
        "stats": cached.get("stats", {}),
        "live_rooms": cached.get("live_rooms", []),
        "profiles": cached.get("profiles", []),
        "posts": cached.get("posts", []),
        "stories": cached.get("stories", []),
        "trending_profiles": cached.get("trending_profiles", []),
        "trending_rooms": cached.get("trending_rooms", []),
        "trending_posts": cached.get("trending_posts", []),
        "recommended_profiles": recommended_profiles,
        "recommended_posts": recommended_posts,
        "notifications": homepage_notifications,
        "categories": cached.get("categories", []),
        "trending_categories": cached.get("categories", []),
        "wallet": wallet,
        "hero_room": hero_room,
        "hero_profile": hero_profile,
        "gift_summary": cached.get("gift_summary", {}),
        "queried_tables": cached.get("queried_tables", []),
        "missing_sources": cached.get("missing_sources", []),
        "search_index": {
            "profiles": cached.get("profiles", []),
            "live_rooms": cached.get("live_rooms", []),
            "posts": cached.get("posts", []),
            "stories": cached.get("stories", []),
            "categories": cached.get("categories", []),
        },
    }
