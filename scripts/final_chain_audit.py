import inspect
import re
import sys
from pathlib import Path

from werkzeug.routing import MapAdapter

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


def endpoint_refs(text):
    return re.findall(r"url_for\(\s*['\"]([A-Za-z0-9_.]+)['\"]", text)


def route_refs(text):
    refs = []
    for attr in ("href", "action", "src"):
        refs.extend(re.findall(rf'{attr}="([^"]+)"', text))
        refs.extend(re.findall(rf"{attr}='([^']+)'", text))
    return refs


def normalize_route_ref(path):
    path = path.split("?", 1)[0]
    path = re.sub(r"\{\{[^}]+\}\}", "sample", path)
    path = re.sub(r"\{%[^%]+%\}", "", path)
    path = path.replace("//", "/")
    if not path.startswith("/"):
        path = "/" + path
    return path


def route_exists(adapter: MapAdapter, path: str):
    if path.startswith("/static/") or path.startswith("/api/"):
        return True
    if path in {"/#", "/javascript:void(0)"}:
        return True
    normalized = normalize_route_ref(path)
    for method in ("GET", "POST"):
        try:
            adapter.match(normalized, method=method)
            return True
        except Exception:
            continue
    return False


def collect_template_closure(initial_templates):
    pending = list(initial_templates)
    seen = set()
    include_refs = re.compile(r'{%\s*(?:include|extends)\s+["\']([^"\']+)["\']')

    while pending:
        template_name = pending.pop()
        if template_name in seen:
            continue
        seen.add(template_name)
        template_path = TEMPLATE_ROOT / template_name
        if not template_path.exists():
            continue
        text = template_path.read_text(encoding="utf-8", errors="ignore")
        for nested in include_refs.findall(text):
            if nested not in seen:
                pending.append(nested)
    return seen


def main():
    app = create_app()
    adapter = app.url_map.bind("localhost")
    endpoints = set(app.view_functions.keys())

    print("CHAIN final audit")
    print("=" * 72)

    missing_templates = []
    missing_static = set()
    wrong_endpoints = []
    missing_route_links = set()
    string_issues = []
    used_templates = set()

    for rule in sorted(app.url_map.iter_rules(), key=lambda item: (item.rule, item.endpoint)):
        if rule.endpoint == "static":
            continue
        methods = ",".join(sorted(method for method in rule.methods if method not in {"HEAD", "OPTIONS"}))
        print(f"{methods:10} {rule.rule:38} -> {rule.endpoint}")
        func = app.view_functions.get(rule.endpoint)
        if not func:
            continue
        for template_name in template_refs(func):
            used_templates.add(template_name)
            if not (TEMPLATE_ROOT / template_name).exists():
                missing_templates.append((rule.endpoint, template_name))

    used_templates = collect_template_closure(used_templates)

    scanned_files = list(ROOT.rglob("*.py")) + list(ROOT.rglob("*.html")) + list(ROOT.rglob("*.js")) + list(ROOT.rglob("*.css"))
    for path in scanned_files:
        if "venv" in path.parts or "__pycache__" in path.parts:
            continue
        if path.name == "final_chain_audit.py":
            continue
        if path.name.startswith("audit_chain_"):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")

        for ref in static_refs(text):
            if not (STATIC_ROOT / ref).exists():
                missing_static.add(ref)

        for endpoint in endpoint_refs(text):
            if endpoint not in endpoints and endpoint != "static":
                wrong_endpoints.append((path.relative_to(ROOT), endpoint))

        if path.suffix == ".html" and TEMPLATE_ROOT in path.parents:
            template_name = str(path.relative_to(TEMPLATE_ROOT))
            if template_name in used_templates:
                for ref in route_refs(text):
                    if not ref.startswith("/"):
                        continue
                    if ref.startswith(("http://", "https://", "mailto:", "tel:", "#")):
                        continue
                    if not route_exists(adapter, ref):
                        missing_route_links.add((str(path.relative_to(ROOT)), ref))

        for pattern in SCAN_PATTERNS:
            if pattern in text:
                string_issues.append((path.relative_to(ROOT), pattern))

    print("\nMissing templates")
    print("-" * 72)
    if missing_templates:
        for endpoint, template_name in missing_templates:
            print(f"{endpoint}: {template_name}")
    else:
        print("none")

    print("\nMissing static files")
    print("-" * 72)
    if missing_static:
        for ref in sorted(missing_static):
            print(ref)
    else:
        print("none")

    print("\nWrong endpoint names")
    print("-" * 72)
    if wrong_endpoints:
        for relpath, endpoint in sorted(set(wrong_endpoints)):
            print(f"{relpath}: {endpoint}")
    else:
        print("none")

    print("\nRoute links to missing pages")
    print("-" * 72)
    if missing_route_links:
        for relpath, ref in sorted(missing_route_links):
            print(f"{relpath}: {ref}")
    else:
        print("none")

    print("\nString scan")
    print("-" * 72)
    if string_issues:
        for relpath, pattern in string_issues:
            print(f"{relpath}: {pattern}")
    else:
        print("none")


if __name__ == "__main__":
    main()
