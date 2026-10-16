"""Capsule: the light dashboard video theme specified in docs/TEMA.md.

Rendered as two layers so the camera can move without shaking the interface:

* ``world`` - the panel content, timeline, cards and presenter. It is drawn on
  a 1.2x canvas and FFmpeg's zoompan moves a virtual camera over it (punch-ins
  on cuts, slow pushes, drifts), a classic retention "pattern interrupt";
* ``hud`` - the charcoal frame, tab, chips, caption capsule and the bottom
  scene bar, which stay still so the viewer always has a fixed anchor.

Every visible phrase still comes verbatim from the script; chart waves are
decoration only.
"""
from __future__ import annotations

import math
import re

from . import presenter

FRAME, PANEL, PANEL_DEEP, CARD = "3C3D3F", "E8E7E2", "D3D1CA", "F6F5F1"
INK, INK_SOFT, LIME = "2B2C2E", "77787A", "D9F23A"
SIGNAL_RED, SIGNAL_GREEN = "E8735A", "9CCB5A"

LABELS = {"hook": "Gündem", "editorial": "Odak", "card": "Gündemde", "statement": "Yakın plan",
          "keyword": "Anahtar kelime", "quote": "Senaryodan", "split": "Adım adım"}
# Host placements tuned for this layout; the PiP badge matches presenter's mask.
PLACEMENTS = {"big": (180.0, 486.0, .88), "pip": (504.0, 676.0, .42)}
PIP_CIRCLE = (588.0, 794.0, 96.0)
TIMELINE_Y = 236
CANVAS_SCALE = 1.2  # World layer canvas relative to the 720x1280 output.

# Camera move per layout: (kind, focus x, focus y) in output coordinates.
CAMERA = {"hook": ("face", 360, 690), "host": ("face", 360, 690), "keyword": ("punch", 360, 540),
          "editorial": ("push", 360, 480), "card": ("pull", 360, 540), "quote": ("drift", 360, 520),
          "split": ("tilt", 360, 420), "statement": ("push", 300, 450)}


def _wave(width: int, base: float, amplitude: float, period: float, phase: float, bottom: float) -> str:
    points = [(x, base + amplitude * math.sin(x / period + phase)) for x in range(0, width + 1, 20)]
    path = f"m 0 {bottom:.0f} l " + " ".join(f"{x} {y:.1f}" for x, y in points)
    return path + f" {width} {bottom:.0f}"


def _round_rect_reversed(x: int, y: int, w: int, h: int, r: int) -> str:
    """Counter-clockwise rounded rectangle, used to punch a hole into the frame."""
    return (f"m {x + r} {y} b {x} {y} {x} {y} {x} {y + r} l {x} {y + h - r} b {x} {y + h} {x} {y + h} {x + r} {y + h} "
            f"l {x + w - r} {y + h} b {x + w} {y + h} {x + w} {y + h} {x + w} {y + h - r} l {x + w} {y + r} "
            f"b {x + w} {y} {x + w} {y} {x + w - r} {y} l {x + r} {y}")


def keyword_size(word: str) -> int:
    from .media import _glyph_width
    # Fits inside the frame even at the punch-in's peak zoom.
    return max(40, min(112, round(470 / max(1.0, sum(map(_glyph_width, word))))))


def keyword_pill(word: str) -> tuple[int, int]:
    from .media import _glyph_width
    size = keyword_size(word)
    return round(sum(map(_glyph_width, word)) * size) + 64, round(size * 1.3)


def perches(scenes: list[dict]) -> list[dict]:
    """Where a roaming host lands in each scene: (time, feet x, feet y, scale).

    The bird sits on the interface itself - the caption ledge, the "Gündemde"
    pill, the keyword, the quote mark, the "+" button - so every cut gives the
    eye one moving, living thing to follow.
    """
    planned = []
    for scene in scenes:
        scene = dict(scene)
        start, end, layout = scene["start"], scene["end"], scene["layout"]
        if layout in ("hook", "host"):
            spots = [(start, 360.0, 934.0, .56 if layout == "hook" else .52)]
        elif layout == "card":
            spots = [(start, 292.0, 290.0, .24)]
        elif layout == "keyword":
            width, height = keyword_pill(keyword(scene["phrase"]))
            spots = [(start, 360.0 + width / 2 - 60, 520.0 - height / 2, .25)]
        elif layout == "quote":
            spots = [(start, 102.0, 278.0, .22)]
        elif layout == "split":
            spots = [(start, 590.0, 290.0, .24), (start + (end - start) * .45, 590.0, 500.0, .24)]
        elif layout == "statement":
            spots = [(start, 640.0, 206.0, .22)]
        else:
            spots = [(start, 600.0, 934.0, .3)]
        scene["perch"] = spots
        planned.append(scene)
    return planned


def keyword(phrase: str) -> str:
    """The longest verbatim word of a phrase, trimmed of surrounding punctuation."""
    words = [word.strip(".,;:!?…\"'“”‘’()[]") for word in phrase.split()]
    return max((word for word in words if word), key=len, default=phrase.strip())


def camera(scenes: list[dict], duration: float) -> tuple[str, str, str]:
    """zoompan expressions (z, x, y) giving each scene its own camera move."""
    def piecewise(build) -> str:
        expression = build(scenes[-1])
        for scene in reversed(scenes[:-1]):
            expression = f"if(lt(it,{scene['end']:.3f}),{build(scene)},{expression})"
        return expression

    def zoom(scene) -> str:
        start, length = scene["start"], max(.1, scene["end"] - scene["start"])
        u = f"(it-{start:.3f})"
        kind = CAMERA.get(scene["layout"], ("push", 360, 480))[0]
        if scene.get("perch") and kind not in ("face", "punch"):
            # Push in on the landing bird, then let the shot breathe.
            return f"1.03+0.12*exp(-abs({u}-0.6)*4)+0.03*{u}/{length:.3f}"
        if kind == "face":
            return f"1.02+0.10*exp(-{u}*6)+0.04*{u}/{length:.3f}"
        if kind == "punch":
            return f"1.02+0.16*exp(-{u}*7)+0.05*{u}/{length:.3f}"
        if kind == "pull":
            return f"1.09-0.08*{u}/{length:.3f}"
        if kind in ("drift", "tilt"):
            return "1.06"
        return f"1.01+0.07*{u}/{length:.3f}"

    def focus(axis: int):
        def build(scene) -> str:
            kind, fx, fy = CAMERA.get(scene["layout"], ("push", 360, 480))
            value = (fx, fy)[axis] * CANVAS_SCALE
            start, length = scene["start"], max(.1, scene["end"] - scene["start"])
            u = f"(it-{start:.3f})/{length:.3f}"
            if kind == "drift" and axis == 0:
                return f"{(fx - 40) * CANVAS_SCALE:.1f}+{80 * CANVAS_SCALE:.1f}*{u}"
            if kind == "tilt" and axis == 1:
                return f"{fy * CANVAS_SCALE:.1f}+{200 * CANVAS_SCALE:.1f}*min(1,{u}*1.6)"
            if scene.get("perch"):
                _at, px, py, ps = scene["perch"][0]
                bird = (px, py - 300 * ps)[axis] * CANVAS_SCALE
                # Start on the bird, then drift towards the scene's content.
                return f"({value:.1f}+({bird - value:.1f})*exp(-max(0,{u}*{length:.3f}-0.4)*1.3))"
            return f"{value:.1f}"
        return build

    z = piecewise(zoom)
    x = f"max(0,min(iw-iw/zoom,({piecewise(focus(0))})-iw/zoom/2))"
    y = f"max(0,min(ih-ih/zoom,({piecewise(focus(1))})-ih/zoom/2))"
    return z, x, y


def sfx_cues(scenes: list[dict]) -> tuple[list[float], list[float]]:
    """Whooshes on every cut, pops when a keyword lands or a second card appears."""
    whooshes = [scene["start"] for scene in scenes[1:]]
    pops = []
    for scene in scenes:
        if scene["layout"] == "keyword":
            pops.append(scene["start"] + .12)
        elif scene["layout"] == "split":
            pops.append(scene["start"] + (scene["end"] - scene["start"]) * .45)
    return whooshes, pops


def events(title: str, segments, scenes: list[dict], duration: float,
           host: dict | None) -> tuple[list[str], list[str]]:
    from .media import _ass_escape, _ass_rgb, _fit_display, _glyph_width, _round_rect, _timestamp

    world: list[str] = []
    hud: list[str] = []

    def event(target, start, end, layer, tags, content):
        target.append(f"Dialogue: {layer},{_timestamp(start, True)},{_timestamp(end, True)},Motion,,0,0,0,,{{{tags}}}{content}")

    def shape(target, start, end, layer, path, color, placement=r"\pos(0,0)", extra="", alpha="00"):
        event(target, start, end, layer, rf"\an7\bord0\shad0\1c{_ass_rgb(color)}\1a&H{alpha}&{placement}{extra}\p1",
              path + r"{\p0}")

    def text(target, start, end, content, x, y, size, color=INK, align=7, extra="", layer=6, bold=False):
        event(target, start, end, layer,
              rf"\an{align}\pos({x},{y})\fs{size}\1c{_ass_rgb(color)}\bord0\shad0\b{int(bold)}{extra}",
              _ass_escape(content))

    def width_of(content: str, size: float) -> int:
        return round(sum(map(_glyph_width, content)) * size)

    def disc(target, cx, cy, r, color, start, end, layer, extra="", alpha="00"):
        # Centered on its own origin so \fscx/\fscy pop around the center.
        shape(target, start, end, layer, presenter.screen_circle(0, 0, r), color, rf"\pos({cx},{cy})", extra, alpha)

    def lines_in(target, start, end, fitted, size, x, y, color=INK, extra="", align=7, layer=6):
        event(target, start, end, layer,
              rf"\an{align}\move({x},{y + 30},{x},{y},0,340)\fs{size}\1c{_ass_rgb(color)}\bord0\shad0\b0\fad(120,120){extra}",
              _ass_escape(fitted))

    # --- HUD chassis: frame with a window onto the moving world ------------------------
    shape(hud, 0, duration, 0, "m 0 0 l 720 0 720 1280 0 1280 " + _round_rect_reversed(18, 150, 684, 1112, 44), FRAME)
    # The tab merges into the window's rounded top-left corner.
    shape(hud, 0, duration, 0, _round_rect(372, 132, 44) + " m 0 62 l 372 62 372 176 0 176", PANEL, r"\pos(18,18)")
    shape(hud, 0, duration, 0, "m 390 104 l 390 150 l 436 150 b 411 150 390 129 390 104", PANEL)
    disc(hud, 74, 84, 30, "FFFFFF", 0, duration, 1)
    shape(hud, 0, duration, 2, "m 78 66 l 64 88 l 74 88 l 69 104 l 86 80 l 76 80 l 82 66", INK)
    text(hud, 0, duration, "Hype", 120, 50, 46, INK)
    text(hud, 0, duration, "Teknoloji gündemi", 122, 104, 17, INK_SOFT)
    shape(hud, 0, duration, 1, _round_rect(640, 66, 33), "FFFFFF", r"\pos(40,1158)")
    disc(hud, 80, 1191, 26, INK, 0, duration, 2)
    shape(hud, 0, duration, 3, _round_rect(18, 16, 4), LIME, r"\pos(71,1183)")
    count = len(scenes)
    dots = [round(150 + (630 - 150) * (i + .5) / count) for i in range(count)]
    for x in dots:
        disc(hud, x, 1191, 6, PANEL_DEEP, 0, duration, 2)
    shape(hud, 0, duration, 4, _round_rect(640, 178, 36), INK, r"\pos(40,936)")

    # --- World backdrop: a faint grid makes every camera move readable -----------------
    shape(world, 0, duration, 0, "m -100 -100 l 820 -100 820 1380 -100 1380", PANEL)
    grid = " ".join(f"m {x} 0 l {x + 1} 0 {x + 1} 1280 {x} 1280" for x in range(40, 720, 80))
    grid += " " + " ".join(f"m 0 {y} l 720 {y} 720 {y + 1} 0 {y + 1}" for y in range(300, 1280, 80))
    shape(world, 0, duration, 0, grid, INK, alpha="F0")
    shape(world, 0, duration, 1, "m 0 0 l 360 0 360 2 0 2", SIGNAL_RED, rf"\pos(0,{TIMELINE_Y - 1})", alpha="40")
    shape(world, 0, duration, 1, "m 360 0 l 720 0 720 2 360 2", SIGNAL_GREEN, rf"\pos(0,{TIMELINE_Y - 1})", alpha="40")
    disc(world, 640, TIMELINE_Y, 30, INK, 0, duration, 2)
    shape(world, 0, duration, 3, "m -10 -1.5 l 10 -1.5 10 1.5 -10 1.5 m -1.5 -10 l 1.5 -10 1.5 10 -1.5 10",
          "FFFFFF", rf"\pos(640,{TIMELINE_Y})")

    big_name = presenter.display_name(host["name"]) if host else ""
    for index, scene in enumerate(scenes):
        start, end = scene["start"], scene["end"]
        milliseconds = max(1, round((end - start) * 1000))
        layout = scene["layout"]
        last = index == count - 1
        label = ("Son söz" if last else "Ara sahne") if layout == "host" else LABELS.get(layout, "Gündem")

        # HUD: active chip, counter and bottom-bar position.
        chip = width_of(label, 18) + 44
        shape(hud, start, end, 1, _round_rect(chip, 52, 26), CARD, r"\pos(408,49)", r"\fad(120,0)")
        text(hud, start, end, label, 408 + chip // 2, 75, 18, INK, 5, r"\fad(120,0)", layer=2)
        shape(hud, start, end, 1, _round_rect(104, 52, 26), "57585B", rf"\pos({416 + chip},49)")
        text(hud, start, end, f"{index + 1:02d} / {count:02d}", 468 + chip, 75, 17, "FFFFFF", 5, layer=2)
        shape(hud, start, end, 2, _round_rect(64, 44, 22), INK, rf"\pos({dots[index] - 32},1169)", r"\fad(100,0)")
        disc(hud, dots[index], 1191, 7, LIME, start, end, 3, r"\fscx0\fscy0\t(0,220,\fscx100\fscy100)")
        for past in dots[:index]:
            disc(hud, past, 1191, 6, INK, start, end, 3, alpha="40")

        # World: timeline node pops in and the line draws across.
        disc(world, 96, TIMELINE_Y, 32, LIME, start, end, 2,
             r"\fscx0\fscy0\t(0,260,\fscx112\fscy112)\t(260,380,\fscx100\fscy100)")
        shape(world, start, end, 3, "m -9 -9 l 9 -9 9 -5 -9 -5 m -9 -2 l 9 -2 9 2 -9 2 m -9 5 l 4 5 4 9 -9 9", INK,
              rf"\pos(96,{TIMELINE_Y})", r"\fad(200,0)")
        shape(world, start, end, 1, "m 0 0 l 512 0 512 3 0 3", INK, rf"\pos(128,{TIMELINE_Y - 1})",
              r"\fscx0\t(0,520,\fscx100)", "90")

        mode = scene.get("host")
        roaming = bool(host and scene.get("perch"))
        if host and mode == "big":
            shape(world, start, end, 1, _round_rect(640, 430, 40), PANEL_DEEP, r"\move(40,540,40,500,0,360)", r"\fad(120,0)")
            disc(world, 360, 690, 170, LIME, start, end, 1, r"\fscx60\fscy60\t(0,420,\fscx100\fscy100)\fad(120,0)", "70")
            tag = width_of(big_name, 22) + 64
            shape(world, start, end, 5, _round_rect(tag, 46, 23), INK, r"\move(-220,866,52,866,0,320)")
            disc(world, 78, 889, 7, LIME, start, end, 5, r"\move(-194,889,78,889,0,320)")
            text(world, start, end, big_name, 96, 877, 22, "FFFFFF", extra=r"\move(-176,877,96,877,0,320)", layer=5)
        elif host and mode == "pip" and not roaming:
            cx, cy, radius = PIP_CIRCLE
            disc(world, cx, cy, radius, INK, start, end, 3, r"\fscx0\fscy0\t(0,260,\fscx100\fscy100)")
            ring = presenter.screen_circle(cx, cy, radius - 4) + " " + presenter.screen_circle(cx, cy, radius - 10, reverse=True)
            shape(world, start, end, 5, ring, LIME, extra=r"\fad(220,0)")
            name = presenter.display_name(host["name"])
            tag = width_of(name, 16) + 30
            shape(world, start, end, 5, _round_rect(tag, 30, 15), LIME,
                  rf"\pos({round(cx - tag / 2)},{round(cy + radius - 20)})", r"\fad(220,0)")
            text(world, start, end, name, round(cx), round(cy + radius - 5), 16, INK, 5, r"\fad(220,0)", layer=5, bold=True)

        if layout == "hook":
            text(world, start, end, "Bugünün konusu", 62, 274, 19, INK_SOFT, extra=r"\fad(120,0)")
            size, fitted = _fit_display(title, sizes=(62, 56, 50, 44, 40, 36), width=600, lines=4,
                                        height=190 if host else 520)
            height = round(size * 1.12)
            for number, line in enumerate(fitted.splitlines()):
                y = 308 + number * height
                event(world, start + min(.1 * number, (end - start) * .15), end, 6,
                      rf"\an7\move(62,{y + 34},62,{y},0,380)\fs{size}\1c{_ass_rgb(INK)}\bord0\shad0\b0\fad(160,120)",
                      _ass_escape(line))
        elif layout == "host":
            size, fitted = _fit_display(scene["phrase"], sizes=(50, 46, 42, 38, 34, 30), width=548, lines=5, height=170)
            box = len(fitted.splitlines()) * round(size * 1.18) + 96
            top = 268
            shape(world, start, end, 6, _round_rect(640, box, 36), CARD, rf"\move(40,{top + 40},40,{top},0,320)", r"\fad(100,120)")
            shape(world, start, end, 6, f"m 300 {top + box - 2} l 364 {top + box - 2} l 318 {top + box + 46}", CARD,
                  r"\move(0,40,0,0,0,320)", r"\fad(100,120)")
            chip = width_of(label, 16) + 36
            shape(world, start + .06, end, 6, _round_rect(chip, 32, 16), INK, rf"\pos(76,{top + 26})", r"\fad(120,120)")
            text(world, start + .06, end, label, 76 + chip // 2, top + 42, 16, "FFFFFF", 5, r"\fad(120,120)")
            lines_in(world, start + .1, end, fitted, size, 76, top + 74)
        elif layout == "editorial":
            shape(world, start, end, 1, "m 0 0 l 2 0 2 36 0 36", INK, rf"\pos(95,{TIMELINE_Y + 30})", alpha="40")
            shape(world, start, end, 3, _round_rect(640, 410, 36), CARD, r"\move(40,346,40,300,0,320)", r"\fad(100,120)")
            text(world, start, end, "Odak noktası", 76, 332, 18, INK_SOFT, extra=r"\move(76,378,76,332,0,320)\fad(100,120)")
            disc(world, 632, 348, 26, "FFFFFF", start, end, 4, r"\fad(160,120)")
            disc(world, 632, 348, 8, LIME, start, end, 4, r"\fad(200,120)")
            size, fitted = _fit_display(scene["phrase"], sizes=(52, 46, 42, 38, 34, 30), width=560, lines=5, height=230)
            lines_in(world, start + .08, end, fitted, size, 76, 380)
            clip = r"\clip(40,610,680,710)"
            shape(world, start, end, 4, _wave(1400, 630, 16, 60, 0, 700), LIME,
                  rf"\move(-680,0,0,0,0,{milliseconds})", clip + r"\fad(200,120)")
            shape(world, start, end, 4, _wave(1400, 656, 12, 44, 1.3, 700), "A9A7A0",
                  rf"\move(0,0,-640,0,0,{milliseconds})", clip + r"\fad(200,120)", "40")
        elif layout == "card":
            shape(world, start, end, 3, _round_rect(300, 64, 32), INK, r"\move(-260,290,40,290,0,320)")
            disc(world, 72, 322, 24, "FFFFFF", start, end, 4, r"\move(-228,322,72,322,0,320)")
            shape(world, start, end, 5, _round_rect(22, 10, 5), INK, r"\move(-239,317,61,317,0,320)", r"\frz35")
            text(world, start, end, "Gündemde", 112, 308, 20, "FFFFFF", extra=r"\move(-188,308,112,308,0,320)", layer=5)
            shape(world, start, end, 1, "m 0 0 l 2 0 2 34 0 34", INK, r"\pos(190,354)", alpha="40")
            shape(world, start, end, 3, _round_rect(640, 330, 36), CARD, r"\move(40,430,40,388,0,320)", r"\fad(100,120)")
            size, fitted = _fit_display(scene["phrase"], sizes=(52, 46, 42, 38, 34, 30), width=560, lines=5, height=250)
            lines_in(world, start + .1, end, fitted, size, 360, 553, align=5)
        elif layout == "keyword":
            word = keyword(scene["phrase"])
            size = keyword_size(word)
            pill_w, pill_h = keyword_pill(word)
            text(world, start, end, "Anahtar kelime", 62, 300, 19, INK_SOFT, extra=r"\fad(120,0)")
            shape(world, start, end, 4,
                  _round_rect(pill_w, pill_h, pill_h // 2), LIME,
                  rf"\pos({360 - pill_w // 2},{520 - pill_h // 2})", r"\fscy0\t(0,180,\fscy100)")
            event(world, start + .06, end, 6,
                  rf"\an5\pos(360,520)\fs{size}\1c{_ass_rgb(INK)}\bord0\shad0\b1\fscx150\fscy150\t(0,200,\fscx100\fscy100)",
                  _ass_escape(word))
            small, context = _fit_display(scene["phrase"], sizes=(34, 30, 28, 26), width=600, lines=4, height=170)
            event(world, start + .35, end, 6,
                  rf"\an8\move(360,{720},360,{690},0,340)\fs{small}\1c{_ass_rgb(INK_SOFT)}\bord0\shad0\b0\fad(160,120)",
                  _ass_escape(context))
        elif layout == "quote":
            shape(world, start, end, 3, "m 0 30 b 0 10 14 0 30 0 l 30 22 b 20 22 16 30 18 40 l 34 40 l 34 74 l 0 74 "
                                        "m 46 30 b 46 10 60 0 76 0 l 76 22 b 66 22 62 30 64 40 l 80 40 l 80 74 l 46 74",
                  LIME, r"\move(62,300,62,276,0,300)", r"\fscx140\fscy140\t(0,260,\fscx100\fscy100)")
            shape(world, start, end, 3, "m 0 0 l 6 0 6 330 0 330", INK, r"\pos(62,380)", r"\fscy0\t(80,520,\fscy100)")
            size, fitted = _fit_display(scene["phrase"], sizes=(54, 48, 44, 40, 36, 32), width=560, lines=6, height=320)
            lines_in(world, start + .1, end, fitted, size, 92, 386, extra=r"\i1")
        elif layout == "split":
            words = scene["phrase"].split()
            half = max(1, len(words) // 2)
            parts = [" ".join(words[:half]), " ".join(words[half:])] if len(words) > 1 else [scene["phrase"], ""]
            reveal = start + (end - start) * .45
            for number, (part, appear, top) in enumerate(((parts[0], start, 290), (parts[1], reveal, 500))):
                if not part:
                    continue
                size, fitted = _fit_display(part, sizes=(44, 40, 36, 32, 28), width=480, lines=3, height=150)
                shape(world, appear, end, 3, _round_rect(640, 180, 32), CARD if number else "FFFFFF",
                      rf"\move(40,{top + 40},40,{top},0,300)", r"\fad(100,120)")
                disc(world, 88, top + 48, 24, LIME if number else INK, appear, end, 4,
                     r"\fscx0\fscy0\t(0,240,\fscx100\fscy100)")
                text(world, appear, end, str(number + 1), 88, top + 48, 24, INK if number else "FFFFFF", 5,
                     r"\fad(120,0)", layer=5, bold=True)
                lines_in(world, appear + .06, end, fitted, size, 130, top + 28)
            shape(world, reveal, end, 2, "m 0 0 l 2 0 2 30 0 30", INK, r"\pos(87,470)", r"\fscy0\t(0,200,\fscy100)", "40")
        else:
            text(world, start, end, "Yakın plan", 62, 274, 19, INK_SOFT, extra=r"\fad(120,0)")
            size, fitted = _fit_display(scene["phrase"], sizes=(60, 54, 48, 44, 40, 36), width=600, lines=6, height=380)
            first = fitted.splitlines()[0] if fitted else ""
            shape(world, start + .36, end, 5, _round_rect(round(width_of(first, size) * .82) + 24, round(size * .38), 6), LIME,
                  rf"\pos(50,{316 + round(size * .74)})", r"\fscx0\t(0,440,\fscx100)")
            event(world, start, end, 6, rf"\an7\move(62,340,62,316,0,360)\fs{size}\1c{_ass_rgb(INK)}\bord0\shad0\b0\fad(120,120)",
                  _ass_escape(fitted))

        if index:
            # Panel-coloured shutter and a lime scan line cover each cut.
            shape(world, max(0, start - .16), min(duration, start + .16), 7, "m -100 262 l 820 262 820 1380 -100 1380", PANEL,
                  extra=r"\fad(140,140)")
            shape(world, max(0, start - .18), min(duration, start + .24), 7, "m -100 0 l 820 0 820 12 -100 12", LIME,
                  r"\move(0,262,0,920,0,420)")

    # Captions: word-by-word highlight keeps the eye moving with the voice.
    for start, end, caption in segments:
        tokens = re.findall(r"\S+|\n", caption)
        words = [token for token in tokens if token != "\n"]
        weights = [len(word) + 1 for word in words]
        total, cursor = sum(weights) or 1, start
        for active, weight in enumerate(weights):
            finish = end if active == len(weights) - 1 else cursor + (end - start) * weight / total
            pieces, seen = [], 0
            for token in tokens:
                if token == "\n":
                    pieces.append(r"\N")
                    continue
                escaped = _ass_escape(token)
                pieces.append(rf"{{\1c&H{LIME[4:6]}{LIME[2:4]}{LIME[0:2]}&}}{escaped}{{\1c&HFFFFFF&}}"
                              if seen == active else escaped)
                seen += 1
            body = " ".join(pieces).replace(r" \N ", r"\N")
            event(hud, cursor, finish, 9, r"\an2\pos(360,1084)\fs44\1c&HFFFFFF&\bord0\shad0\b1", body)
            cursor = finish
    if host:
        world.extend(presenter.puppet_events(
            look_id=host["look"], accent_for=lambda _index: LIME, spans=host["spans"], scenes=scenes,
            duration=duration, levels=host.get("levels"), seed=title, layer=4,
            placements=PLACEMENTS, pip_circle=PIP_CIRCLE))
    return world, hud
