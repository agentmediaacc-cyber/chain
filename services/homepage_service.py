from datetime import datetime, timedelta, timezone
import time

from flask import has_request_context

from engines.cache_engine import cache_key, get_cache, set_cache
from services.neon_service import fetch_all_with_connection, get_connection, get_tables_columns, release_connection
from services.profile_service import get_current_profile
from services.wallet_service import ensure_wallet


_CACHE_TTL_SECONDS = 45
_QUERY_TIMEOUT_SECONDS = 500
_TOTAL_BUDGET_MS = 400
_UNAVAILABLE_TTL_SECONDS = 60
_QUERY_BACKOFF = {}
_HOMEPAGE_TABLES = [
    "chain_profiles",
    "chain_posts",
    "chain_stories",
    "chain_status_posts",
    "chain_reels",
    "chain_live_rooms",
]
_SCHEMA_CACHE = {}


def _log(message):
    print(f"[homepage_service] {message}")


def _utcnow():
    return datetime.now(timezone.utc)


def _now_ts():
    return time.monotonic()


def _clean_text(value, fallback=""):
    if value is None:
        return fallback
    text = str(value).strip()
    return text or fallback


def _safe_int(value, default=0):
    try:
        if value in (None, "", False):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _safe_float(value, default=0.0):
    try:
        if value in (None, "", False):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _boolish(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return value != 0
    return str(value).strip().lower() in {"1", "true", "yes", "on", "live", "active", "online", "verified"}


def _first_present(record, keys, default=None):
    for key in keys:
        value = record.get(key)
        if value not in (None, ""):
            return value
    return default


def _format_relative(value):
    if not value:
        return "Just now"
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


def _error_code(error):
    code = getattr(error, "pgcode", None) or getattr(error, "code", None)
    if code:
        return str(code)
    text = str(error)
    if "42703" in text:
        return "42703"
    if "42P01" in text:
        return "42P01"
    return None


def _variant_unavailable(query_key):
    payload = _QUERY_BACKOFF.get(query_key)
    if not payload:
        return False
    if payload["expires_at"] <= _now_ts():
        _QUERY_BACKOFF.pop(query_key, None)
        return False
    return True


def _mark_unavailable(query_key, reason):
    _QUERY_BACKOFF[query_key] = {
        "expires_at": _now_ts() + _UNAVAILABLE_TTL_SECONDS,
        "reason": reason,
    }


def _table_columns(table_name):
    if not _SCHEMA_CACHE:
        for name, columns in get_tables_columns(_HOMEPAGE_TABLES, timeout_ms=_QUERY_TIMEOUT_SECONDS).items():
            _SCHEMA_CACHE[name] = set(columns)
    return _SCHEMA_CACHE.get(table_name, set())


def _select_columns(table_name, candidates, required=None):
    available = _table_columns(table_name)
    if required and any(column not in available for column in required):
        return []
    return [column for column in candidates if column in available]


def _run_sql(query_key, sql_text, params=None, timeout_ms=_QUERY_TIMEOUT_SECONDS, connection=None):
    if _variant_unavailable(query_key):
        return [], f"{query_key}: cached-unavailable"
    try:
        if connection is not None:
            return fetch_all_with_connection(connection, sql_text, params=params or [], timeout_ms=timeout_ms), None
        from services.neon_service import fetch_all
        return fetch_all(sql_text, params=params or [], timeout_ms=timeout_ms), None
    except Exception as error:
        code = _error_code(error)
        if code in {"42703", "42P01"}:
            _mark_unavailable(query_key, code)
        return [], f"{query_key}: unavailable"


def _profile_select():
    return _select_columns(
        "chain_profiles",
        [
            "id",
            "auth_user_id",
            "username",
            "display_name",
            "full_name",
            "avatar_url",
            "photo_url",
            "town",
            "city",
            "location",
            "region",
            "country",
            "country_origin",
            "current_location",
            "is_verified",
            "verified",
            "is_online",
            "is_creator",
            "creator_category",
            "dating_mode_enabled",
            "created_at",
            "deleted_at",
        ],
        required=["id"],
    )


def _post_select():
    return _select_columns(
        "chain_posts",
        [
            "id",
            "profile_id",
            "caption",
            "content",
            "body",
            "media_url",
            "video_url",
            "thumbnail_url",
            "likes_count",
            "comments_count",
            "created_at",
            "category",
            "deleted_at",
        ],
        required=["id"],
    )


def _story_select():
    return _select_columns(
        "chain_stories",
        [
            "id",
            "profile_id",
            "caption",
            "media_url",
            "video_url",
            "thumbnail_url",
            "created_at",
            "status",
            "active",
            "is_active",
            "deleted_at",
        ],
        required=["id"],
    )


def _status_select():
    return _select_columns(
        "chain_status_posts",
        [
            "id",
            "profile_id",
            "caption",
            "media_url",
            "video_url",
            "thumbnail_url",
            "created_at",
            "expires_at",
            "status",
            "deleted_at",
        ],
        required=["id"],
    )


def _reel_select():
    return _select_columns(
        "chain_reels",
        [
            "id",
            "profile_id",
            "caption",
            "media_url",
            "thumbnail_url",
            "created_at",
            "deleted_at",
        ],
        required=["id"],
    )


def _live_select():
    return _select_columns(
        "chain_live_rooms",
        [
            "id",
            "profile_id",
            "host_id",
            "creator_id",
            "title",
            "room_title",
            "category",
            "status",
            "is_live",
            "viewer_count",
            "viewers",
            "cover_url",
            "thumbnail_url",
            "media_url",
            "entry_fee",
            "coins_required",
            "created_at",
            "deleted_at",
        ],
        required=["id"],
    )


def _build_where(columns, extra=None):
    clauses = []
    if "deleted_at" in columns:
        clauses.append("deleted_at IS NULL")
    if extra:
        clauses.extend(extra)
    return clauses


def _fetch_profiles(limit=10, only_creators=False, dating_only=False, connection=None):
    columns = _profile_select()
    if not columns:
        return [], ["profiles: unavailable"]
    filters = []
    available = set(columns)
    if only_creators and "is_creator" in available:
        filters.append("is_creator = TRUE")
    if dating_only:
        if "dating_mode_enabled" not in available:
            return [], ["matches: unavailable"]
        filters.append("dating_mode_enabled = TRUE")
    where = _build_where(available, filters)
    query = f"SELECT {', '.join(columns)} FROM chain_profiles"
    if where:
        query += f" WHERE {' AND '.join(where)}"
    order_column = "created_at" if "created_at" in available else "id"
    query += f" ORDER BY {order_column} DESC LIMIT %s"
    rows, issue = _run_sql(f"profiles:{limit}:{only_creators}:{dating_only}", query, [limit], connection=connection)
    return rows, [issue] if issue else []


def _fetch_posts(connection=None):
    columns = _post_select()
    if not columns:
        return [], ["posts: unavailable"]
    available = set(columns)
    where = _build_where(available)
    query = f"SELECT {', '.join(columns)} FROM chain_posts"
    if where:
        query += f" WHERE {' AND '.join(where)}"
    if "likes_count" in available:
        query += " ORDER BY likes_count DESC NULLS LAST, created_at DESC NULLS LAST"
    else:
        query += " ORDER BY created_at DESC NULLS LAST"
    query += " LIMIT %s"
    rows, issue = _run_sql("posts", query, [8], connection=connection)
    return rows, [issue] if issue else []


def _fetch_stories(connection=None):
    issues = []
    story_rows = []
    story_columns = _story_select()
    if story_columns:
        available = set(story_columns)
        where = _build_where(available)
        if "is_active" in available:
            where.append("is_active = TRUE")
        elif "active" in available:
            where.append("active = TRUE")
        elif "status" in available:
            where.append("COALESCE(status, '') <> 'deleted'")
        query = f"SELECT {', '.join(story_columns)} FROM chain_stories"
        if where:
            query += f" WHERE {' AND '.join(where)}"
        query += " ORDER BY created_at DESC NULLS LAST LIMIT %s"
        story_rows, issue = _run_sql("stories", query, [12], connection=connection)
        if issue:
            issues.append(issue)
    else:
        issues.append("stories: unavailable")

    status_rows = []
    status_columns = _status_select()
    if status_columns:
        available = set(status_columns)
        cutoff = _utcnow() - timedelta(hours=24)
        where = _build_where(available, ["created_at >= %s"])
        params = [cutoff]
        if "expires_at" in available:
            where.append("(expires_at IS NULL OR expires_at > %s)")
            params.append(_utcnow())
        if "status" in available:
            where.append("COALESCE(status, '') <> 'deleted'")
        query = f"SELECT {', '.join(status_columns)} FROM chain_status_posts WHERE {' AND '.join(where)} ORDER BY created_at DESC NULLS LAST LIMIT %s"
        params.append(12)
        status_rows, issue = _run_sql("status_posts", query, params, connection=connection)
        if issue:
            issues.append(issue)

    combined = [row for row in story_rows if row.get("id")]
    for row in status_rows:
        if row.get("id"):
            combined.append(row)
    combined.sort(key=lambda row: str(row.get("created_at") or ""), reverse=True)
    return combined[:12], issues


def _fetch_reels(connection=None):
    columns = _reel_select()
    if not columns:
        return [], ["reels: unavailable"]
    available = set(columns)
    where = _build_where(available)
    query = f"SELECT {', '.join(columns)} FROM chain_reels"
    if where:
        query += f" WHERE {' AND '.join(where)}"
    query += " ORDER BY created_at DESC NULLS LAST LIMIT %s"
    rows, issue = _run_sql("reels", query, [8], connection=connection)
    return rows, [issue] if issue else []


def _fetch_live_rooms(connection=None):
    columns = _live_select()
    if not columns:
        return [], ["live_rooms: unavailable"]
    available = set(columns)
    where = _build_where(available)
    if "is_live" in available:
        where.append("is_live = TRUE")
    elif "status" in available:
        where.append("LOWER(COALESCE(status, '')) = 'live'")
    query = f"SELECT {', '.join(columns)} FROM chain_live_rooms"
    if where:
        query += f" WHERE {' AND '.join(where)}"
    query += " ORDER BY created_at DESC NULLS LAST LIMIT %s"
    rows, issue = _run_sql("live_rooms", query, [8], connection=connection)
    live_only = [row for row in rows if _boolish(row.get("is_live")) or _clean_text(row.get("status")).lower() == "live"]
    return live_only[:8], [issue] if issue else []


def _load_profile_map(profile_ids, connection=None):
    unique_ids = [profile_id for profile_id in dict.fromkeys(profile_ids) if profile_id]
    columns = _profile_select()
    if not unique_ids or not columns:
        return {}
    available = set(columns)
    placeholders = ", ".join(["%s"] * len(unique_ids))
    where = _build_where(available, [f"id IN ({placeholders})"])
    query = f"SELECT {', '.join(columns)} FROM chain_profiles WHERE {' AND '.join(where)}"
    rows, issue = _run_sql(f"profile_map:{len(unique_ids)}", query, unique_ids, connection=connection)
    if issue:
        pass
    return {row.get("id"): _normalize_profile(row) for row in rows if row.get("id")}


def _normalize_profile(row):
    if not row:
        return None
    username = _clean_text(row.get("username"))
    display_name = _clean_text(_first_present(row, ["display_name", "full_name", "username"]), "")
    avatar_url = _first_present(row, ["avatar_url", "photo_url", "media_url", "thumbnail_url"])
    town = _clean_text(_first_present(row, ["town", "city", "location", "current_location"]), "")
    region = _clean_text(_first_present(row, ["region", "country", "country_origin"]), "")
    location = ", ".join(part for part in [town, region] if part)
    profile_id = _first_present(row, ["id", "auth_user_id"])
    return {
        "id": profile_id,
        "username": username,
        "display_name": display_name,
        "avatar_url": avatar_url,
        "verified": _boolish(_first_present(row, ["verified", "is_verified"])),
        "is_online": _boolish(row.get("is_online")),
        "location": location,
        "town": town,
        "creator_category": _clean_text(row.get("creator_category"), ""),
        "dating_mode_enabled": _boolish(row.get("dating_mode_enabled")),
        "created_label": _format_relative(row.get("created_at")),
        "initial": (display_name or username or "?")[:1].upper(),
        "profile_url": f"/profile/@{username}" if username else "/discover/",
        "message_url": "/messages/" if username else "/discover/",
    }


def _normalize_story(row, profile_map):
    profile = profile_map.get(row.get("profile_id")) or {}
    display_name = profile.get("display_name") or profile.get("username") or ""
    return {
        "id": row.get("id"),
        "display_name": display_name,
        "avatar_url": profile.get("avatar_url"),
        "verified": profile.get("verified", False),
        "is_online": profile.get("is_online", False),
        "caption": _clean_text(row.get("caption")),
        "created_label": _format_relative(row.get("created_at")),
        "profile_url": profile.get("profile_url", "/discover/"),
    }


def _normalize_live_room(row, profile_map):
    profile_id = _first_present(row, ["profile_id", "host_id", "creator_id"])
    profile = profile_map.get(profile_id) or {}
    title = _clean_text(_first_present(row, ["title", "room_title"]), "")
    viewers = _first_present(row, ["viewer_count", "viewers"])
    fee_raw = _first_present(row, ["entry_fee", "coins_required"])
    entry_fee = _safe_float(fee_raw, 0) if fee_raw not in (None, "", False) else None
    creator_name = profile.get("display_name") or profile.get("username") or ""
    return {
        "id": row.get("id"),
        "title": title,
        "category": _clean_text(row.get("category"), ""),
        "viewer_count": _safe_int(viewers, 0) if viewers is not None else None,
        "entry_fee_label": f"{int(entry_fee)} coins" if entry_fee is not None else "",
        "cover_url": _first_present(row, ["cover_url", "thumbnail_url", "media_url"]),
        "creator_name": creator_name,
        "creator_avatar": profile.get("avatar_url"),
        "creator_verified": profile.get("verified", False),
        "creator_location": profile.get("town") or profile.get("location") or "",
        "created_label": _format_relative(row.get("created_at")),
        "watch_url": "/live/",
    }


def _normalize_post(row, profile_map):
    profile = profile_map.get(row.get("profile_id")) or {}
    caption = _clean_text(_first_present(row, ["caption", "content", "body"]), "")
    return {
        "id": row.get("id"),
        "display_name": profile.get("display_name") or profile.get("username") or "",
        "username": profile.get("username", ""),
        "avatar_url": profile.get("avatar_url"),
        "verified": profile.get("verified", False),
        "caption": caption,
        "excerpt": caption[:180] + ("..." if len(caption) > 180 else ""),
        "media_url": _first_present(row, ["media_url", "thumbnail_url", "video_url"]),
        "likes_count": _safe_int(row.get("likes_count"), 0),
        "comments_count": _safe_int(row.get("comments_count"), 0),
        "category": _clean_text(row.get("category"), ""),
        "created_label": _format_relative(row.get("created_at")),
        "profile_url": profile.get("profile_url", "/discover/"),
    }


def _wallet_snapshot(current):
    snapshot = {"coin_balance": 0, "gift_earnings": 0, "label_balance": "0"}
    if not current:
        return snapshot
    try:
        wallet = ensure_wallet(current["id"]) or {}
        snapshot["coin_balance"] = _safe_int(wallet.get("coin_balance"), 0)
        snapshot["gift_earnings"] = _safe_int(wallet.get("gift_earnings"), 0)
        snapshot["label_balance"] = f"{snapshot['coin_balance']:,}"
    except Exception as error:
        _log(f"wallet unavailable: {error}")
    return snapshot


def _safe_current_profile():
    if not has_request_context():
        return None
    try:
        return get_current_profile()
    except Exception as error:
        _log(f"current profile unavailable: {error}")
        return None


def _load_public_homepage():
    cached = get_cache(cache_key("chain_homepage_neon_v1", "public"))
    if cached is not None:
        return cached

    raw = {}
    issues = []
    connection = None
    started = time.perf_counter()
    try:
        connection = get_connection(statement_timeout_ms=_QUERY_TIMEOUT_SECONDS)
        jobs = [
            ("stories", lambda conn: _fetch_stories(connection=conn)),
            ("live_rooms", lambda conn: _fetch_live_rooms(connection=conn)),
            ("profiles", lambda conn: _fetch_profiles(10, True, False, connection=conn)),
            ("posts", lambda conn: _fetch_posts(connection=conn)),
            ("matches", lambda conn: _fetch_profiles(8, False, True, connection=conn)),
            ("reels", lambda conn: _fetch_reels(connection=conn)),
        ]
        for key, loader in jobs:
            elapsed_ms = (time.perf_counter() - started) * 1000
            if elapsed_ms >= _TOTAL_BUDGET_MS:
                raw[key] = []
                issues.append(f"{key}: budget")
                continue
            rows, row_issues = loader(connection)
            raw[key] = rows
            issues.extend(issue for issue in row_issues if issue)
    except Exception as error:
        _log(f"homepage neon connection unavailable: {error}")
        for key in ["stories", "live_rooms", "profiles", "posts", "matches", "reels"]:
            raw.setdefault(key, [])
        issues.append("neon: unavailable")
    finally:
        release_connection(connection)

    related_profile_ids = []
    for story in raw.get("stories", []):
        related_profile_ids.append(story.get("profile_id"))
    for room in raw.get("live_rooms", []):
        related_profile_ids.append(_first_present(room, ["profile_id", "host_id", "creator_id"]))
    for post in raw.get("posts", []):
        related_profile_ids.append(post.get("profile_id"))
    for row in raw.get("matches", []):
        related_profile_ids.append(row.get("id"))
    for row in raw.get("profiles", []):
        related_profile_ids.append(row.get("id"))

    profile_map = _load_profile_map(related_profile_ids)

    normalized_profiles = []
    for row in raw.get("profiles", []):
        profile = _normalize_profile(row)
        if profile:
            profile_map.setdefault(profile["id"], profile)
            normalized_profiles.append(profile)

    normalized_matches = []
    for row in raw.get("matches", []):
        profile = profile_map.get(row.get("id")) or _normalize_profile(row)
        if profile:
            normalized_matches.append(profile)

    payload = {
        "stories": [_normalize_story(row, profile_map) for row in raw.get("stories", []) if row.get("id")][:12],
        "live_rooms": [_normalize_live_room(row, profile_map) for row in raw.get("live_rooms", []) if row.get("id")][:8],
        "recommended_profiles": [profile for profile in normalized_profiles if profile][:10],
        "trending_posts": [_normalize_post(row, profile_map) for row in raw.get("posts", []) if row.get("id")][:8],
        "dating_matches": [profile for profile in normalized_matches if profile][:8],
        "stats": {
            "stories": len(raw.get("stories", [])),
            "live_rooms": len(raw.get("live_rooms", [])),
            "profiles": len(normalized_profiles),
            "posts": len(raw.get("posts", [])),
            "reels": len(raw.get("reels", [])),
        },
        "issues": issues,
    }
    set_cache(cache_key("chain_homepage_neon_v1", "public"), payload, ttl=_CACHE_TTL_SECONDS)
    return payload


def get_homepage_data():
    current = _safe_current_profile()
    public_data = _load_public_homepage()
    wallet = _wallet_snapshot(current)
    return {
        "current": current,
        "stories": public_data.get("stories", []),
        "live_rooms": public_data.get("live_rooms", []),
        "recommended_profiles": public_data.get("recommended_profiles", []),
        "trending_posts": public_data.get("trending_posts", []),
        "dating_matches": public_data.get("dating_matches", []),
        "stats": public_data.get("stats", {}),
        "wallet": wallet,
        "hero_story_count": len(public_data.get("stories", [])),
        "hero_live_count": len(public_data.get("live_rooms", [])),
        "hero_profile_count": len(public_data.get("recommended_profiles", [])),
        "hero_post_count": len(public_data.get("trending_posts", [])),
        "missing_sources": public_data.get("issues", []),
    }
