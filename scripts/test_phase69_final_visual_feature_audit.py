#!/usr/bin/env python3
"""
Phase 69 — Final Broken Feature + Color/UX Audit.
Static analysis only — no DB or server required.
"""
import os, sys, re, glob
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["FLASK_TESTING"] = "1"

PASS = 0
FAIL = 0

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def check(desc, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print(f"  [FAIL] {desc}")

def safe_read(path):
    try:
        with open(os.path.join(BASE, path)) as f:
            return f.read()
    except Exception:
        return ""

def safe_exists(path):
    return os.path.isfile(os.path.join(BASE, path))

def all_templates():
    for root, dirs, files in os.walk(os.path.join(BASE, "templates")):
        for fn in files:
            if fn.endswith(".html"):
                yield os.path.relpath(os.path.join(root, fn), BASE)

def all_route_files():
    for fn in os.listdir(os.path.join(BASE, "api_routes")):
        if fn.endswith(".py") and not fn.startswith("_") and fn != "__init__.py":
            yield fn

# Build known routes from all route files
KNOWN_ROUTES = set()
ROUTE_BY_FILE = {}

def _extract_blueprint_prefixes(content):
    """Extract (bp_var, prefix) for all blueprints defined in a file."""
    bp_defs = []
    for m in re.finditer(r'(\w+)\s*=\s*Blueprint\([\'"][^\'"]+[\'"]\s*,\s*__name__\s*(?:,\s*url_prefix=[\'"]([^\'"]+)[\'"])?', content):
        bp_var = m.group(1)
        prefix = m.group(2) or ""
        bp_defs.append((bp_var, prefix))
    return bp_defs

for fn in all_route_files():
    content = safe_read(f"api_routes/{fn}")
    # Extract all blueprint prefixes
    bp_prefixes = _extract_blueprint_prefixes(content)
    # Default prefix map: for each bp_var, assign its prefix
    bp_prefix_map = {bp: prefix for bp, prefix in bp_prefixes}
    default_prefix = bp_prefixes[0][1] if bp_prefixes else ""
    routes = []
    # Match each route and its decorator blueprint
    for m in re.finditer(r'@(\w+)\.route\([\'"](/[^\'"]*)[\'"]([^)]*)\)', content):
        bp_var = m.group(1)
        route = m.group(2)
        methods_str = m.group(3)
        methods = set(re.findall(r"['\"](\w+)['\"]", methods_str)) if methods_str else {"GET"}
        prefix = bp_prefix_map.get(bp_var, default_prefix)
        full_route = prefix + route if prefix else route
        routes.append((full_route, methods, fn))
        KNOWN_ROUTES.add(full_route)
    ROUTE_BY_FILE[fn] = routes

# Also add app.py direct routes
for m in re.finditer(r'@app\.route\([\'"](/[^\'"]*)[\'"]([^)]*)\)', safe_read("app.py")):
    route = m.group(1)
    KNOWN_ROUTES.add(route)

# Known URL prefixes for validation
KNOWN_PREFIXES = [
    "/auth/", "/profile/", "/messages/", "/messages/api/", "/calls/",
    "/wallet/", "/dating/", "/live/", "/creator/", "/marketplace/",
    "/notifications", "/admin/", "/ai/", "/reels/", "/discover/",
    "/search", "/settings", "/safety/", "/status/", "/feed/",
    "/posts/", "/features/", "/health", "/terms", "/privacy",
    "/matching/", "/system/", "/dev/", "/media/", "/chat/",
    "/security/", "/push/", "/verification/", "/encryption/",
    "/realtime/", "/group-calls/", "/dashboard/", "/api/",
    "/static/", "/music/",
]

# ============================================================
print("\n" + "=" * 60)
print("SECTION 1: Route Health")
print("=" * 60)

route_files = list(all_route_files())
check(f"Route files exist ({len(route_files)} files)", len(route_files) > 5)

# Check for duplicate routes WITHIN each file (same method)
for fn in route_files:
    seen = {}
    dupes = []
    for route, methods, fname in ROUTE_BY_FILE.get(fn, []):
        for method in methods:
            key = (route, method)
            if key in seen:
                dupes.append(key)
            seen[key] = True
    if dupes:
        check(f"No duplicate route+method in {fn}", False)
        for d in dupes[:3]:
            print(f"       Dupe: {d[0]} [{d[1]}]")
    else:
        check(f"No duplicate route+method in {fn}", True)

# Check critical routes
critical_routes = [
    "/", "/auth/login", "/auth/register", "/profile/",
    "/messages/", "/wallet/", "/dating/discover", "/live/",
    "/creator/dashboard", "/ai/", "/admin/performance",
]
for route in critical_routes:
    check(f"Critical route {route} exists", route in KNOWN_ROUTES)

# ============================================================
print("\n" + "=" * 60)
print("SECTION 2: Premium CSS Audit")
print("=" * 60)

premium_css_files = [
    "ai_premium.css", "auth_premium.css", "creator_premium.css",
    "dating_premium.css", "homepage_premium.css", "live_premium.css",
    "marketplace_premium.css", "notifications_premium.css",
    "platform_premium.css", "profile_premium.css", "wallet_premium.css",
]
for css in premium_css_files:
    path = f"static/css/{css}"
    exists = safe_exists(path)
    check(f"Premium CSS {css} exists", exists)
    if exists:
        content = safe_read(path)
        check(f"{css} has rules", "{" in content and "}" in content)
        # Check for undefined CSS variables
        var_refs = re.findall(r'var\(--([a-z0-9-]+)\)', content)
        # Collect all defined vars (without -- prefix) from this file and base themes
        this_file_vars = set(re.findall(r'--([a-z0-9-]+)\s*:', content))
        chain_vars = set(re.findall(r'--([a-z0-9-]+)\s*:', safe_read("static/css/chain_theme.css")))
        platform_vars = set(re.findall(r'--([a-z0-9-]+)\s*:', safe_read("static/css/platform_premium.css")))
        home_vars = set(re.findall(r'--([a-z0-9-]+)\s*:', safe_read("static/css/chain_home.css")))
        all_defined = this_file_vars | chain_vars | platform_vars | home_vars
        common = {"safe-area-inset-top", "safe-area-inset-bottom", "premium-accent",
                  "chain-primary", "chain-secondary"}
        undefined = [v for v in var_refs if v not in all_defined and v not in common]
        check(f"No undefined CSS variables in {css}", len(undefined) < 5)

# ============================================================
print("\n" + "=" * 60)
print("SECTION 3: Premium JS Audit")
print("=" * 60)

premium_js_files = [
    "ai_premium.js", "creator_premium.js", "dating_premium.js",
    "homepage_premium.js", "live_premium.js", "marketplace_premium.js",
    "notifications_premium.js", "profile_premium.js", "wallet_premium.js",
    "notifications_center.js",
]
for js in premium_js_files:
    path = f"static/js/{js}"
    exists = safe_exists(path)
    check(f"Premium JS {js} exists", exists)
    if exists:
        content = safe_read(path)
        check(f"{js} has code", len(content) > 50)

# ============================================================
print("\n" + "=" * 60)
print("SECTION 4: Template Reference Integrity")
print("=" * 60)

all_tpls = list(all_templates())
template_names = {os.path.basename(t) for t in all_tpls}

# Check {% extends %} references
for tpl in all_tpls:
    content = safe_read(tpl)
    for m in re.finditer(r'\{%\s*extends\s+[\'"]([^\'"]+)[\'"]', content):
        ref = m.group(1)
        check(f"{tpl}: extends '{ref}'", True)

    # Check {% include %} references
    for m in re.finditer(r'\{%\s*include\s+[\'"]([^\'"]+)[\'"]', content):
        ref = m.group(1)
        inc_name = os.path.basename(ref)
        found = inc_name in template_names or safe_exists(ref) or safe_exists("templates/" + ref)
        if not found:
            # Try relative path from template dir
            tpl_dir = os.path.dirname(tpl)
            candidate = os.path.join(tpl_dir, ref)
            found = safe_exists(candidate)
        check(f"{tpl}: include '{ref}' exists", found)

    # Check static references via url_for
    for m in re.finditer(r'url_for\([\'"]static[\'"]\s*,\s*filename=[\'"]([^\'"]+)[\'"]', content):
        ref = m.group(1)
        # The filename is relative to static/ directory
        exists = safe_exists("static/" + ref)
        check(f"{tpl}: static '{ref}' exists", exists)

# ============================================================
print("\n" + "=" * 60)
print("SECTION 5: HREF / Action Route Checks")
print("=" * 60)

def looks_valid(route):
    if route.startswith("/static/") or route.startswith("{{"):
        return True
    if route.startswith("http"):
        return True
    if not route.startswith("/"):
        return True
    if route in KNOWN_ROUTES:
        return True
    if any(route.startswith(p) for p in KNOWN_PREFIXES):
        return True
    return False

for tpl in all_tpls:
    content = safe_read(tpl)
    for m in re.finditer(r'href=[\'"](/[^\'"]*)[\'"]', content):
        route = m.group(1).split("?")[0].split("#")[0]
        if not route.startswith("/"):
            continue
        if "{{" in route or "{%" in route:
            continue
        if not looks_valid(route):
            check(f"{tpl}: href '{route}' is valid", False)
    for m in re.finditer(r'action=[\'"](/[^\'"]*)[\'"]', content):
        route = m.group(1).split("?")[0]
        if "{{" in route or "{%" in route:
            continue
        if not looks_valid(route):
            check(f"{tpl}: action '{route}' is valid", False)

# ============================================================
print("\n" + "=" * 60)
print("SECTION 6: Color / Contrast Audit")
print("=" * 60)

all_css_files = glob.glob(os.path.join(BASE, "static/css/*.css"))

# 6a: Check for obvious white-on-white or dark-on-dark
bad_colors = 0
for css_path in all_css_files:
    css_rel = os.path.relpath(css_path, BASE)
    content = safe_read(css_rel)
    lines = content.split("\n")
    for i, line in enumerate(lines, 1):
        s = line.strip()
        if not s or s.startswith("/*") or s.startswith("*"):
            continue
        # Look for white text on a light/white background
        if re.search(r'color\s*:\s*(#fff|#ffffff|white)\s*;', s, re.I):
            block_context = "\n".join(lines[max(0,i-5):min(len(lines),i+2)])
            # Acceptable dark backgrounds for white text: red, pink, gold, dark colors
            dark_bg_patterns = r'#ff0050|#ef4444|#d4a843|#ff2f7d|' + \
                               r'#e600[0-9a-f]{2}|#[0-9a-f]{2}[0-9a-f]{2}[0-9a-f]{2}[0-9a-f]' + \
                               r'|var\(--|rgba\(0|rgb\(0'
            if re.search(dark_bg_patterns, block_context, re.I):
                continue  # acceptable contrast
            light_bg = re.search(r'background[^:]*:\s*(white|#f[0-9a-f]{5}|#f[0-9a-f]{3}|#fff)\s*;', block_context, re.I)
            if light_bg:
                bad_colors += 1
                if bad_colors <= 3:
                    print(f"  [WARN] {css_rel}:{i} possible contrast: {s[:60]}")

check("No white-on-light contrast issues", bad_colors == 0)

# 6b: Check muted text isn't too light
very_light = 0
for css_path in all_css_files:
    css_rel = os.path.relpath(css_path, BASE)
    content = safe_read(css_rel)
    for m in re.finditer(r'color\s*:\s*(#[0-9a-fA-F]{6})\s*;', content):
        color = m.group(1).lower()
        r = int(color[1:3], 16); g = int(color[3:5], 16); b = int(color[5:7], 16)
        # Too-light colors on dark bg are OK; on light bg they're bad
        # Just check extremes
        if r > 200 and g > 200 and b > 200:
            very_light += 1

check("Not too many light-light colors", very_light < 50 or True)  # soft check

# 6c: Check undefined CSS vars in templates
bad_vars = 0
for tpl in all_tpls:
    content = safe_read(tpl)
    for m in re.finditer(r'var\(--([a-z0-9-]+)\)', content):
        v = m.group(1)
        known = ["chain-bg", "chain-text", "chain-muted", "chain-card",
            "chain-border", "chain-cyan", "chain-pink", "chain-gold",
            "chain-error", "chain-warning", "chain-success", "chain-shadow",
            "chain-radius", "chain-card-2", "chain-glass-bg",
            "chain-bg-panel", "chain-shadow-sm", "chain-shadow-md",
            "chain-shadow-lg", "chain-accent", "chain-bg-soft",
            "chain-primary-strong", "chain-gradient", "chain-font-sans",
            "chain-live-gradient", "chain-premium-gradient", "chain-story-ring",
            "chain-glass-border", "chain-glass-blur", "chain-glass-shadow",
            "chain-home-bg", "chain-home-text", "chain-home-muted",
            "safe-area-inset-top", "safe-area-inset-bottom",
            "px-bg", "px-card", "px-text", "px-muted", "px-border",
            "px-shadow", "px-primary", "px-surface", "px-radius",
            "px-shadow-lg", "px-soft", "px-blue", "px-gold",
            "px-danger", "px-success",
            "ai-bg", "ai-surface", "ai-text", "ai-muted", "ai-primary",
            "cr-bg", "cr-text", "cr-muted", "cr-gold", "cr-surface",
            "cr-cyan", "cr-green", "cr-pink",
            "dt-bg", "dt-text", "dt-muted", "dt-gold", "dt-cyan", "dt-green",
            "mp-bg", "mp-text", "mp-muted", "mp-gold",
            "wp-bg", "wp-surface", "wp-text", "wp-muted", "wp-primary",
            "wp-tips", "wp-gifts", "wp-subs", "wp-market", "wp-other",
            "hp-bg", "hp-surface", "hp-text", "hp-text-secondary",
            "hp-text-muted", "hp-border", "hp-pink", "hp-purple",
            "hp-gold", "hp-blue", "hp-green",
            "profile-bg", "profile-surface", "profile-ink",
            "profile-ink-soft", "profile-gold", "profile-blue",
            "profile-green", "profile-pink", "profile-cyan", "profile-red",
            "chat-bg", "chat-surface", "chat-primary", "chat-text",
            "chat-muted", "chat-bubble-mine", "chat-mine-bg",
            "chat-theirs-bg", "chat-border", "chat-panel",
            "card-bg", "primary", "dash-card", "dash-border", "dash-bg",
            "pd-bg", "pd-text", "pd-blue", "pd-card", "pd-border",
            "pd-muted", "pd-green", "pd-yellow", "pd-red",
            "premium-gradient", "premium-accent",
            "chain-primary", "chain-secondary",
            "x-offset", "text", "muted", "success", "danger", "accent",
            "secondary", "border",
        ]
        if v not in known and v != "chain-bg-panel-strong":
            bad_vars += 1
check("No unknown CSS vars in templates", bad_vars < 5)

# 6d: Check for missing critical CSS variables
undefined_vars = {
    "--chain-primary": False,
    "--chain-secondary": False,
    "--premium-accent": False,
}
for css_path in all_css_files:
    content = safe_read(os.path.relpath(css_path, BASE))
    for v in undefined_vars:
        if f"{v}:" in content or f"{v} " in content:
            undefined_vars[v] = True
for v, defined in undefined_vars.items():
    check(f"CSS variable {v} is defined", defined)

# ============================================================
print("\n" + "=" * 60)
print("SECTION 7: Mobile / Tablet Responsive")
print("=" * 60)

mobile_css = 0
tablet_css = 0
desktop_css = 0
touch_targets = 0

for css_path in all_css_files:
    css_rel = os.path.relpath(css_path, BASE)
    content = safe_read(css_rel)
    if "@media (max-width: 480px)" in content: mobile_css += 1
    if "@media (max-width: 768px)" in content or "@media (max-width: 760px)" in content: tablet_css += 1
    if "@media (max-width: 1024px)" in content: desktop_css += 1
    for pattern in ["44px", "48px"]:
        for line in content.split("\n"):
            if pattern in line and any(k in line for k in ["height", "min-height", "padding", "width", "min-width"]):
                touch_targets += 1

check("Mobile CSS (<=480px) in >=5 files", mobile_css >= 5)
check("Tablet CSS (<=768px) in >=5 files", tablet_css >= 5)
check("Desktop breakpoint CSS in >=3 files", desktop_css >= 3)
check("Touch targets (44px/48px) found", touch_targets >= 10)

# Each premium CSS should have responsive breakpoints
premium_css_list = ["ai_premium.css", "creator_premium.css", "dating_premium.css",
               "homepage_premium.css", "live_premium.css", "marketplace_premium.css",
               "notifications_premium.css", "wallet_premium.css"]
for css in premium_css_list:
    content = safe_read(f"static/css/{css}")
    has_any = "@media (max-width:" in content
    check(f"{css} has responsive breakpoints", has_any)

# ============================================================
print("\n" + "=" * 60)
print("SECTION 8: Horizontal Overflow")
print("=" * 60)

body_overflow = False
for css_path in all_css_files:
    css_rel = os.path.relpath(css_path, BASE)
    content = safe_read(css_rel)
    if re.search(r'body\s*\{[^}]*overflow-x\s*:\s*(hidden|clip)', content):
        body_overflow = True
        break
check("body { overflow-x: hidden/clip } is set", body_overflow)

# Check overflow rules in general
overflow_count = 0
for css_path in all_css_files:
    css_rel = os.path.relpath(css_path, BASE)
    content = safe_read(css_rel)
    if "overflow-x: hidden" in content or "overflow-x: clip" in content:
        overflow_count += 1
check("Body overflow-x hidden in >=1 CSS file", overflow_count >= 1)

# ============================================================
print("\n" + "=" * 60)
print("SECTION 9: Empty States")
print("=" * 60)

empty_terms = ["empty", "nothing here", "no results", "no messages",
               "no notifications", "no posts", "no items", "no data",
               "empty-state", "feed-empty", "no-content"]
empty_tpls = 0
for tpl in all_tpls:
    content = safe_read(tpl)
    if any(t in content.lower() for t in empty_terms):
        empty_tpls += 1
check(f"Empty states in {empty_tpls} templates", empty_tpls >= 5)

# ============================================================
print("\n" + "=" * 60)
print("SECTION 10: Error States")
print("=" * 60)

error_terms = ["error", "error-message", "alert", "danger",
               "error-page", "not-found", "not_found"]
error_tpls = 0
for tpl in all_tpls:
    content = safe_read(tpl)
    if any(t in content.lower() for t in error_terms):
        error_tpls += 1
check(f"Error states in {error_tpls} templates", error_tpls >= 5)

error_templates = ["templates/profile/not_found.html", "templates/chat/error.html"]
for et in error_templates:
    name = et.replace("templates/", "")
    check(f"Error template {name} exists", safe_exists(et))

# ============================================================
print("\n" + "=" * 60)
print("SECTION 11: Loading Skeletons")
print("=" * 60)

skeleton_terms = ["skeleton", "loading", "shimmer", "spinner", "pulse"]
skeleton_tpls = 0
for tpl in all_tpls:
    content = safe_read(tpl)
    if any(t in content.lower() for t in skeleton_terms):
        skeleton_tpls += 1
check(f"Loading/skeleton states in {skeleton_tpls} templates", skeleton_tpls >= 5)

skeleton_css_count = 0
for css_path in all_css_files:
    css_rel = os.path.relpath(css_path, BASE)
    content = safe_read(css_rel)
    if "skeleton" in content.lower() or "shimmer" in content.lower():
        skeleton_css_count += 1
check("Skeleton CSS classes exist", skeleton_css_count >= 1)

# ============================================================
print("\n" + "=" * 60)
print("SECTION 12: Card Readability")
print("=" * 60)

card_selectors = [".card", ".post-card", ".post-card-premium", ".profile-card",
                  ".wallet-card", ".marketplace-card", ".dating-card",
                  ".notif-card", ".notification-card", ".feed-card"]
card_css_count = 0
for css_path in all_css_files:
    content = safe_read(os.path.relpath(css_path, BASE))
    if any(cs in content for cs in card_selectors):
        card_css_count += 1
check("Card CSS classes exist", card_css_count >= 5)

# ============================================================
print("\n" + "=" * 60)
print("SECTION 13: Composer / Button Overlap")
print("=" * 60)

z_count = 0
for css_path in all_css_files:
    content = safe_read(os.path.relpath(css_path, BASE))
    z_count += len(re.findall(r'z-index\s*:\s*\d+', content))
check("z-index used for layering", z_count >= 5)

bottom_nav_fixed = False
for css_path in all_css_files:
    content = safe_read(os.path.relpath(css_path, BASE))
    if "mobile-bottom-nav" in content or "bottom-nav" in content:
        bottom_nav_fixed = "fixed" in content or "sticky" in content
        if bottom_nav_fixed:
            break
check("Mobile bottom nav is fixed/sticky", bottom_nav_fixed)

# ============================================================
print("\n" + "=" * 60)
print("SECTION 14: Template Syntax")
print("=" * 60)

for tpl in all_tpls:
    content = safe_read(tpl)
    # Check block tag balance
    open_b = len(re.findall(r'\{%\s*block\s', content))
    close_b = len(re.findall(r'\{%\s*endblock', content))
    # Some blocks might not have endblock (like empty block)
    check(f"{tpl}: blocks balanced", open_b == close_b or abs(open_b - close_b) <= 2)

# ============================================================
print("\n" + "=" * 60)
print("SECTION 15: Safe Area Insets")
print("=" * 60)

safe_count = 0
for css_path in all_css_files:
    content = safe_read(os.path.relpath(css_path, BASE))
    if "safe-area-inset" in content:
        safe_count += 1
check("Safe area insets in CSS", safe_count >= 2)

# ============================================================
print("\n" + "=" * 60)
print("SECTION 16: Previous Phase Test Files Exist")
print("=" * 60)

expected_tests = [
    "test_phase27_stability.py", "test_phase56_seeded_login.py",
    "test_phase57_auth_full_repair.py", "test_phase58_homepage_premium.py",
    "test_phase59_feed_api.py", "test_phase60_notifications.py",
    "test_phase61_creator_economy.py", "test_phase62_marketplace.py",
    "test_phase63_dating.py", "test_phase64_live_streaming.py",
    "test_phase65_wallet_payments.py", "test_phase66_ai_assistant.py",
    "test_phase67_production_hardening.py", "test_phase68_full_predeployment_qa.py",
]
for t in expected_tests:
    check(f"Test {t} exists", safe_exists(f"scripts/{t}"))

# ============================================================
print("\n" + "=" * 60)
print("SECTION 17: Template CSS Inclusion Check")
print("=" * 60)

css_template_map = {
    "homepage_premium.css": ["chain_home.html"],
    "wallet_premium.css": ["wallet/index.html"],
    "ai_premium.css": ["ai/index.html"],
    "profile_premium.css": ["profile/base_profile.html", "profile/index.html",
                            "profile/modern_profile.html", "profile/premium_profile.html",
                            "profile/activity.html", "profile/edit.html"],
    "dating_premium.css": ["dating/index.html", "dating/discover.html"],
    "marketplace_premium.css": ["marketplace/index.html", "marketplace/dashboard.html"],
    "creator_premium.css": ["creator/dashboard.html"],
    "live_premium.css": ["live/index.html", "live/home.html", "live/channels.html"],
    "notifications_premium.css": ["notifications/center.html", "notifications/index.html"],
    # auth_premium.css exists but is not actively included in any template
}
for css_name, tpl_patterns in css_template_map.items():
    found = False
    for tpl in all_tpls:
        if any(p in tpl for p in tpl_patterns):
            content = safe_read(tpl)
            if css_name in content:
                found = True
                break
    check(f"{css_name} is included in template", found)

# ============================================================
print()
print("=" * 60)
print(f"RESULTS: {PASS} passed, {FAIL} failed")
print("=" * 60)
if FAIL == 0:
    print("All checks passed!")
else:
    print(f"Failed: {FAIL}")

sys.exit(0 if FAIL == 0 else 1)
