import inspect
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import create_app


TEMPLATE_ROOT = ROOT / "templates"
STATIC_ROOT = ROOT / "static"
SCAN_PATTERNS = ["Placeholder", "Mock", "fake", "updateNotifCount(3)"]


def unwrap(func):
    return inspect.unwrap(func)


def get_source(func):
    try:
        return inspect.getsource(unwrap(func))
    except OSError:
        return ""


def template_refs(func):
    return re.findall(r'render_template\(\s*["\']([^"\']+)["\']', get_source(func))


def static_refs(text):
    refs = set()
    refs.update(re.findall(r'/static/([A-Za-z0-9_./-]+)', text))
    refs.update(re.findall(r"url_for\(['\"]static['\"],\s*filename=['\"]([^'\"]+)['\"]\)", text))
    return refs


def main():
    app = create_app()
    print("CHAIN premium audit")
    print("=" * 72)

    missing_templates = []
    missing_static = set()

    for rule in sorted(app.url_map.iter_rules(), key=lambda item: (item.rule, item.endpoint)):
        if rule.endpoint == "static":
            continue
        methods = ",".join(sorted(method for method in rule.methods if method not in {"HEAD", "OPTIONS"}))
        print(f"{methods:10} {rule.rule:35} -> {rule.endpoint}")
        func = app.view_functions.get(rule.endpoint)
        if not func:
            continue
        for template_name in template_refs(func):
            if not (TEMPLATE_ROOT / template_name).exists():
                missing_templates.append((rule.endpoint, template_name))

    print("\nMissing templates")
    print("-" * 72)
    if missing_templates:
        for endpoint, template_name in missing_templates:
            print(f"{endpoint}: {template_name}")
    else:
        print("none")

    print("\nMissing static files")
    print("-" * 72)
    for path in list(TEMPLATE_ROOT.rglob("*.html")) + list((ROOT / "static").rglob("*.js")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for ref in static_refs(text):
            if not (STATIC_ROOT / ref).exists():
                missing_static.add(ref)
    if missing_static:
        for ref in sorted(missing_static):
            print(ref)
    else:
        print("none")

    print("\nString scan")
    print("-" * 72)
    issues = []
    for path in list(ROOT.rglob("*.py")) + list(ROOT.rglob("*.html")) + list(ROOT.rglob("*.js")):
        if "venv" in path.parts or "__pycache__" in path.parts:
            continue
        if path.name == "audit_chain_premium.py":
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in SCAN_PATTERNS:
            if pattern in text:
                issues.append((path.relative_to(ROOT), pattern))
    if issues:
        for relpath, pattern in issues:
            print(f"{relpath}: {pattern}")
    else:
        print("none")


if __name__ == "__main__":
    main()
