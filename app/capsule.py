"""Capsule: the light dashboard video theme specified in docs/TEMA.md.

Warm grey panel inside a charcoal frame, pill chips, a red-to-green timeline
with a lime node, rounded cards and a dark caption capsule. Every visible
phrase still comes verbatim from the script; chart waves are decoration only.
"""
from __future__ import annotations

import math

from . import presenter

FRAME, PANEL, PANEL_DEEP, CARD = "3C3D3F", "E8E7E2", "D3D1CA", "F6F5F1"
INK, INK_SOFT, LIME = "2B2C2E", "77787A", "D9F23A"
SIGNAL_RED, SIGNAL_GREEN = "E8735A", "9CCB5A"

LABELS = {"hook": "Gündem", "editorial": "Odak", "card": "Gündemde", "statement": "Yakın plan"}
# Host placements tuned for this layout; the PiP badge matches presenter's mask.
PLACEMENTS = {"big": (180.0, 486.0, .88), "pip": (520.0, 704.0, .42)}
PIP_CIRCLE = (604.0, 822.0, 100.0)
TIMELINE_Y = 236


def _wave(width: int, base: float, amplitude: float, period: float, phase: float, bottom: float) -> str:
    points = [(x, base + amplitude * math.sin(x / period + phase)) for x in range(0, width + 1, 20)]
    path = f"m 0 {bottom:.0f} l " + " ".join(f"{x} {y:.1f}" for x, y in points)
    return path + f" {width} {bottom:.0f}"


def events(title: str, segments, scenes: list[dict], duration: float, host: dict | None) -> list[str]:
    from .media import _ass_escape, _ass_rgb, _fit_display, _glyph_width, _round_rect, _timestamp

    out: list[str] = []

    def event(start, end, layer, tags, content):
        out.append(f"Dialogue: {layer},{_timestamp(start, True)},{_timestamp(end, True)},Motion,,0,0,0,,{{{tags}}}{content}")

    def shape(start, end, layer, path, color, placement=r"\pos(0,0)", extra="", alpha="00"):
        event(start, end, layer, rf"\an7\bord0\shad0\1c{_ass_rgb(color)}\1a&H{alpha}&{placement}{extra}\p1", path + r"{\p0}")

    def text(start, end, content, x, y, size, color=INK, align=7, extra="", layer=6, bold=False):
        event(start, end, layer, rf"\an{align}\pos({x},{y})\fs{size}\1c{_ass_rgb(color)}\bord0\shad0\b{int(bold)}{extra}",
              _ass_escape(content))

    def width_of(content: str, size: int) -> int:
        return round(sum(map(_glyph_width, content)) * size)

    def disc(cx, cy, r, color, start, end, layer, extra="", alpha="00"):
        # Centered on its own origin so \fscx/\fscy pop around the center.
        shape(start, end, layer, presenter.screen_circle(0, 0, r), color, rf"\pos({cx},{cy})", extra, alpha)

    # --- the fixed chassis --------------------------------------------------------
    shape(0, duration, 0, "m 0 0 l 720 0 720 1280 0 1280", FRAME)
    shape(0, duration, 0, _round_rect(684, 1112, 44), PANEL, r"\pos(18,150)")
    shape(0, duration, 0, _round_rect(372, 200, 44), PANEL, r"\pos(18,18)")
    shape(0, duration, 0, "m 390 104 l 390 150 l 436 150 b 411 150 390 129 390 104", PANEL)
    disc(74, 84, 30, "FFFFFF", 0, duration, 1)
    shape(0, duration, 2, "m 78 66 l 64 88 l 74 88 l 69 104 l 86 80 l 76 80 l 82 66", INK)
    text(0, duration, "Hype", 120, 50, 46, INK)
    text(0, duration, "Teknoloji gündemi", 122, 104, 17, INK_SOFT)
    shape(0, duration, 1, "m 18 0 l 360 0 360 2 18 2", SIGNAL_RED, rf"\pos(0,{TIMELINE_Y - 1})", alpha="40")
    shape(0, duration, 1, "m 360 0 l 702 0 702 2 360 2", SIGNAL_GREEN, rf"\pos(0,{TIMELINE_Y - 1})", alpha="40")
    disc(640, TIMELINE_Y, 30, INK, 0, duration, 2)
    shape(0, duration, 3, "m -10 -1.5 l 10 -1.5 10 1.5 -10 1.5 m -1.5 -10 l 1.5 -10 1.5 10 -1.5 10",
          "FFFFFF", rf"\pos(640,{TIMELINE_Y})")
    # Bottom timeline bar doubles as the progress indicator.
    shape(0, duration, 1, _round_rect(640, 66, 33), "FFFFFF", r"\pos(40,1158)")
    disc(80, 1191, 26, INK, 0, duration, 2)
    shape(0, duration, 3, _round_rect(18, 16, 4), LIME, r"\pos(71,1183)")
    count = len(scenes)
    dots = [round(150 + (630 - 150) * (i + .5) / count) for i in range(count)]
    for x in dots:
        disc(x, 1191, 6, PANEL_DEEP, 0, duration, 2)

    big_name = presenter.display_name(host["name"]) if host else ""
    for index, scene in enumerate(scenes):
        start, end = scene["start"], scene["end"]
        milliseconds = max(1, round((end - start) * 1000))
        layout = scene["layout"]
        last = index == count - 1
        label = ("Son söz" if last else "Ara sahne") if layout == "host" else LABELS.get(layout, "Gündem")

        # Header chips: the active scene label, then the counter.
        chip = width_of(label, 18) + 44
        shape(start, end, 1, _round_rect(chip, 52, 26), CARD, r"\pos(408,49)", r"\fad(120,0)")
        text(start, end, label, 408 + chip // 2, 75, 18, INK, 5, r"\fad(120,0)", layer=2)
        counter = f"{index + 1:02d} / {count:02d}"
        shape(start, end, 1, _round_rect(104, 52, 26), "57585B", rf"\pos({416 + chip},49)")
        text(start, end, counter, 468 + chip, 75, 17, "FFFFFF", 5, layer=2)

        # Timeline node pops in and the line draws across.
        disc(96, TIMELINE_Y, 32, LIME, start, end, 2, r"\fscx0\fscy0\t(0,260,\fscx112\fscy112)\t(260,380,\fscx100\fscy100)")
        shape(start, end, 3, "m -9 -9 l 9 -9 9 -5 -9 -5 m -9 -2 l 9 -2 9 2 -9 2 m -9 5 l 4 5 4 9 -9 9", INK,
              rf"\pos(96,{TIMELINE_Y})", r"\fad(200,0)")
        shape(start, end, 1, "m 0 0 l 512 0 512 3 0 3", INK, rf"\pos(128,{TIMELINE_Y - 1})",
              r"\fscx0\t(0,520,\fscx100)", "90")
        # Active segment in the bottom bar.
        shape(start, end, 2, _round_rect(64, 44, 22), INK, rf"\pos({dots[index] - 32},1169)", r"\fad(100,0)")
        disc(dots[index], 1191, 7, LIME, start, end, 3, r"\fscx0\fscy0\t(0,220,\fscx100\fscy100)")
        for past in dots[:index]:
            disc(past, 1191, 6, INK, start, end, 3, alpha="40")

        if host and scene.get("host") == "big":
            shape(start, end, 1, _round_rect(640, 430, 40), PANEL_DEEP, r"\move(40,540,40,500,0,360)", r"\fad(120,0)")
            disc(360, 690, 170, LIME, start, end, 1, r"\fscx60\fscy60\t(0,420,\fscx100\fscy100)\fad(120,0)", "70")
            tag = width_of(big_name, 22) + 64
            shape(start, end, 5, _round_rect(tag, 46, 23), INK, r"\move(-220,866,52,866,0,320)")
            disc(78, 889, 7, LIME, start, end, 5, r"\move(-194,889,78,889,0,320)")
            text(start, end, big_name, 96, 877, 22, "FFFFFF", extra=r"\move(-176,877,96,877,0,320)", layer=5)
        elif host:
            cx, cy, radius = PIP_CIRCLE
            disc(cx, cy, radius, INK, start, end, 3, r"\fscx0\fscy0\t(0,260,\fscx100\fscy100)")
            ring = presenter.screen_circle(cx, cy, radius - 4) + " " + presenter.screen_circle(cx, cy, radius - 10, reverse=True)
            shape(start, end, 5, ring, LIME, extra=r"\fad(220,0)")
            name = presenter.display_name(host["name"])
            tag = width_of(name, 16) + 30
            shape(start, end, 5, _round_rect(tag, 30, 15), LIME, rf"\pos({round(cx - tag / 2)},{round(cy + radius - 20)})",
                  r"\fad(220,0)")
            text(start, end, name, round(cx), round(cy + radius - 5), 16, INK, 5, r"\fad(220,0)", layer=5, bold=True)

        if layout == "hook":
            text(start, end, "Bugünün konusu", 62, 274, 19, INK_SOFT, extra=r"\fad(120,0)")
            size, fitted = _fit_display(title, sizes=(62, 56, 50, 44, 40, 36), width=600, lines=4,
                                        height=190 if host else 520)
            height = round(size * 1.12)
            for number, line in enumerate(fitted.splitlines()):
                y = 308 + number * height
                event(start + min(.1 * number, (end - start) * .15), end, 6,
                      rf"\an7\move(62,{y + 34},62,{y},0,380)\fs{size}\1c{_ass_rgb(INK)}\bord0\shad0\b0\fad(160,120)",
                      _ass_escape(line))
        elif layout == "host":
            size, fitted = _fit_display(scene["phrase"], sizes=(50, 46, 42, 38, 34, 30), width=548, lines=5, height=170)
            box = len(fitted.splitlines()) * round(size * 1.18) + 96
            top = 268
            shape(start, end, 6, _round_rect(640, box, 36), CARD, rf"\move(40,{top + 40},40,{top},0,320)", r"\fad(100,120)")
            shape(start, end, 6, f"m 300 {top + box - 2} l 364 {top + box - 2} l 318 {top + box + 46}", CARD,
                  r"\move(0,40,0,0,0,320)", r"\fad(100,120)")
            chip = width_of(label, 16) + 36
            shape(start + .06, end, 6, _round_rect(chip, 32, 16), INK, rf"\pos(76,{top + 26})", r"\fad(120,120)")
            text(start + .06, end, label, 76 + chip // 2, top + 42, 16, "FFFFFF", 5, r"\fad(120,120)")
            event(start + .1, end, 6, rf"\an7\move(76,{top + 104},76,{top + 74},0,340)\fs{size}\1c{_ass_rgb(INK)}\bord0\shad0\b0\fad(120,120)",
                  _ass_escape(fitted))
        elif layout == "editorial":
            shape(start, end, 1, "m 0 0 l 2 0 2 36 0 36", INK, rf"\pos(95,{TIMELINE_Y + 30})", alpha="40")
            shape(start, end, 3, _round_rect(640, 410, 36), CARD, r"\move(40,346,40,300,0,320)", r"\fad(100,120)")
            text(start, end, "Odak noktası", 76, 332, 18, INK_SOFT, extra=r"\move(76,378,76,332,0,320)\fad(100,120)")
            disc(632, 348, 26, "FFFFFF", start, end, 4, r"\fad(160,120)")
            disc(632, 348, 8, LIME, start, end, 4, r"\fad(200,120)")
            size, fitted = _fit_display(scene["phrase"], sizes=(52, 46, 42, 38, 34, 30), width=560, lines=5, height=230)
            event(start + .08, end, 6, rf"\an7\move(76,{410},76,{380},0,340)\fs{size}\1c{_ass_rgb(INK)}\bord0\shad0\b0\fad(120,120)",
                  _ass_escape(fitted))
            clip = r"\clip(40,610,680,710)"
            shape(start, end, 4, _wave(1400, 630, 16, 60, 0, 700), LIME,
                  rf"\move(-680,0,0,0,0,{milliseconds})", clip + r"\fad(200,120)")
            shape(start, end, 4, _wave(1400, 656, 12, 44, 1.3, 700), "A9A7A0",
                  rf"\move(0,0,-640,0,0,{milliseconds})", clip + r"\fad(200,120)", "40")
        elif layout == "card":
            shape(start, end, 3, _round_rect(300, 64, 32), INK, r"\move(-260,290,40,290,0,320)")
            disc(72, 322, 24, "FFFFFF", start, end, 4, r"\move(-228,322,72,322,0,320)")
            shape(start, end, 5, _round_rect(22, 10, 5), INK, r"\move(-239,317,61,317,0,320)", r"\frz35")
            text(start, end, "Gündemde", 112, 308, 20, "FFFFFF", extra=r"\move(-188,308,112,308,0,320)", layer=5)
            shape(start, end, 1, "m 0 0 l 2 0 2 34 0 34", INK, r"\pos(190,354)", alpha="40")
            shape(start, end, 3, _round_rect(640, 330, 36), CARD, r"\move(40,430,40,388,0,320)", r"\fad(100,120)")
            size, fitted = _fit_display(scene["phrase"], sizes=(52, 46, 42, 38, 34, 30), width=560, lines=5, height=250)
            event(start + .1, end, 6, rf"\an5\move(360,583,360,553,0,340)\fs{size}\1c{_ass_rgb(INK)}\bord0\shad0\b0\fad(120,120)",
                  _ass_escape(fitted))
        else:
            text(start, end, "Yakın plan", 62, 274, 19, INK_SOFT, extra=r"\fad(120,0)")
            size, fitted = _fit_display(scene["phrase"], sizes=(60, 54, 48, 44, 40, 36), width=600, lines=6, height=380)
            first = fitted.splitlines()[0] if fitted else ""
            shape(start + .36, end, 5, _round_rect(round(width_of(first, size) * 1.1) + 24, round(size * .42), 6), LIME,
                  rf"\pos(50,{316 + round(size * .66)})", r"\fscx0\t(0,440,\fscx100)")
            event(start, end, 6, rf"\an7\move(62,{340},62,{316},0,360)\fs{size}\1c{_ass_rgb(INK)}\bord0\shad0\b0\fad(120,120)",
                  _ass_escape(fitted))

        if index:
            # Panel-coloured shutter and a lime scan line cover each cut.
            shape(max(0, start - .16), min(duration, start + .16), 6, "m 18 262 l 702 262 702 930 18 930", PANEL,
                  extra=r"\fad(140,140)")
            shape(max(0, start - .18), min(duration, start + .24), 6, _round_rect(684, 12, 6), LIME,
                  r"\move(18,262,18,920,0,420)")

    # Captions: bold white on the dark capsule, tied to the narration timings.
    shape(0, duration, 7, _round_rect(640, 178, 36), INK, r"\pos(40,936)")
    for start, end, caption in segments:
        event(start, end, 9,
              r"\an2\pos(360,1084)\fs44\1c&HFFFFFF&\bord0\shad0\b1\fscx97\fscy97\t(0,100,\fscx100\fscy100)\fad(0,35)",
              _ass_escape(caption))
    if host:
        out.extend(presenter.puppet_events(
            look_id=host["look"], accent_for=lambda _index: LIME, spans=host["spans"], scenes=scenes,
            duration=duration, levels=host.get("levels"), seed=title, layer=4,
            placements=PLACEMENTS, pip_circle=PIP_CIRCLE))
    return out
