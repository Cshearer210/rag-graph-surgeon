# CALLED BY: ragghost/surgeon/builders/__init__.py (BUILDERS registry) -> road.py (build stage); tested by tests/test_surgeon_modules.py
"""Build a marketing landing page with a signup -- a second, fully-built output type, so "ships a
variety" is demonstrated rather than asserted. Reads config.json (store_name/tagline/features).
"""
from __future__ import annotations

import html
import os

from .._common import load as _load, name_context, slurp as _slurp








def build(ws: str, scope, out_dir: str) -> dict:
    cfg = _load(ws, "config.json", {})
    name = cfg.get("store_name") or scope.get("store_name") or "Your Product"
    tagline = cfg.get("tagline") or scope.get("goal") or "The thing you have been waiting for."
    features = cfg.get("features") or ["Fast", "Private", "Yours"]
    os.makedirs(out_dir, exist_ok=True)
    feat = "".join("<li>%s</li>" % html.escape(str(f)) for f in features)
    page = ("<!doctype html><html lang=en><head><meta charset=utf-8>"
            "<meta name=viewport content='width=device-width,initial-scale=1'>"
            "<title>%s</title><style>body{font:16px/1.6 system-ui;margin:0;color:#111}"
            ".hero{padding:80px 24px;text-align:center;background:#0f172a;color:#fff}"
            ".hero h1{font-size:2.6rem;margin:0 0 12px}ul{max-width:600px;margin:32px auto;"
            "list-style:none;padding:0;display:flex;gap:16px;justify-content:center;flex-wrap:wrap}"
            "li{background:#f1f5f9;padding:10px 18px;border-radius:999px}"
            "form{margin:24px auto;max-width:420px;display:flex;gap:8px}"
            "input{flex:1;padding:12px;border:1px solid #cbd5e1;border-radius:8px}"
            "button{padding:12px 20px;border:0;border-radius:8px;background:#3b82f6;color:#fff}</style>"
            "</head><body><section class=hero><h1>%s</h1><p>%s</p>"
            "<form onsubmit=\"event.preventDefault();this.querySelector('button').textContent='Thanks!'\">"
            "<input type=email placeholder='you@email.com' required aria-label=email>"
            "<button>Get early access</button></form></section>"
            "<ul>%s</ul></body></html>"
            % (html.escape(name), html.escape(name), html.escape(tagline), feat))
    open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8").write(page)
    return {"name": name, "features": len(features), "files": ["index.html"]}


def rubric(scope):
    def has_index(o, c):
        return os.path.exists(os.path.join(o, "index.html")), "index.html present"

    def has_signup(o, c):
        t = _slurp(o, "index.html")
        return ("<form" in t and "email" in t), "signup form present"

    def name_shown(o, c):
        return html.escape(c.get("name", "")) in _slurp(o, "index.html"), "name in the hero"

    return [("has-index", has_index), ("has-signup", has_signup), ("name-shown", name_shown)]


grade_context = name_context("name", "Your Product")


