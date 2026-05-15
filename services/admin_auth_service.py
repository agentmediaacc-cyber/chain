from datetime import datetime, timezone
from functools import wraps

from flask import redirect, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from services.supabase_safe import safe_insert, safe_select, safe_update, table_exists


ADMIN_COLUMNS = {
    "id",
    "username",
    "email",
    "full_name",
    "role",
    "is_master",
    "is_active",
    "password_hash",
    "created_at",
    "updated_at",
}


SITE_SETTING_COLUMNS = {
    "id",
    "setting_key",
    "setting_value",
    "updated_by",
    "updated_at",
}


def _utcnow_iso():
    return datetime.now(timezone.utc).isoformat()


def hash_password(password):
    return generate_password_hash(password, method='pbkdf2:sha256')


def verify_password(password, password_hash):
    if not password or not password_hash:
        return False
    try:
        return check_password_hash(password_hash, password)
    except Exception:
        return False


def get_admin_by_username(username):
    cleaned = (username or "").strip().lower()
    if not cleaned or not table_exists("chain_admin_users"):
        return None
    rows = safe_select("chain_admin_users", filters={"username": cleaned}, limit=1, order_by=None)
    return rows[0] if rows else None


def set_master_admin_password(username, password):
    admin = get_admin_by_username(username)
    if not admin:
        return False, "Admin user not found."
    if len(password or "") < 8:
        return False, "Password must be at least 8 characters."

    payload = {
        "password_hash": hash_password(password),
        "is_master": admin.get("username") == "chainkasera",
        "role": "developer" if admin.get("username") == "chainkasera" else (admin.get("role") or "admin"),
        "is_active": True,
        "updated_at": _utcnow_iso(),
    }
    safe_update("chain_admin_users", payload, eq={"id": admin["id"]}, fallback_columns=ADMIN_COLUMNS)
    return True, "Master admin password updated."


def authenticate_admin(username, password):
    admin = get_admin_by_username(username)
    if not admin:
        return False, "Admin account not found."
    if not admin.get("is_active", True):
        return False, "Admin account is inactive."
    if not verify_password(password, admin.get("password_hash")):
        return False, "Invalid username or password."
    return True, admin


def login_admin_session(admin):
    session["admin_id"] = admin.get("id")
    session["admin_username"] = admin.get("username")
    session["admin_role"] = admin.get("role") or "admin"
    session["is_master_admin"] = bool(admin.get("is_master"))


def logout_admin_session():
    session.pop("admin_id", None)
    session.pop("admin_username", None)
    session.pop("admin_role", None)
    session.pop("is_master_admin", None)


def current_admin():
    admin_id = session.get("admin_id")
    if not admin_id or not table_exists("chain_admin_users"):
        return None
    rows = safe_select("chain_admin_users", filters={"id": admin_id}, limit=1, order_by=None)
    return rows[0] if rows else None


def admin_redirect_target(admin):
    if admin.get("is_master") or admin.get("username") == "chainkasera":
        return "/developer/dashboard"
    return "/admin/dashboard"


def log_admin_action(admin_id, action, target_type=None, target_id=None, metadata=None):
    if not table_exists("chain_admin_audit_log"):
        return
    safe_insert(
        "chain_admin_audit_log",
        {
            "admin_id": admin_id,
            "action": action,
            "target_type": target_type,
            "target_id": target_id,
            "metadata": metadata or {},
            "created_at": _utcnow_iso(),
        },
    )


def get_site_setting(setting_key, default=None):
    if not table_exists("chain_site_settings"):
        return default
    rows = safe_select("chain_site_settings", filters={"setting_key": setting_key}, limit=1, order_by=None)
    if not rows:
        return default
    return rows[0].get("setting_value", default)


def set_site_setting(setting_key, setting_value, admin_id=None):
    existing = safe_select("chain_site_settings", filters={"setting_key": setting_key}, limit=1, order_by=None)
    payload = {
        "setting_key": setting_key,
        "setting_value": setting_value,
        "updated_by": admin_id,
        "updated_at": _utcnow_iso(),
    }
    if existing:
        safe_update("chain_site_settings", payload, eq={"id": existing[0]["id"]}, fallback_columns=SITE_SETTING_COLUMNS)
        return existing[0]["id"]
    inserted = safe_insert("chain_site_settings", payload, fallback_columns=SITE_SETTING_COLUMNS)
    if inserted:
        return inserted[0].get("id")
    return None


def require_admin(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not session.get("admin_id"):
            return redirect(f"/admin/login?next={request.path}")
        admin = current_admin()
        if not admin or not admin.get("is_active", True):
            logout_admin_session()
            return redirect(f"/admin/login?next={request.path}")
        return view_func(*args, **kwargs)

    return wrapped


def require_master_admin(view_func):
    @wraps(view_func)
    @require_admin
    def wrapped(*args, **kwargs):
        admin = current_admin()
        if not admin or not (admin.get("is_master") or admin.get("username") == "chainkasera"):
            return redirect("/admin/dashboard")
        return view_func(*args, **kwargs)

    return wrapped
