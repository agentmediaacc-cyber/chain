import random
import re
from datetime import datetime, timezone

from flask import session

from engines.cache_engine import cache_key, delete_cache, get_cache, set_cache
from engines.performance_engine import normalize_username, profile_completion_score, safe_int
from services.supabase_safe import column_safe_payload, safe_count, safe_insert, safe_select, safe_update, table_exists


PROFILE_COLUMNS = {
    "id",
    "auth_user_id",
    "username",
    "email",
    "normalized_email",
    "full_name",
    "bio",
    "gender",
    "age",
    "country_origin",
    "current_location",
    "phone",
    "normalized_phone",
    "residential_address",
    "town",
    "region",
    "country_of_birth",
    "date_of_birth",
    "current_residential_location",
    "avatar_url",
    "avatar_upload_id",
    "profile_photo",
    "cover_url",
    "cover_upload_id",
    "profile_photo",
    "profile_video_url",
    "video_intro_url",
    "relationship_status",
    "relationship_goal",
    "creator_category",
    "profile_type",
    "interests",
    "languages",
    "is_public",
    "is_verified",
    "is_premium",
    "premium_tier",
    "followers_count",
    "following_count",
    "profile_views",
    "total_likes",
    "wallet_balance",
    "profile_completion",
    "profile_completed",
    "onboarding_step",
    "password_set",
    "auth_provider",
    "provider_user_id",
    "zodiac_sign",
    "show_zodiac",
    "allow_zodiac_display",
    "allow_birthday_notifications",
    "profile_visibility",
    "terms_accepted",
    "human_confirmed",
    "anonymous_profile",
    "creator_mode_enabled",
    "seller_mode_enabled",
    "dating_mode_enabled",
    "premium_mode_enabled",
    "account_mode",
    "last_login_at",
    "login_count",
    "linked_providers",
    "username_slug",
    "oauth_metadata",
    "is_creator",
    "created_at",
    "updated_at",
}


def _utcnow_iso():
    return datetime.now(timezone.utc).isoformat()


def _normalize_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return []


def _clean_email(value):
    cleaned = str(value or "").strip().lower()
    return cleaned or None


def _normalize_phone(value):
    cleaned = "".join(ch for ch in str(value or "") if ch.isdigit() or ch == "+")
    if cleaned.startswith("00"):
        cleaned = f"+{cleaned[2:]}"
    if cleaned and not cleaned.startswith("+"):
        cleaned = f"+{cleaned}"
    return cleaned or None


def _username_valid(username):
    return bool(re.fullmatch(r"[a-z0-9_]{3,30}", username or ""))


def _username_suggestions(username, town=None):
    base = normalize_username(username or "chain")
    place = normalize_username(town or "world")
    year_suffix = str(datetime.now(timezone.utc).year)[-2:]
    candidates = [f"{base}{random.randint(10, 99)}", f"{base}{place}", f"{base}{year_suffix}"]
    suggestions = []
    seen = set()
    for candidate in candidates:
        trimmed = candidate[:30]
        if trimmed and trimmed not in seen:
            seen.add(trimmed)
            suggestions.append(trimmed)
    return suggestions[:3]


def _bool_value(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value).strip().lower() in {"true", "1", "on", "yes"}


def _age_from_dob(date_of_birth):
    if not date_of_birth:
        return None
    try:
        dob = datetime.fromisoformat(str(date_of_birth)).date()
        today = datetime.now(timezone.utc).date()
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    except ValueError:
        return None


def _upsert_single(table, key_field, key_value, payload, fallback_columns=None):
    existing = safe_select(table, columns="id", filters={key_field: key_value}, limit=1, order_by=None)
    if existing:
        safe_update(table, payload, eq={"id": existing[0]["id"]}, fallback_columns=fallback_columns)
        return existing[0]["id"]
    inserted = safe_insert(table, {key_field: key_value, **payload}, fallback_columns=fallback_columns)
    if inserted:
        return inserted[0].get("id")
    return None


def normalize_profile(profile):
    if not profile:
        return None

    normalized = dict(profile)
    normalized["avatar_url"] = normalized.get("avatar_url") or normalized.get("profile_photo")
    normalized["cover_url"] = normalized.get("cover_url") or normalized.get("cover_photo")
    normalized["profile_video_url"] = normalized.get("profile_video_url") or normalized.get("video_intro_url")
    normalized["profile_type"] = normalized.get("profile_type") or ("creator" if normalized.get("is_creator") else "member")
    normalized["creator_category"] = normalized.get("creator_category") or normalized.get("profile_type")
    normalized["premium_tier"] = normalized.get("premium_tier") or ("premium" if normalized.get("is_premium") else "free")
    normalized["is_premium"] = bool(normalized.get("is_premium") or normalized.get("premium_tier") not in {None, "", "free"})
    normalized["wallet_balance"] = normalized.get("wallet_balance") or 0
    normalized["interests"] = _normalize_list(normalized.get("interests"))
    normalized["languages"] = _normalize_list(normalized.get("languages"))
    normalized["linked_providers"] = _normalize_list(normalized.get("linked_providers"))
    normalized["profile_completion"] = normalized.get("profile_completion") or calculate_completion(normalized)
    normalized["profile_completed"] = normalized.get("profile_completed")
    if normalized["profile_completed"] is None:
        normalized["profile_completed"] = normalized["profile_completion"] >= 55
    normalized["creator_mode_enabled"] = _bool_value(normalized.get("creator_mode_enabled") or normalized.get("profile_type") in {"creator", "host"})
    normalized["seller_mode_enabled"] = _bool_value(normalized.get("seller_mode_enabled") or normalized.get("profile_type") == "seller")
    normalized["dating_mode_enabled"] = _bool_value(normalized.get("dating_mode_enabled"))
    normalized["premium_mode_enabled"] = _bool_value(normalized.get("premium_mode_enabled") or normalized.get("is_premium"))
    normalized["show_zodiac"] = _bool_value(normalized.get("show_zodiac"))
    return normalized


def get_current_profile():
    try:
        auth_user_id = session.get("auth_user_id")
        if not auth_user_id:
            return None

        cached_profile = get_cache(cache_key("current_profile", auth_user_id))
        if cached_profile is not None:
            return cached_profile

        profiles = safe_select("chain_profiles", columns="*", filters={"auth_user_id": auth_user_id}, limit=1)
        if not profiles and session.get("profile_id"):
            profiles = safe_select("chain_profiles", columns="*", filters={"id": session.get("profile_id")}, limit=1)

        if profiles:
            profile = normalize_profile(profiles[0])
            session["profile_id"] = profile["id"]
            session["username"] = profile["username"]
            set_cache(cache_key("current_profile", auth_user_id), profile, ttl=60)
            return profile

        return None
    except Exception as error:
        print(f"[profile_service] get_current_profile failed: {error}")
        return None


def get_public_profiles(limit=20):
    key = cache_key("public_profiles", limit)
    cached_profiles = get_cache(key)
    if cached_profiles is not None:
        return cached_profiles
    profiles = safe_select(
        "chain_profiles",
        columns="id,username,full_name,bio,current_location,avatar_url,premium_tier,is_premium,is_verified,age,country_origin,interests,cover_url",
        filters={"is_public": True},
        limit=limit,
    )
    result = [normalize_profile(profile) for profile in profiles]
    set_cache(key, result, ttl=60)
    return result


def get_profile_by_username(username):
    try:
        cleaned = username[1:] if username.startswith("@") else username
        key = cache_key("profile_username", cleaned)
        cached_profile = get_cache(key)
        if cached_profile is not None:
            return cached_profile
        profiles = safe_select("chain_profiles", columns="*", filters={"username": cleaned}, limit=1)
        profile = normalize_profile(profiles[0]) if profiles else None
        set_cache(key, profile, ttl=120)
        return profile
    except Exception as error:
        print(f"[profile_service] get_profile_by_username failed: {error}")
        return None


def get_profile_by_id(profile_id):
    key = cache_key("profile_id", profile_id)
    cached_profile = get_cache(key)
    if cached_profile is not None:
        return cached_profile
    profiles = safe_select("chain_profiles", columns="*", filters={"id": profile_id}, limit=1, order_by=None)
    profile = normalize_profile(profiles[0]) if profiles else None
    set_cache(key, profile, ttl=120)
    return profile


def calculate_completion(profile):
    return profile_completion_score(profile)


def required_profile_fields():
    return [
        "full_name",
        "username",
        "phone",
        "date_of_birth",
        "gender",
        "country_of_birth",
        "region",
        "town",
        "current_residential_location",
        "residential_address",
    ]


def get_profile_completion(profile):
    if not profile:
        return 0
    required = required_profile_fields()
    filled = 0
    for field in required:
        value = profile.get(field)
        if value not in (None, "", []):
            filled += 1
    return int((filled / len(required)) * 100)


def is_profile_complete(profile):
    if not profile:
        return False
    return all((profile.get(field) not in (None, "", [])) for field in required_profile_fields())


def _profile_payload_from_form(data, auth_user_id=None):
    username = normalize_username((data.get("username") or session.get("username") or "").lower().strip())
    email = _clean_email(data.get("email") or session.get("email"))
    phone = _normalize_phone(data.get("phone") or session.get("phone"))
    avatar_url = data.get("avatar_url") or data.get("profile_photo")
    avatar_upload_id = data.get("avatar_upload_id")
    cover_url = data.get("cover_url") or data.get("cover_photo")
    cover_upload_id = data.get("cover_upload_id")
    premium_tier = data.get("premium_tier") or ("premium" if data.get("is_premium") else "free")

    raw_payload = {
        "auth_user_id": auth_user_id or session.get("auth_user_id"),
        "username": username,
        "email": email,
        "normalized_email": email,
        "full_name": (data.get("full_name") or "").strip(),
        "bio": data.get("bio") or "",
        "gender": data.get("gender"),
        "age": safe_int(data.get("age"), None) if data.get("age") not in (None, "") else _age_from_dob(data.get("date_of_birth")),
        "country_origin": data.get("country_origin"),
        "current_location": data.get("current_location"),
        "phone": phone,
        "normalized_phone": phone,
        "residential_address": data.get("residential_address"),
        "town": data.get("town"),
        "region": data.get("region"),
        "country_of_birth": data.get("country_of_birth") or data.get("country_origin"),
        "date_of_birth": data.get("date_of_birth"),
        "current_residential_location": data.get("current_residential_location") or data.get("current_location"),
        "avatar_url": avatar_url,
        "avatar_upload_id": avatar_upload_id,
        "profile_photo": avatar_url,
        "cover_url": cover_url,
        "cover_upload_id": cover_upload_id,
        "cover_photo": cover_url,
        "profile_video_url": data.get("profile_video_url") or data.get("video_intro_url"),
        "video_intro_url": data.get("profile_video_url") or data.get("video_intro_url"),
        "relationship_status": data.get("relationship_status") or data.get("relationship_goal"),
        "relationship_goal": data.get("relationship_status") or data.get("relationship_goal"),
        "creator_category": data.get("creator_category") or data.get("profile_type"),
        "profile_type": data.get("profile_type", "member"),
        "zodiac_sign": data.get("zodiac_sign"),
        "show_zodiac": _bool_value(data.get("show_zodiac")),
        "allow_zodiac_display": _bool_value(data.get("show_zodiac")),
        "allow_birthday_notifications": _bool_value(data.get("allow_birthday_notifications"), True),
        "profile_visibility": data.get("profile_visibility", "public"),
        "creator_mode_enabled": _bool_value(data.get("creator_mode_enabled")) or data.get("profile_type") in {"creator", "host"},
        "seller_mode_enabled": _bool_value(data.get("seller_mode_enabled")) or data.get("profile_type") == "seller",
        "dating_mode_enabled": _bool_value(data.get("dating_mode_enabled")),
        "premium_mode_enabled": _bool_value(data.get("premium_mode_enabled")) or str(data.get("premium_tier", "")).lower() == "premium",
        "account_mode": data.get("account_mode") or data.get("profile_type", "member"),
        "interests": _normalize_list(data.get("interests")),
        "languages": _normalize_list(data.get("languages")),
        "is_public": str(data.get("is_public", "true")).lower() not in {"false", "0", "off"},
        "is_verified": str(data.get("is_verified", "false")).lower() in {"true", "1", "on"},
        "is_premium": str(data.get("is_premium", "false")).lower() in {"true", "1", "on"} or premium_tier not in {"", "free"},
        "premium_tier": premium_tier,
        "wallet_balance": data.get("wallet_balance"),
        "username_slug": username,
        "terms_accepted": _bool_value(data.get("terms_accepted") or data.get("consent_accepted")),
        "human_confirmed": _bool_value(data.get("human_confirmed") or data.get("real_person_confirmed")),
        "anonymous_profile": _bool_value(data.get("anonymous_profile") or data.get("is_anonymous_avatar")),
        "updated_at": _utcnow_iso(),
    }
    raw_payload["profile_completion"] = get_profile_completion(raw_payload)
    raw_payload["profile_completed"] = False
    raw_payload["onboarding_step"] = "profile_setup"
    raw_payload["is_creator"] = raw_payload["profile_type"] in {"creator", "host"}
    return column_safe_payload("chain_profiles", raw_payload, fallback_columns=PROFILE_COLUMNS)


def _find_existing_profile(uid=None, profile_id=None, username=None, email=None):
    rows = []
    if uid:
        rows = safe_select("chain_profiles", columns="id,auth_user_id,username,email,phone", filters={"auth_user_id": uid}, limit=1, order_by=None)
    if not rows and profile_id:
        rows = safe_select("chain_profiles", columns="id,auth_user_id,username,email,phone", filters={"id": profile_id}, limit=1, order_by=None)
    if not rows and email:
        rows = safe_select("chain_profiles", columns="id,auth_user_id,username,email,phone", filters={"normalized_email": email}, limit=1, order_by=None)
    if not rows and username:
        rows = safe_select("chain_profiles", columns="id,auth_user_id,username,email,phone", filters={"username": username}, limit=1, order_by=None)
    return rows[0] if rows else None


def _check_duplicate_identity(payload, existing_id=None):
    username = payload.get("username")
    email = payload.get("normalized_email") or payload.get("email")
    phone = payload.get("normalized_phone") or payload.get("phone")
    town = payload.get("town")

    if username:
        owner = safe_select("chain_profiles", columns="id", filters={"username": username}, limit=1, order_by=None)
        if owner and owner[0].get("id") != existing_id:
            suggestions = ", ".join(_username_suggestions(username, town=town))
            return False, f"That username is already in use. Try {suggestions}."

    if email:
        for field in ("normalized_email", "email"):
            owner = safe_select("chain_profiles", columns="id", filters={field: email}, limit=1, order_by=None)
            if owner and owner[0].get("id") != existing_id:
                return False, "That email is already connected to another CHAIN profile."

    if phone:
        for field in ("normalized_phone", "phone"):
            owner = safe_select("chain_profiles", columns="id", filters={field: phone}, limit=1, order_by=None)
            if owner and owner[0].get("id") != existing_id:
                return False, "That phone number is already connected to another CHAIN profile."

    return True, None


def bootstrap_profile_for_current_user():
    uid = session.get("auth_user_id")
    if not uid:
        return False, "Missing authenticated session."

    current = get_current_profile()
    if current:
        return True, current

    email = _clean_email(session.get("email"))
    base_username = normalize_username(session.get("username") or ((email or "chain").split("@")[0]))
    username = base_username if _username_valid(base_username) else "chainuser"

    while safe_select("chain_profiles", columns="id", filters={"username": username}, limit=1, order_by=None):
        username = _username_suggestions(base_username)[0]

    payload = {
        "full_name": session.get("full_name") or username.replace("_", " ").title(),
        "username": username,
        "email": email,
        "phone": session.get("phone"),
        "profile_type": "member",
    }
    return create_or_update_profile(payload, auth_user_id=uid)


def create_or_update_profile(data, auth_user_id=None):
    try:
        uid = auth_user_id or session.get("auth_user_id")
        payload = _profile_payload_from_form(data, auth_user_id=uid)
        if not payload.get("username") or not payload.get("full_name"):
            return False, "Username and full name are required."
        if not _username_valid(payload.get("username")):
            return False, "Use 3 to 30 lowercase letters, numbers or underscores only."

        existing = _find_existing_profile(
            uid=uid,
            profile_id=session.get("profile_id"),
            username=payload.get("username"),
            email=payload.get("normalized_email"),
        )
        is_valid, duplicate_error = _check_duplicate_identity(payload, existing_id=(existing or {}).get("id"))
        if not is_valid:
            return False, duplicate_error

        if existing:
            safe_update("chain_profiles", payload, eq={"id": existing["id"]}, fallback_columns=PROFILE_COLUMNS)
        else:
            safe_insert("chain_profiles", payload, fallback_columns=PROFILE_COLUMNS)

        saved = safe_select("chain_profiles", filters={"auth_user_id": uid}, limit=1)
        if not saved and payload.get("username"):
            saved = safe_select("chain_profiles", filters={"username": payload["username"]}, limit=1)

        if saved:
            profile = normalize_profile(saved[0])
            session["profile_id"] = profile["id"]
            session["username"] = profile["username"]
            delete_cache(cache_key("current_profile", uid))
            delete_cache(cache_key("profile_username", profile["username"]))
            delete_cache(cache_key("profile_id", profile["id"]))
            delete_cache(cache_key("public_profiles", 20))
            return True, profile["username"]

        return False, "Profile could not be saved yet."
    except Exception as error:
        print(f"[profile_service] create_or_update_profile failed: {error}")
        return False, str(error)


def update_profile_setup(profile_id, form):
    try:
        profile = get_profile_by_id(profile_id)
        if not profile:
            return False, "Profile not found."

        payload = _profile_payload_from_form(form, auth_user_id=profile.get("auth_user_id"))
        if not payload.get("username") or not payload.get("full_name"):
            return False, "Full name and username are required."
        if not _username_valid(payload.get("username")):
            return False, "Use 3 to 30 lowercase letters, numbers or underscores only."

        is_valid, duplicate_error = _check_duplicate_identity(payload, existing_id=profile_id)
        if not is_valid:
            return False, duplicate_error

        safe_update("chain_profiles", payload, eq={"id": profile_id}, fallback_columns=PROFILE_COLUMNS)
        _save_onboarding_foundations(profile_id, form, payload)
        delete_cache(cache_key("profile_id", profile_id))
        delete_cache(cache_key("profile_username", profile.get("username")))
        delete_cache(cache_key("current_profile", profile.get("auth_user_id")))
        return complete_profile_setup(profile_id)
    except Exception as error:
        print(f"[profile_service] update_profile_setup failed: {error}")
        return False, str(error)


def _save_onboarding_foundations(profile_id, form, profile_payload):
    preferences_payload = {
        "live_categories": _normalize_list(form.get("live_categories")),
        "post_categories": _normalize_list(form.get("post_categories")),
        "language_preferences": _normalize_list(form.get("language_preferences") or form.get("languages")),
        "dating_interest": _normalize_list(form.get("dating_interest")),
        "creator_interest": _bool_value(form.get("creator_mode_enabled")),
        "seller_interest": _bool_value(form.get("seller_mode_enabled")),
        "preferred_regions": _normalize_list(form.get("preferred_regions") or form.get("region")),
        "updated_at": _utcnow_iso(),
    }
    if table_exists("chain_user_preferences"):
        _upsert_single(
            "chain_user_preferences",
            "profile_id",
            profile_id,
            preferences_payload,
            fallback_columns={"profile_id", "live_categories", "post_categories", "language_preferences", "dating_interest", "creator_interest", "seller_interest", "preferred_regions", "updated_at", "created_at"},
        )

    privacy_payload = {
        "profile_visibility": form.get("profile_visibility", "public"),
        "who_can_view_profile": form.get("who_can_view_profile", "everyone"),
        "allow_profile_discovery": _bool_value(form.get("allow_profile_discovery"), True),
        "allow_contact_from": form.get("allow_contact_from", "everyone"),
        "updated_at": _utcnow_iso(),
    }
    if table_exists("chain_user_privacy_settings"):
        _upsert_single(
            "chain_user_privacy_settings",
            "profile_id",
            profile_id,
            privacy_payload,
            fallback_columns={"profile_id", "profile_visibility", "who_can_view_profile", "allow_profile_discovery", "allow_contact_from", "updated_at", "created_at"},
        )

    call_payload = {
        "allow_messages": _bool_value(form.get("allow_messages"), True),
        "allow_audio_calls": _bool_value(form.get("allow_audio_calls"), True),
        "allow_video_calls": _bool_value(form.get("allow_video_calls"), True),
        "allow_high_quality_media": _bool_value(form.get("allow_high_quality_media"), True),
        "allow_status_video": _bool_value(form.get("allow_status_video"), True),
        "allow_music_uploads": _bool_value(form.get("allow_music_uploads"), True),
        "updated_at": _utcnow_iso(),
    }
    if table_exists("chain_user_call_settings"):
        _upsert_single(
            "chain_user_call_settings",
            "profile_id",
            profile_id,
            call_payload,
            fallback_columns={"profile_id", "allow_messages", "allow_audio_calls", "allow_video_calls", "allow_high_quality_media", "allow_status_video", "allow_music_uploads", "updated_at", "created_at"},
        )

    verification_payload = {
        "consent_accepted": _bool_value(form.get("consent_accepted")),
        "real_person_confirmed": _bool_value(form.get("real_person_confirmed")),
        "verification_status": "pending" if form.get("verification_selfie_url") else "self-attested",
        "selfie_url": form.get("verification_selfie_url"),
        "updated_at": _utcnow_iso(),
    }
    if table_exists("chain_user_verifications"):
        _upsert_single(
            "chain_user_verifications",
            "profile_id",
            profile_id,
            verification_payload,
            fallback_columns={"profile_id", "consent_accepted", "real_person_confirmed", "verification_status", "selfie_url", "updated_at", "created_at"},
        )

    avatar_payload = {
        "avatar_mode": form.get("avatar_mode", "upload"),
        "avatar_url": profile_payload.get("avatar_url"),
        "system_avatar_key": form.get("system_avatar_key"),
        "is_anonymous": _bool_value(form.get("is_anonymous_avatar")),
        "updated_at": _utcnow_iso(),
    }
    if table_exists("chain_profile_avatars"):
        _upsert_single(
            "chain_profile_avatars",
            "profile_id",
            profile_id,
            avatar_payload,
            fallback_columns={"profile_id", "avatar_mode", "avatar_url", "system_avatar_key", "is_anonymous", "updated_at", "created_at"},
        )

    if _bool_value(form.get("dating_mode_enabled")):
        dating_payload = {
            "is_enabled": True,
            "dating_intent": form.get("dating_intent", "open_to_meeting"),
            "dating_interest": _normalize_list(form.get("dating_interest")),
            "updated_at": _utcnow_iso(),
        }
        if table_exists("chain_dating_profiles"):
            _upsert_single(
                "chain_dating_profiles",
                "profile_id",
                profile_id,
                dating_payload,
                fallback_columns={"profile_id", "is_enabled", "dating_intent", "dating_interest", "updated_at", "created_at"},
            )


def complete_profile_setup(profile_id):
    profile = get_profile_by_id(profile_id)
    if not profile:
        return False, "Profile not found."

    completed = is_profile_complete(profile)
    safe_update(
        "chain_profiles",
        {
            "profile_completed": completed,
            "profile_completion": get_profile_completion(profile),
            "onboarding_step": "complete" if completed else "profile_setup",
            "updated_at": _utcnow_iso(),
        },
        eq={"id": profile_id},
        fallback_columns=PROFILE_COLUMNS,
    )
    refreshed = get_profile_by_id(profile_id)
    return True, refreshed


def get_profile_settings(profile_id):
    settings = (safe_select("chain_user_settings", filters={"profile_id": profile_id}, limit=1, order_by=None) or [None])[0]
    security = (safe_select("chain_account_security", filters={"profile_id": profile_id}, limit=1, order_by=None) or [None])[0]

    if not settings and table_exists("chain_user_settings"):
        safe_insert(
            "chain_user_settings",
            {
                "profile_id": profile_id,
                "allow_messages": True,
                "allow_video_calls": True,
                "show_online_status": True,
                "profile_visibility": "public",
            },
            fallback_columns={"profile_id", "allow_messages", "allow_video_calls", "show_online_status", "profile_visibility", "created_at", "updated_at"},
        )
        settings = (safe_select("chain_user_settings", filters={"profile_id": profile_id}, limit=1, order_by=None) or [None])[0]

    profile = get_profile_by_id(profile_id) or {}
    if not security and table_exists("chain_account_security"):
        safe_insert(
            "chain_account_security",
            {
                "profile_id": profile_id,
                "email": profile.get("email"),
                "password_set": bool(profile.get("password_set")),
                "recovery_enabled": True,
            },
            fallback_columns={"profile_id", "email", "password_set", "recovery_enabled", "created_at", "updated_at"},
        )
        security = (safe_select("chain_account_security", filters={"profile_id": profile_id}, limit=1, order_by=None) or [None])[0]

    return {
        "settings": settings or {
            "profile_id": profile_id,
            "allow_messages": True,
            "allow_video_calls": True,
            "show_online_status": True,
            "profile_visibility": "public",
        },
        "security": security or {
            "profile_id": profile_id,
            "email": profile.get("email"),
            "password_set": bool(profile.get("password_set")),
            "recovery_enabled": True,
        },
    }


def record_profile_view(profile_id, viewer_profile_id=None):
    try:
        viewer = viewer_profile_id or session.get("profile_id")
        if table_exists("chain_recent_views"):
            safe_insert(
                "chain_recent_views",
                {
                    "profile_id": viewer,
                    "viewer_profile_id": viewer,
                    "viewed_profile_id": profile_id,
                    "view_type": "profile",
                    "created_at": _utcnow_iso(),
                },
                fallback_columns={"profile_id", "viewer_profile_id", "viewed_profile_id", "view_type", "created_at"},
            )

        profile = get_profile_by_id(profile_id)
        if profile:
            safe_update(
                "chain_profiles",
                {"profile_views": int(profile.get("profile_views") or 0) + 1, "updated_at": _utcnow_iso()},
                eq={"id": profile_id},
                fallback_columns=PROFILE_COLUMNS,
            )
        return True
    except Exception as error:
        print(f"[profile_service] record_profile_view failed: {error}")
        return False


def get_profile_counts(profile_id):
    followers = safe_count("chain_followers", filters={"following_profile_id": profile_id})
    if followers == 0:
        followers = safe_count("chain_follows", filters={"following_profile_id": profile_id})

    following = safe_count("chain_followers", filters={"follower_profile_id": profile_id})
    if following == 0:
        following = safe_count("chain_followers", filters={"profile_id": profile_id})
    if following == 0:
        following = safe_count("chain_follows", filters={"follower_profile_id": profile_id})

    likes = safe_count("chain_profile_likes", filters={"profile_id": profile_id})
    favorites = safe_count("chain_favorites", filters={"target_profile_id": profile_id})
    views = safe_count("chain_recent_views", filters={"viewed_profile_id": profile_id})

    return {
        "followers": followers,
        "following": following,
        "likes": likes,
        "favorites": favorites,
        "views": views,
    }


def get_profile_stats(profile_id):
    try:
        rooms = safe_count("chain_live_rooms", filters={"host_profile_id": profile_id})
        if rooms == 0:
            rooms = safe_count("chain_live_rooms", filters={"profile_id": profile_id})

        posts = safe_count("chain_posts", filters={"profile_id": profile_id})
        stories = safe_count("chain_stories", filters={"profile_id": profile_id})
        counts = get_profile_counts(profile_id)
        return {
            "rooms": rooms,
            "posts": posts,
            "stories": stories,
            "followers": counts["followers"],
            "following": counts["following"],
            "likes": counts["likes"],
            "favorites": counts["favorites"],
            "views": counts["views"],
        }
    except Exception as error:
        print(f"[profile_service] get_profile_stats failed: {error}")
        return {"rooms": 0, "posts": 0, "stories": 0, "followers": 0, "following": 0, "likes": 0, "favorites": 0, "views": 0}


def get_profile_content(profile_id, limit=8):
    rooms = safe_select("chain_live_rooms", columns="id,title,host_name,host_profile_id,profile_id,status,category,access_type,viewer_count,gift_total,welcome_message,cover_url,created_at", filters={"host_profile_id": profile_id}, limit=limit)
    if not rooms:
        rooms = safe_select("chain_live_rooms", columns="id,title,host_name,host_profile_id,profile_id,status,category,access_type,viewer_count,gift_total,welcome_message,cover_url,created_at", filters={"profile_id": profile_id}, limit=limit)
    posts = safe_select("chain_posts", columns="id,profile_id,body,caption,category,media_url,visibility,status,created_at", filters={"profile_id": profile_id}, limit=limit)
    stories = safe_select("chain_status_posts", filters={"profile_id": profile_id}, limit=limit) or safe_select("chain_stories", filters={"profile_id": profile_id}, limit=limit)
    
    # Phase 8: Marketplace & Music
    marketplace = safe_select("chain_marketplace_items", filters={"profile_id": profile_id}, limit=limit)
    albums = safe_select("chain_music_albums", filters={"profile_id": profile_id}, limit=limit)
    
    return {
        "rooms": rooms, 
        "posts": posts, 
        "stories": stories,
        "marketplace": marketplace,
        "albums": albums
    }


def get_wallet_snapshot(profile_id):
    wallet = (safe_select("chain_wallets", filters={"profile_id": profile_id}, limit=1) or [None])[0]
    if wallet:
        return wallet

    profile = get_profile_by_id(profile_id) or {}
    return {
        "coin_balance": profile.get("wallet_balance", 0) or 0,
        "gift_earnings": 0,
        "pending_withdrawal": 0,
    }


def get_creator_tools(profile_id):
    tools = (safe_select("chain_creator_tools", filters={"profile_id": profile_id}, limit=1) or [None])[0]
    if tools:
        return tools
    return {
        "profile_id": profile_id,
        "studio_enabled": False,
        "creator_notes": "",
        "featured_links": [],
    }


def get_profile_activity(profile_id):
    try:
        content = get_profile_content(profile_id, limit=5)
        gifts = safe_select("chain_live_gifts", filters={"host_profile_id": profile_id}, limit=5)
        if not gifts:
            gifts = safe_select("chain_gift_events", filters={"receiver_profile_id": profile_id}, limit=5)
        favorites = safe_select("chain_favorites", filters={"profile_id": profile_id}, limit=5)
        recent_views = safe_select("chain_recent_views", filters={"profile_id": profile_id}, limit=5)
        return {
            "rooms": content["rooms"],
            "posts": content["posts"],
            "stories": content["stories"],
            "gifts": gifts,
            "favorites": favorites,
            "recent_views": recent_views,
        }
    except Exception as error:
        print(f"[profile_service] get_profile_activity failed: {error}")
        return {"rooms": [], "posts": [], "stories": [], "gifts": [], "favorites": [], "recent_views": []}


def get_profile_actions(profile, viewer=None):
    own_profile = viewer and profile and viewer.get("id") == profile.get("id")
    stored_actions = safe_select("chain_profile_actions", filters={"profile_id": profile.get("id")}, limit=10)
    if stored_actions:
        return stored_actions

    username = profile.get("username")
    if own_profile:
        return [
            {"label": "Edit Profile", "href": "/profile/edit", "icon": "fa-user-pen", "kind": "link"},
            {"label": "Wallet", "href": "/wallet/", "icon": "fa-wallet", "kind": "link"},
            {"label": "Creator Tools", "href": f"/profile/@{username}/creator-tools", "icon": "fa-sliders", "kind": "link"},
            {"label": "Premium", "href": f"/profile/@{username}/premium", "icon": "fa-gem", "kind": "link"},
        ]

    return [
        {"label": "Follow", "href": f"/profile/@{username}/follow", "icon": "fa-user-plus", "kind": "post"},
        {"label": "Message", "href": f"/chat/start/{username}", "icon": "fa-comment-dots", "kind": "link"},
        {"label": "Video Call", "href": f"/calls/video/{username}", "icon": "fa-video", "kind": "link"},
        {"label": "Favorite", "href": f"/profile/@{username}/favorite", "icon": "fa-heart", "kind": "post"},
        {"label": "Like", "href": f"/profile/@{username}/like", "icon": "fa-thumbs-up", "kind": "post"},
    ]


def get_profile_bundle(username=None, profile_id=None, viewer=None):
    profile = get_profile_by_username(username) if username else get_profile_by_id(profile_id)
    if not profile:
        return None

    stats = get_profile_stats(profile["id"])
    content = get_profile_content(profile["id"])
    activity = get_profile_activity(profile["id"])
    wallet = get_wallet_snapshot(profile["id"])
    creator_tools = get_creator_tools(profile["id"])
    actions = get_profile_actions(profile, viewer=viewer)
    
    # Phase 8: Real-time Presence
    presence_row = safe_select("chain_presence", filters={"profile_id": profile["id"]}, limit=1)
    presence = presence_row[0] if presence_row else {"status": "offline", "last_seen": None}
    
    # Phase 8: Follow Status
    is_following = False
    if viewer:
        res = safe_select("chain_follows", filters={"follower_profile_id": viewer["id"], "following_profile_id": profile["id"]}, limit=1)
        is_following = bool(res)

    return {
        "profile": profile,
        "stats": stats,
        "content": content,
        "activity": activity,
        "wallet": wallet,
        "creator_tools": creator_tools,
        "actions": actions,
        "presence": presence,
        "is_following": is_following
    }


def _recount_and_store_profile_counts(profile_id):
    counts = get_profile_counts(profile_id)
    safe_update(
        "chain_profiles",
        {
            "followers_count": counts["followers"],
            "following_count": counts["following"],
            "total_likes": counts["likes"],
            "profile_views": counts["views"],
            "updated_at": _utcnow_iso(),
        },
        eq={"id": profile_id},
        fallback_columns=PROFILE_COLUMNS,
    )
    profile = get_profile_by_id(profile_id)
    if profile:
        delete_cache(cache_key("profile_username", profile.get("username")))
        delete_cache(cache_key("profile_id", profile_id))


def follow_profile(username):
    current = get_current_profile()
    target = get_profile_by_username(username)
    if not current or not target or current["id"] == target["id"]:
        return False

    existing = safe_select(
        "chain_followers",
        filters={"follower_profile_id": current["id"], "following_profile_id": target["id"]},
        limit=1,
        order_by=None,
    )
    if not existing:
        safe_insert(
            "chain_followers",
            {
                "profile_id": current["id"],
                "follower_profile_id": current["id"],
                "following_profile_id": target["id"],
                "created_at": _utcnow_iso(),
            },
            fallback_columns={"profile_id", "follower_profile_id", "following_profile_id", "created_at"},
        )
    _recount_and_store_profile_counts(target["id"])
    _recount_and_store_profile_counts(current["id"])
    return True


def like_profile(username):
    current = get_current_profile()
    target = get_profile_by_username(username)
    if not current or not target or current["id"] == target["id"]:
        return False

    existing = safe_select(
        "chain_profile_likes",
        filters={"profile_id": target["id"], "liker_key": current["id"]},
        limit=1,
        order_by=None,
    )
    if not existing:
        safe_insert(
            "chain_profile_likes",
            {"profile_id": target["id"], "liker_key": current["id"], "created_at": _utcnow_iso()},
            fallback_columns={"profile_id", "liker_key", "created_at"},
        )
    _recount_and_store_profile_counts(target["id"])
    return True


def favorite_profile(username):
    current = get_current_profile()
    target = get_profile_by_username(username)
    if not current or not target or current["id"] == target["id"]:
        return False

    existing = safe_select(
        "chain_favorites",
        filters={"profile_id": current["id"], "target_profile_id": target["id"]},
        limit=1,
        order_by=None,
    )
    if not existing:
        safe_insert(
            "chain_favorites",
            {"profile_id": current["id"], "target_profile_id": target["id"], "created_at": _utcnow_iso()},
            fallback_columns={"profile_id", "target_profile_id", "created_at"},
        )
    return True


def report_profile(username, reason=None):
    current = get_current_profile()
    target = get_profile_by_username(username)
    if not current or not target:
        return False

    safe_insert(
        "chain_reports",
        {
            "reporter_profile_id": current["id"],
            "reported_profile_id": target["id"],
            "reason": reason or "Profile report",
            "status": "open",
            "created_at": _utcnow_iso(),
        },
        fallback_columns={"reporter_profile_id", "reported_profile_id", "reason", "status", "created_at"},
    )
    return True


def block_profile(username):
    current = get_current_profile()
    target = get_profile_by_username(username)
    if not current or not target or current["id"] == target["id"]:
        return False

    existing = safe_select(
        "chain_blocks",
        filters={"blocker_profile_id": current["id"], "blocked_profile_id": target["id"]},
        limit=1,
        order_by=None,
    )
    if not existing:
        safe_insert(
            "chain_blocks",
            {"blocker_profile_id": current["id"], "blocked_profile_id": target["id"], "created_at": _utcnow_iso()},
            fallback_columns={"blocker_profile_id", "blocked_profile_id", "created_at"},
        )
    return True
