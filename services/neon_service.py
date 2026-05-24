import os
import time
from typing import Any
import uuid

from dotenv import load_dotenv
import psycopg2
from psycopg2 import pool, sql
from psycopg2.extras import Json, RealDictCursor


load_dotenv(dotenv_path=".env")

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
_POOL = None
_COLUMN_CACHE = {}
_COLUMN_CACHE_TTL_SECONDS = 300
_HEALTH_CACHE = {"expires_at": 0.0, "payload": None}
_HEALTH_CACHE_TTL_SECONDS = 30
_CONNECTION_BACKOFF = {"expires_at": 0.0, "error": None}
_CONNECTION_BACKOFF_SECONDS = 30


def _log(message: str) -> None:
    print(f"[neon_service] {message}")


def is_configured() -> bool:
    return bool(DATABASE_URL)


def _connection_blocked():
    return _CONNECTION_BACKOFF.get("expires_at", 0) > time.monotonic()


def _mark_connection_failure(error):
    _CONNECTION_BACKOFF["expires_at"] = time.monotonic() + _CONNECTION_BACKOFF_SECONDS
    _CONNECTION_BACKOFF["error"] = str(error)


def _clear_connection_failure():
    _CONNECTION_BACKOFF["expires_at"] = 0.0
    _CONNECTION_BACKOFF["error"] = None


def _pool_instance():
    global _POOL
    if _connection_blocked():
        raise RuntimeError(_CONNECTION_BACKOFF.get("error") or "Neon temporarily unavailable")
    if _POOL is None and DATABASE_URL:
        try:
            _POOL = pool.SimpleConnectionPool(
                minconn=1,
                maxconn=4,
                dsn=DATABASE_URL,
                connect_timeout=1,
                application_name="chain_app",
                keepalives=1,
                keepalives_idle=30,
                keepalives_interval=10,
                keepalives_count=3,
            )
            _clear_connection_failure()
        except Exception as error:
            _mark_connection_failure(error)
            raise
    return _POOL


def get_connection(statement_timeout_ms=None):
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not configured")
    pool_instance = _pool_instance()
    if pool_instance is None:
        raise RuntimeError("Neon pool is unavailable")
    try:
        connection = pool_instance.getconn()
        _clear_connection_failure()
    except Exception as error:
        _mark_connection_failure(error)
        raise
    if statement_timeout_ms:
        with connection.cursor() as cursor:
            cursor.execute(f"SET statement_timeout = {max(int(statement_timeout_ms), 100)}")
    return connection


def release_connection(connection):
    if connection is None:
        return
    pool_instance = _pool_instance()
    if pool_instance is not None:
        pool_instance.putconn(connection)


def _adapt_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return Json(value)
    return value


def _run(query: Any, params=None, fetch="all", timeout_ms=900):
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not configured")

    pool_instance = _pool_instance()
    if pool_instance is None:
        raise RuntimeError("Neon pool is unavailable")

    connection = pool_instance.getconn()
    try:
        with connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(f"SET LOCAL statement_timeout = {max(int(timeout_ms), 100)}")
                cursor.execute(query, params)
                if fetch == "all":
                    return [dict(row) for row in cursor.fetchall()]
                if fetch == "one":
                    row = cursor.fetchone()
                    return dict(row) if row else None
                return {"rowcount": cursor.rowcount}
    except Exception as error:
        _log(f"query failed: {error}")
        raise
    finally:
        pool_instance.putconn(connection)


def fetch_all_with_connection(connection, query: Any, params=None, timeout_ms=900):
    with connection.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute(f"SET LOCAL statement_timeout = {max(int(timeout_ms), 100)}")
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]


def fetch_one_with_connection(connection, query: Any, params=None, timeout_ms=900):
    with connection.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute(f"SET LOCAL statement_timeout = {max(int(timeout_ms), 100)}")
        cursor.execute(query, params)
        row = cursor.fetchone()
        return dict(row) if row else None


def fetch_all(query: Any, params=None, timeout_ms=900):
    return _run(query, params=params, fetch="all", timeout_ms=timeout_ms)


def fetch_one(query: Any, params=None, timeout_ms=900):
    return _run(query, params=params, fetch="one", timeout_ms=timeout_ms)


def execute(query: Any, params=None, timeout_ms=900):
    return _run(query, params=params, fetch="none", timeout_ms=timeout_ms)


def insert_row(table_name: str, payload: dict, returning="id", timeout_ms=900):
    if not payload:
        raise ValueError("payload is required")
    columns = list(payload.keys())
    values = [_adapt_value(payload[column]) for column in columns]
    query = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
        sql.Identifier(table_name),
        sql.SQL(", ").join(sql.Identifier(column) for column in columns),
        sql.SQL(", ").join(sql.Placeholder() for _ in columns),
    )
    if returning:
        query += sql.SQL(" RETURNING {}").format(sql.SQL(returning))
        return fetch_one(query, values, timeout_ms=timeout_ms)
    execute(query, values, timeout_ms=timeout_ms)
    return None


def get_table_columns(table_name: str, timeout_ms=500):
    return get_tables_columns([table_name], timeout_ms=timeout_ms).get(table_name, [])


def get_tables_columns(table_names, timeout_ms=500):
    table_names = [name for name in table_names if name]
    if not table_names:
        return {}

    now = time.monotonic()
    results = {}
    missing = []
    for table_name in table_names:
        cached = _COLUMN_CACHE.get(table_name)
        if cached and cached["expires_at"] > now:
            results[table_name] = cached["columns"]
        else:
            missing.append(table_name)

    if not DATABASE_URL:
        return {table_name: [] for table_name in table_names}
    if _connection_blocked():
        return {table_name: [] for table_name in table_names}

    if missing:
        for table_name in missing:
            results.setdefault(table_name, [])
        try:
            rows = fetch_all(
                """
                SELECT table_name, column_name
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = ANY(%s)
                ORDER BY table_name, ordinal_position
                """,
                [missing],
                timeout_ms=timeout_ms,
            )
            for row in rows:
                results.setdefault(row["table_name"], []).append(row["column_name"])
        except Exception as error:
            _mark_connection_failure(error)

        for table_name in missing:
            _COLUMN_CACHE[table_name] = {
                "columns": results.get(table_name, []),
                "expires_at": now + (_CONNECTION_BACKOFF_SECONDS if _connection_blocked() else _COLUMN_CACHE_TTL_SECONDS),
            }

    return {table_name: results.get(table_name, []) for table_name in table_names}


def table_exists(table_name: str, timeout_ms=500) -> bool:
    return bool(get_table_columns(table_name, timeout_ms=timeout_ms))


def get_neon_health():
    now = time.monotonic()
    cached = _HEALTH_CACHE.get("payload")
    if cached is not None and _HEALTH_CACHE.get("expires_at", 0) > now:
        return dict(cached)

    health = {
        "configured": is_configured(),
        "connected": False,
        "latency_ms": None,
        "error": None,
    }
    if not health["configured"]:
        health["error"] = "DATABASE_URL missing"
        return health
    if _connection_blocked():
        health["error"] = _CONNECTION_BACKOFF.get("error") or "Neon temporarily unavailable"
        _HEALTH_CACHE["payload"] = dict(health)
        _HEALTH_CACHE["expires_at"] = now + _HEALTH_CACHE_TTL_SECONDS
        return health

    started = time.perf_counter()
    try:
        row = fetch_one("SELECT current_database() AS database_name, now() AS server_time", timeout_ms=700)
        health["connected"] = bool(row)
        health["database_name"] = (row or {}).get("database_name")
        health["server_time"] = str((row or {}).get("server_time")) if row else None
    except Exception as error:
        health["error"] = str(error)
    health["latency_ms"] = round((time.perf_counter() - started) * 1000, 1)
    _HEALTH_CACHE["payload"] = dict(health)
    _HEALTH_CACHE["expires_at"] = now + _HEALTH_CACHE_TTL_SECONDS
    return health


def prime_neon_runtime(table_names=None):
    if not is_configured():
        return
    started = time.perf_counter()
    connection = None
    try:
        connection = get_connection(statement_timeout_ms=500)
        _HEALTH_CACHE["payload"] = {
            "configured": True,
            "connected": True,
            "latency_ms": round((time.perf_counter() - started) * 1000, 1),
            "error": None,
            "database_name": None,
            "server_time": None,
        }
        _HEALTH_CACHE["expires_at"] = time.monotonic() + _HEALTH_CACHE_TTL_SECONDS
    except Exception as error:
        pass
    finally:
        release_connection(connection)
    if table_names:
        get_tables_columns(table_names, timeout_ms=700)
