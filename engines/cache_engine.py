import threading
import time
from functools import wraps


_CACHE = {}
_LOCK = threading.RLock()


def init_cache(app):
    app.extensions["chain_cache"] = _CACHE
    return _CACHE


def cache_key(*parts):
    return ":".join(str(part) for part in parts if part not in (None, ""))


def _is_expired(expires_at):
    return expires_at is not None and expires_at <= time.time()


def get_cache(key, default=None):
    with _LOCK:
        record = _CACHE.get(key)
        if not record:
            return default
        if _is_expired(record["expires_at"]):
            _CACHE.pop(key, None)
            return default
        return record["value"]


def set_cache(key, value, ttl=60):
    expires_at = None if ttl is None else time.time() + max(int(ttl), 0)
    with _LOCK:
        _CACHE[key] = {"value": value, "expires_at": expires_at}
    return value


def delete_cache(key):
    with _LOCK:
        _CACHE.pop(key, None)


def cached(key, ttl=60):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            resolved_key = key(*args, **kwargs) if callable(key) else key
            if resolved_key:
                cached_value = get_cache(resolved_key)
                if cached_value is not None:
                    return cached_value
            value = func(*args, **kwargs)
            if resolved_key:
                set_cache(resolved_key, value, ttl=ttl)
            return value

        return wrapper

    return decorator
