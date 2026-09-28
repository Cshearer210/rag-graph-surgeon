# CALLED BY: ragghost/surgeon/builders/__init__.py (BUILDERS registry) -> road.py (build stage); tested by tests/test_surgeon_modules.py
"""Build an operations dashboard -- a THIRD fully-built output type, so "ships a variety" is
demonstrated with three real builders rather than asserted. Reads config.json for the title and
any JSON data files in the system (products.json, metrics.json, orders.json, ...) and renders KPI
cards plus a table of the first data set it finds. Static HTML, no dependencies.
"""
from __future__ import annotations

import html
import os

from .._common import load as _load, name_context, slurp as _slurp

_DATA_CANDIDATES = ["metrics.json", "products.json", "orders.json", "data.json", "items.json"]






def _first_dataset(ws):
    """Return (name, list-of-rows) for the first readable JSON collection found, or (None, [])."""
    for cand in _DATA_CANDIDATES:
        data = _load(ws, cand, None)
        rows = None
        if isinstance(data, list):
            rows = data
        elif isinstance(data, dict):
            # a dict whose first list value is the collection (e.g. {"products": [...]})
            for v in data.values():
                if isinstance(v, list):
                    rows = v
                    break
        if rows:
            return cand.replace(".json", ""), [r for r in rows if isinstance(r, dict)]
    return None, []


def _cards(rows, name):
    cards = [("Records", len(rows))]
    if rows:
        # a numeric column becomes a summed KPI; a price/total column is the obvious one
        keys = rows[0].keys()
        for k in keys:
            vals = [r.get(k) for r in rows if isinstance(r.get(k), (int, float))]
            if vals and any(w in k.lower() for w in ("price", "total", "amount", "qty", "count", "stock")):
                s = sum(vals)
                cards.append((("Total " + k).title(), round(s, 2)))
                if len(cards) >= 4:
                    break
    return cards


def build(ws: str, scope, out_dir: str) -> dict:
    cfg = _load(ws, "config.json", {})
    title = cfg.get("store_name") or scope.get("store_name") or "Operations Dashboard"
    name, rows = _first_dataset(ws)
    cards = _cards(rows, name or "records")
    os.makedirs(out_dir, exist_ok=True)

    card_html = "".join(
        "<div class=card><div class=n>%s</div><div class=k>%s</div></div>" % (html.escape(str(v)), html.escape(str(k)))
        for k, v in cards)

    thead = tbody = ""
    if rows:
        cols = list(rows[0].keys())[:6]
        thead = "".join("<th>%s</th>" % html.escape(str(c)) for c in cols)
        for r in rows[:50]:
            tbody += "<tr>%s</tr>" % "".join("<td>%s</td>" % html.escape(str(r.get(c, ""))) for c in cols)

    page = ("<!doctype html><html lang=en><head><meta charset=utf-8>"
            "<meta name=viewport content='width=device-width,initial-scale=1'>"
            "<title>%s</title><style>"
            "body{font:15px/1.5 system-ui;margin:0;background:#0b1220;color:#e5e7eb}"
            "header{padding:20px 28px;background:#111827;font-size:1.4rem;font-weight:700}"
            ".cards{display:flex;gap:16px;flex-wrap:wrap;padding:24px 28px}"
            ".card{background:#1f2937;border-radius:12px;padding:18px 22px;min-width:140px}"
            ".card .n{font-size:2rem;font-weight:700;color:#60a5fa}.card .k{color:#9ca3af;font-size:.85rem}"
            "table{width:calc(100%% - 56px);margin:0 28px 28px;border-collapse:collapse;background:#111827;border-radius:10px;overflow:hidden}"
            "th,td{padding:10px 14px;text-align:left;border-bottom:1px solid #1f2937;font-size:.9rem}"
            "th{background:#0f172a;color:#93c5fd}tr:hover td{background:#0f172a}"
            "</style></head><body><header>%s</header>"
            "<div class=cards>%s</div>%s</body></html>"
            % (html.escape(title), html.escape(title), card_html,
               ("<table><thead><tr>%s</tr></thead><tbody>%s</tbody></table>" % (thead, tbody)) if rows
               else "<p style='padding:0 28px;color:#9ca3af'>No data set found to chart yet.</p>"))
    open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8").write(page)
    return {"title": title, "dataset": name, "rows": len(rows), "cards": len(cards), "files": ["index.html"]}


def rubric(scope):
    def has_index(o, c):
        return os.path.exists(os.path.join(o, "index.html")), "index.html present"

    def has_cards(o, c):
        return "class=card" in _slurp(o, "index.html"), "at least one KPI card rendered"

    def title_shown(o, c):
        return html.escape(c.get("title", "")) in _slurp(o, "index.html"), "title in the header"

    return [("has-index", has_index), ("has-cards", has_cards), ("title-shown", title_shown)]


grade_context = name_context("title", "Operations Dashboard")


