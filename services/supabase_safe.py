import os

try:
    from postgrest.exceptions import APIError
except Exception:  # pragma: no cover
    class APIError(Exception):
        pass

from utils.supabase_client import get_supabase_admin


_COLUMN_CACHE = {}
_TABLE_EXISTS_CACHE = {}
_WARNED_MESSAGES = set()


def _is_api_error(error):
    return isinstance(error, APIError) or error.__class__.__name__ == "APIError"


def _warn_once(key, message):
    if key in _WARNED_MESSAGES:
        return
    _WARNED_MESSAGES.add(key)
    if os.getenv("SUPABASE_SAFE_DEBUG") == "1":
        print(message)


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
        elif operator == "neq":
            query = query.neq(column, value)
        elif operator == "gt":
            query = query.gt(column, value)
        elif operator == "gte":
            query = query.gte(column, value)
        elif operator == "lt":
            query = query.lt(column, value)
        elif operator == "lte":
            query = query.lte(column, value)
        elif operator == "like":
            query = query.like(column, value)
        elif operator == "ilike":
            query = query.ilike(column, value)
        elif operator == "in":
            query = query.in_(column, value)
        elif operator == "is":
            query = query.is_(column, value)
        elif operator == "not.is":
            query = query.not_.is_(column, value)
        elif operator == "contains":
            query = query.contains(column, value)
        else:
            raise ValueError(f"Unsupported filter operator: {operator}")

    return query


def table_exists(table):
    if table in _TABLE_EXISTS_CACHE:
        return _TABLE_EXISTS_CACHE[table]

    try:
        admin = get_supabase_admin()
        admin.table(table).select("id").limit(1).execute()
        _TABLE_EXISTS_CACHE[table] = True
        return True
    except Exception as error:
        if _is_api_error(error):
            _warn_once(f"table:{table}:api", f"[supabase_safe] table_exists({table}) -> False: {error}")
            _TABLE_EXISTS_CACHE[table] = False
            return False
        _warn_once(f"table:{table}:transport", f"[supabase_safe] table_exists({table}) failed: {error}")
        _TABLE_EXISTS_CACHE[table] = False
        return False


def _load_columns(table):
    if table in _COLUMN_CACHE:
        return _COLUMN_CACHE[table]

    admin = get_supabase_admin()
    columns = set()
    try:
        response = (
            admin.table("information_schema.columns")
            .select("column_name")
            .eq("table_schema", "public")
            .eq("table_name", table)
            .limit(500)
            .execute()
        )
        columns = {row["column_name"] for row in (response.data or []) if row.get("column_name")}
    except Exception:
        columns = set()

    _COLUMN_CACHE[table] = columns
    return columns


def column_safe_payload(table, payload, fallback_columns=None):
    if payload is None:
        return {}

    safe_payload = {key: value for key, value in payload.items() if value is not None}
    known_columns = _load_columns(table)

    if known_columns:
        return {key: value for key, value in safe_payload.items() if key in known_columns}

    if fallback_columns:
        fallback_set = set(fallback_columns)
        return {key: value for key, value in safe_payload.items() if key in fallback_set}

    return safe_payload


def safe_select(table, columns="*", limit=20, filters=None, order_by="created_at", desc=True):
    if not table_exists(table):
        return []

    admin = get_supabase_admin()

    def build_query(include_order=True):
        query = admin.table(table).select(columns)
        query = _apply_filters(query, filters)
        if include_order and order_by:
            query = query.order(order_by, desc=desc)
        if limit is not None:
            query = query.limit(limit)
        return query

    try:
        return build_query(include_order=True).execute().data or []
    except Exception as first_error:
        if order_by:
            try:
                return build_query(include_order=False).execute().data or []
            except Exception as second_error:
                _warn_once(f"select:{table}", f"[supabase_safe] safe_select({table}) failed: {second_error}")
                return []
        _warn_once(f"select:{table}", f"[supabase_safe] safe_select({table}) failed: {first_error}")
        return []


def safe_count(table, filters=None):
    if not table_exists(table):
        return 0

    try:
        admin = get_supabase_admin()
        query = admin.table(table).select("id", count="exact").limit(1)
        query = _apply_filters(query, filters)
        result = query.execute()
        return result.count or 0
    except Exception as error:
        _warn_once(f"count:{table}", f"[supabase_safe] safe_count({table}) failed: {error}")
        return 0


def safe_insert(table, payload, fallback_columns=None):
    if not table_exists(table):
        return None

    try:
        admin = get_supabase_admin()
        safe_payload = column_safe_payload(table, payload, fallback_columns=fallback_columns)
        if safe_payload in ({}, []):
            return []
        result = admin.table(table).insert(safe_payload).execute()
        return result.data if result.data is not None else []
    except Exception as error:
        _warn_once(f"insert:{table}", f"[supabase_safe] safe_insert({table}) failed: {error}")
        return None


def safe_update(table, payload, eq=None, fallback_columns=None):
    if not table_exists(table):
        return None

    try:
        admin = get_supabase_admin()
        safe_payload = column_safe_payload(table, payload, fallback_columns=fallback_columns)
        if not safe_payload:
            return []
        query = admin.table(table).update(safe_payload)
        query = _apply_filters(query, eq)
        result = query.execute()
        return result.data if result.data is not None else []
    except Exception as error:
        _warn_once(f"update:{table}", f"[supabase_safe] safe_update({table}) failed: {error}")
        return None


def safe_delete(table, eq=None):
    if not table_exists(table):
        return None

    try:
        admin = get_supabase_admin()
        query = admin.table(table).delete()
        query = _apply_filters(query, eq)
        result = query.execute()
        return result.data if result.data is not None else []
    except Exception as error:
        _warn_once(f"delete:{table}", f"[supabase_safe] safe_delete({table}) failed: {error}")
        return None
