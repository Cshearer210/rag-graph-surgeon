#!/usr/bin/env python3
"""Render the live demo output into a crisp terminal-card SVG for the README -- in pure Python, no
external recorder, no network, no paid service, so it can never rot and regenerates from a clone.

    python3 tools/render_demo_svg.py            # writes assets/demo.svg from a live demo run

It runs the real demo and draws what it prints, so the image cannot drift from the tool. GitHub
sanitises SVG animation in READMEs, so this is a STATIC card on purpose -- it renders everywhere.
"""
from __future__ import annotations

import html
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ragghost.demo import main as demo_main   # noqa: E402

_BG, _FG, _DIM, _GREEN, _RED, _YELLOW = "#0d1117", "#c9d1d9", "#8b949e", "#3fb950", "#f85149", "#d29922"
_CH_W, _LINE_H, _PAD, _TOP = 8.0, 19.0, 22, 52


def _colour(line):
    s = line.strip()
    if s.startswith(("GRAPH", "ORGANIZE", "HARNESS", "PLAN", "ANALYSE", "FIX", "SCAN", "RETRIEVE")):
        return _GREEN
    if "->" in line and ("orphan" in line or "dangling" in line or "misfiled" in line or "ungated" in line):
        return _FG
    if line.startswith("rag-ghost demo") or set(line.strip()) == {"="}:
        return _YELLOW
    if "moved-ref" in line or "no-gate" in line or "orphan " in line:
        return _RED
    if line.startswith("Exit codes") or line.startswith("Point it"):
        return _DIM
    return _FG


def render():
    buf = io.StringIO()
    _orig = sys.stdout
    sys.stdout = buf
    try:
        demo_main([])
    finally:
        sys.stdout = _orig
    lines = buf.getvalue().rstrip("\n").splitlines()
    width = max(64, max((len(l) for l in lines), default=64))
    W = int(_PAD * 2 + width * _CH_W)
    H = int(_TOP + len(lines) * _LINE_H + _PAD)
    out = []
    out.append('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
               'viewBox="0 0 %d %d" font-family="SFMono-Regular,Consolas,Liberation Mono,Menlo,monospace" '
               'font-size="13">' % (W, H, W, H))
    out.append('<rect width="%d" height="%d" rx="8" fill="%s"/>' % (W, H, _BG))
    out.append('<rect width="%d" height="34" rx="8" fill="#161b22"/>' % W)
    out.append('<rect y="26" width="%d" height="8" fill="#161b22"/>' % W)
    for i, c in enumerate(("#ff5f56", "#ffbd2e", "#27c93f")):
        out.append('<circle cx="%d" cy="17" r="6" fill="%s"/>' % (20 + i * 20, c))
    out.append('<text x="%d" y="21" fill="%s" font-size="12">python3 -m ragghost demo</text>'
               % (W // 2 - 90, _DIM))
    for i, line in enumerate(lines):
        y = _TOP + i * _LINE_H
        out.append('<text x="%d" y="%d" fill="%s" xml:space="preserve">%s</text>'
                   % (_PAD, y, _colour(line), html.escape(line)))
    out.append('</svg>')
    svg = "\n".join(out) + "\n"
    dest = os.path.join(ROOT, "assets", "demo.svg")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "w", encoding="utf-8") as f:
        f.write(svg)
    print("wrote", os.path.relpath(dest, ROOT), "(%d lines, %dx%d)" % (len(lines), W, H))


if __name__ == "__main__":
    render()
