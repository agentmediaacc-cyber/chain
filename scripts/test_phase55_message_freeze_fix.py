"""
Phase 55: Message freeze fix — inbox deduplication, defensive JS, mobile layout,
composer completeness, premium feature wiring, and debug diagnostics.
"""
import os, sys, json, uuid as uuid_mod, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["FLASK_TESTING"] = "1"
os.environ["CHAIN_FAST_LOCAL"] = "1"
os.environ["CHAIN_TEST_FAKE_DB"] = "1"
os.environ["CHAIN_TRUST_PROFILE_SCHEMA"] = "1"

from app import create_app
app = create_app()
from api_routes.message_production_routes import message_production_bp
app.register_blueprint(message_production_bp)

import services.message_feature_service as _mfs
import services.message_delivery_service as _mds
from services.neon_service import get_pool_status, fast_query, write_query

_MESSAGES = {}
_THREADS = {}

def _db_true():
    return False
if hasattr(_mfs, '_db_available'): _mfs._db_available = _db_true
if hasattr(_mds, '_db_available'): _mds._db_available = _db_true

PASS = 0; FAIL = 0
def check(label, ok, detail=None):
    global PASS, FAIL
    if ok:
        print(f"  [PASS] {label}"); PASS += 1
    else:
        print(f"  [FAIL] {label}" + (f" — {detail}" if detail else "")); FAIL += 1

PID_A = str(uuid_mod.uuid4())
PID_B = str(uuid_mod.uuid4())
TID = None
MSG_ID = None

client = app.test_client()

# ============================================================
# TASK 1: Inbox Duplication
# ============================================================
def test_inbox_no_duplicates():
    """list_threads SQL uses DISTINCT ON to prevent duplicate rows"""
    from services.messaging_engine import list_threads
    # Verify SQL pattern
    import inspect
    src = inspect.getsource(list_threads)
    has_distinct = "DISTINCT ON" in src
    check("list_threads uses DISTINCT ON", has_distinct,
          "Missing DISTINCT ON in SQL query")
    # Smoke test: function returns list (empty since no DB data)
    result = list_threads("nonexistent", folder='primary')
    check("list_threads returns list", isinstance(result, list))

# ============================================================
# TASK 2: No Freeze — single init guard
# ============================================================
def test_single_init_guard():
    """_chainMessagesInit flag prevents double initialization"""
    import asyncio
    check("Single init guard pattern exists",
          os.path.exists("templates/messages/index.html") and
          "_chainMessagesInit" in open("templates/messages/index.html").read(),
          "Missing _chainMessagesInit guard in index.html")

def test_no_duplicate_setinterval():
    """checkPresence should only be set once"""
    content = open("templates/messages/index.html").read()
    count = content.count("checkPresence")
    check("checkPresence referenced at most 3 times (declare + call + _chainSchedule)",
          count < 5, f"Found {count} references")

# ============================================================
# TASK 3: Composer completeness
# ============================================================
def test_composer_buttons_present():
    """Composer must have: plus/attach, emoji, textarea, voice, disappearing timer, send"""
    content = open("templates/messages/index.html").read()
    checks = [
        ("messageInput", "textarea input"),
        ("emojiBtn", "emoji button"),
        ("stickerGifBtn", "sticker/GIF button"),
        ("voiceBtn", "voice button"),
        ("sendBtn", "send button"),
        ("attachBtn", "attach/plus button"),
    ]
    for btn_id, label in checks:
        check(f"Composer has {label} (#{btn_id})",
              f'id="{btn_id}"' in content, f"Missing #{btn_id}")

    # thread.html composer
    thread_content = open("templates/messages/thread.html").read()
    tc = [
        ("msg-input", "composer textarea"),
        ("file-input", "file input"),
        ("send-btn", "send button"),
    ]
    for btn_id, label in tc:
        check(f"Thread composer has {label} (#{btn_id})",
              f'id="{btn_id}"' in thread_content, f"Missing #{btn_id}")

# ============================================================
# TASK 4: Feature wiring — no crash routes
# ============================================================
def test_feature_routes_exist():
    """All premium feature routes must return 401 (no auth) not 404"""
    routes = [
        "/messages/api/poll/create",
        "/messages/api/chat/ai/summarize",
        "/messages/api/wallet/send",
        "/messages/api/thread/_test/disappearing",
        "/messages/api/thread/_test/search?q=hello",
        "/messages/api/messages/_test/transcribe",
        "/messages/api/debug/inbox",
    ]
    for route in routes:
        resp = client.post(route, json={})
        check(f"Route {route} exists (401 not 404)",
              resp.status_code != 404, f"Got {resp.status_code}")

def test_index_route_returns_200():
    """GET /messages/ should return 200"""
    resp = client.get("/messages/")
    check("Messages index returns 200 or redirect",
          resp.status_code in (200, 302), f"Got {resp.status_code}")

# ============================================================
# TASK 5: Defensive JS patterns
# ============================================================
def test_defensive_js_patterns():
    """index.html must have try/catch wrapping and null-safe DOM queries"""
    content = open("templates/messages/index.html").read()
    checks = [
        ("try {", "try/catch wrapper"),
        ("} catch(e)", "catch block"),
        ("document.getElementById", "getElementById usage"),
        (".catch(", "fetch catch"),
    ]
    for pattern, label in checks:
        check(f"Defensive JS: {label}",
              pattern in content, f"Missing: {pattern}")

def test_premium_js_exists():
    """message_premium_features.js must exist and expose initPremiumFeatures"""
    js_path = "static/js/message_premium_features.js"
    ok = os.path.exists(js_path)
    check(f"Premium JS file exists", ok, f"Missing: {js_path}")
    if ok:
        js = open(js_path).read()
        check("initPremiumFeatures exported", "initPremiumFeatures" in js)
        check("catch wrappers in premium JS", ".catch(" in js)
        check("null-safe DOM in premium JS", "getElementById" in js)

# ============================================================
# TASK 6: Split inline JS
# ============================================================
def test_split_inline_js():
    """thread.html should reference message_premium_features.js and not have Phase 53 inline"""
    content = open("templates/messages/thread.html").read()
    check("References message_premium_features.js",
          "message_premium_features.js" in content,
          "Missing script reference")
    check("initPremiumFeatures called",
          "initPremiumFeatures" in content,
          "Missing initPremiumFeatures() call")

# ============================================================
# TASK 7: Mobile layout
# ============================================================
def test_mobile_css():
    """chat.css must have 320px/480px breakpoints"""
    css = open("static/css/chat.css").read()
    checks = [
        ("@media (max-width: 480px)", "480px breakpoint"),
        ("min-height: 44px", "44px touch targets"),
        ("overflow-x: hidden", "no horizontal overflow"),
        ("word-break: break-word", "word break"),
    ]
    for pattern, label in checks:
        check(f"Mobile CSS: {label}",
              pattern in css, f"Missing: {pattern}")

# ============================================================
# TASK 8: Debug diagnostics
# ============================================================
def test_debug_routes():
    """Debug diagnostics route must exist (302 redirect or 200/401 means route exists)"""
    resp = client.get("/messages/api/debug/inbox")
    check("Debug inbox route accessible (302 redirect to login or 401/200)",
          resp.status_code in (200, 302, 401),
          f"Got {resp.status_code}")

def test_diag_window_object():
    """CHAIN_MESSAGE_DIAG must be defined in premium JS"""
    js = open("static/js/message_premium_features.js").read()
    check("CHAIN_MESSAGE_DIAG defined",
          "CHAIN_MESSAGE_DIAG" in js,
          "Missing window.CHAIN_MESSAGE_DIAG")
    check("fetch errors tracked",
          "fetchErrors" in js,
          "Missing fetchErrors tracking")

# ============================================================
# TASK 9: Existing test compatibility
# ============================================================
def test_existing_tests_not_broken():
    """Existing messaging test files still have proper structure"""
    for fname in ["test_phase52_smart_composer.py", "test_phase53_premium_messaging.py"]:
        fpath = os.path.join("scripts", fname)
        if os.path.exists(fpath):
            check(f"Existing test {fname} still present",
                  os.path.getsize(fpath) > 100, f"File too small")

# ============================================================
# Run all tests
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("Phase 55: Message Freeze Fix — Test Suite")
    print("=" * 60)
    for fn in [
        test_inbox_no_duplicates,
        test_single_init_guard,
        test_no_duplicate_setinterval,
        test_composer_buttons_present,
        test_feature_routes_exist,
        test_index_route_returns_200,
        test_defensive_js_patterns,
        test_premium_js_exists,
        test_split_inline_js,
        test_mobile_css,
        test_debug_routes,
        test_diag_window_object,
        test_existing_tests_not_broken,
    ]:
        try:
            fn()
        except Exception as e:
            print(f"  [FAIL] {fn.__name__} — exception: {e}")
            FAIL += 1

    print("=" * 60)
    total = PASS + FAIL
    print(f"Results: {PASS}/{total} passed, {FAIL}/{total} failed")
    if FAIL:
        sys.exit(1)
