# CALLED BY: ragghost/surgeon/builders/__init__.py (BUILDERS registry) -> road.py (build stage); tested by tests/test_surgeon_modules.py
"""Build a static read-only JSON API -- a FOURTH fully-built output type, so the demo's own claim
("a landing page, API or dashboard") is true rather than aspirational. Reads the system's JSON
data and emits: one endpoint file per collection under api/, plus an index.html that documents
every endpoint. Static files only (servable by any host), no dependencies, nothing to run.
"""
from __future__ import annotations

import html
import json
import os

_SKIP = {".git", "node_modules", "__pycache__", ".venv", "dist", "build"}
_DATA_CANDIDATES = ["products.json", "orders.json", "items.json", "metrics.json", "data.json"]


def _find(ws, basename):
    root_hit = os.path.join(ws, basename)
    if os.path.exists(root_hit):
        return root_hit
    best, best_depth = None, 1 << 30
    for dp, dn, fn in os.walk(ws):
        dn[:] = [d for d in dn if d not in _SKIP and not d.startswith(".")]
        if basename in fn:
            depth = dp[len(ws):].count(os.sep)
            if depth < best_depth:
                best, best_depth = os.path.join(dp, basename), depth
    return best


def _load(ws, basename):
    p = _find(ws, basename)
    if not p or not os.path.exists(p):
        return None
    try:
        return json.load(open(p, encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _collections(ws):
    """Return {name: list-of-rows} for every readable JSON collection found."""
    out = {}
    for cand in _DATA_CANDIDATES:
        data = _load(ws, cand)
        name = cand.replace(".json", "")
        if isinstance(data, list):
            out[name] = data
        elif isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, list):
                    out[k] = v
    return out


def build(ws: str, scope, out_dir: str) -> dict:
    cfg = _load(ws, "config.json") or {}
    title = (cfg.get("store_name") if isinstance(cfg, dict) else None) or scope.get("store_name") or "API"
    cols = _collections(ws)
    api_dir = os.path.join(out_dir, "api")
    os.makedirs(api_dir, exist_ok=True)

    endpoints = []
    # a manifest endpoint listing everything, plus one endpoint per collection
    for name, rows in cols.items():
        with open(os.path.join(api_dir, "%s.json" % name), "w", encoding="utf-8") as fh:
            json.dump(rows, fh, indent=2)
        endpoints.append(("/api/%s.json" % name, len(rows)))
    manifest = {"title": title, "endpoints": [{"path": p, "records": n} for p, n in endpoints]}
    with open(os.path.join(api_dir, "index.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)

    rows_html = "".join(
        "<tr><td><a href='api%s'><code>%s</code></a></td><td>%d records</td></tr>"
        % (_p[len("/api"):] if _p.startswith("/api") else _p, html.escape(_p), n)
        for _p, n in endpoints)
    page = ("<!doctype html><html lang=en><head><meta charset=utf-8>"
            "<meta name=viewport content='width=device-width,initial-scale=1'>"
            "<title>%s API</title><style>body{font:16px/1.6 system-ui;margin:0;color:#0f172a}"
            "header{padding:28px;background:#0f172a;color:#fff;font-size:1.5rem;font-weight:700}"
            "table{border-collapse:collapse;margin:24px 28px}td{padding:10px 16px;border-bottom:1px solid #e2e8f0}"
            "code{background:#f1f5f9;padding:2px 6px;border-radius:6px}a{color:#2563eb}"
            "p{margin:20px 28px;color:#475569}</style></head><body>"
            "<header>%s API</header><p>Read-only JSON endpoints. Start at "
            "<a href='api/index.json'><code>/api/index.json</code></a>.</p>"
            "<table>%s</table></body></html>"
            % (html.escape(title), html.escape(title),
               rows_html or "<tr><td>No JSON collections found to serve.</td></tr>"))
    with open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8") as fh:
        fh.write(page)
    return {"title": title, "endpoints": len(endpoints), "collections": list(cols),
            "files": ["index.html", "api/index.json"] + ["api/%s.json" % n for n in cols]}


def rubric(scope):
    def has_manifest(o, c):
        return os.path.exists(os.path.join(o, "api", "index.json")), "api/index.json manifest present"

    def manifest_valid(o, c):
        p = os.path.join(o, "api", "index.json")
        if not os.path.exists(p):
            return False, "manifest missing"
        try:
            m = json.load(open(p, encoding="utf-8"))
            return isinstance(m.get("endpoints"), list), "manifest lists endpoints"
        except json.JSONDecodeError:
            return False, "manifest is not valid JSON"

    def has_index(o, c):
        return os.path.exists(os.path.join(o, "index.html")), "index.html documents the API"

    return [("has-manifest", has_manifest), ("manifest-valid", manifest_valid), ("has-index", has_index)]


def grade_context(ws, scope):
    cfg = _load(ws, "config.json") or {}
    return {"title": (cfg.get("store_name") if isinstance(cfg, dict) else None)
            or scope.get("store_name") or "API"}
