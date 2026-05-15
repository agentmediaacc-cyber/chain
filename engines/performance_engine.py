import re
import time
import unicodedata
from contextlib import contextmanager


@contextmanager
def timed(label):
    start = time.perf_counter()
    try:
        yield
    finally:
        duration_ms = (time.perf_counter() - start) * 1000
        if duration_ms >= 1500:
            print(f"[perf] {label}: {duration_ms:.1f}ms")


def safe_int(value, default=0):
    try:
        if value in (None, ""):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def clean_email(value):
    return (value or "").strip().lower()


def normalize_username(value):
    raw = unicodedata.normalize("NFKD", str(value or ""))
    ascii_only = raw.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9_]+", "_", ascii_only.strip().lower()).strip("_")
    return slug[:24] or "chain_user"


def make_unique_username(base_username, exists_func):
    base = normalize_username(base_username)
    if not exists_func(base):
        return base
    for index in range(2, 5000):
        candidate = f"{base}_{index}"
        if not exists_func(candidate):
            return candidate
    return f"{base}_{int(time.time())}"


def profile_completion_score(profile):
    fields = [
        "full_name",
        "username",
        "bio",
        "gender",
        "age",
        "country_origin",
        "current_location",
        "phone",
        "avatar_url",
        "cover_url",
        "creator_category",
        "interests",
        "languages",
    ]
    filled = 0
    for field in fields:
        value = (profile or {}).get(field)
        if isinstance(value, list):
            filled += 1 if value else 0
        elif value not in (None, "", []):
            filled += 1
    return int((filled / len(fields)) * 100)


def compact_profile(profile):
    if not profile:
        return None
    return {
        "id": profile.get("id"),
        "auth_user_id": profile.get("auth_user_id"),
        "username": profile.get("username"),
        "full_name": profile.get("full_name"),
        "email": profile.get("email"),
        "avatar_url": profile.get("avatar_url") or profile.get("profile_photo"),
        "current_location": profile.get("current_location"),
        "is_premium": bool(profile.get("is_premium")),
        "premium_tier": profile.get("premium_tier"),
        "bio": profile.get("bio"),
    }


def compact_room(room):
    if not room:
        return None
    return {
        "id": room.get("id"),
        "title": room.get("title"),
        "host_name": room.get("host_name"),
        "host_profile_id": room.get("host_profile_id") or room.get("profile_id"),
        "status": room.get("status"),
        "category": room.get("category"),
        "access_type": room.get("access_type"),
        "viewer_count": room.get("viewer_count") or 0,
        "gift_total": room.get("gift_total") or room.get("total_gift_coins") or 0,
        "welcome_message": room.get("welcome_message"),
        "cover_url": room.get("cover_url"),
    }


def paginate(items, page=1, per_page=20):
    page = max(safe_int(page, 1), 1)
    per_page = max(safe_int(per_page, 20), 1)
    start = (page - 1) * per_page
    end = start + per_page
    subset = list(items)[start:end]
    total = len(items)
    return {
        "items": subset,
        "page": page,
        "per_page": per_page,
        "total": total,
        "pages": max((total + per_page - 1) // per_page, 1),
    }
