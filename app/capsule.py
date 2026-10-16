"""Capsule: the dashboard video theme specified in docs/TEMA.md.

Rendered as two layers so the camera can move without shaking the interface:

* ``world`` - the panel content, timeline, cards and the raven host. It is drawn
  on a 1.2x canvas and FFmpeg's zoompan moves a virtual camera over it: every
  scene zooms into its main widget, holds, then zooms back out;
* ``hud`` - the charcoal frame, tab, chips, burned-in kinetic captions and the
  bottom scene bar, which stay still so the viewer always has a fixed anchor.

Scene colours cycle: two accent palettes, then back to the main palette, so the
eye registers every cut. Every visible phrase still comes verbatim from the
script; chart waves are decoration only.
"""
from __future__ import annotations

import math
import os
import re

from . import emphasis, presenter
from .palettes import PACKS

FRAME, PANEL, PANEL_DEEP, CARD = "3C3D3F", "E8E7E2", "D3D1CA", "F6F5F1"
INK, INK_SOFT, LIME = "2B2C2E", "77787A", "D9F23A"
SIGNAL_RED, SIGNAL_GREEN = "E8735A", "9CCB5A"

BRAND = os.environ.get("VIDEO_BRAND", "Aopia")[:24] or "Aopia"

LABELS = {"hook": "Gündem", "editorial": "Odak", "card": "Gündemde", "statement": "Yakın plan",
          "keyword": "Anahtar kelime", "quote": "Senaryodan", "split": "Adım adım"}
# Host placements for non-roaming characters; the PiP badge matches presenter's mask.
PLACEMENTS = {"big": (180.0, 486.0, .88), "pip": (504.0, 676.0, .42)}
PIP_CIRCLE = (588.0, 794.0, 96.0)
TIMELINE_Y = 236
CANVAS_SCALE = 1.2  # World layer canvas relative to the 720x1280 output.
CAPTION_Y = 1128    # Baseline of the burned-in captions, just above the scene bar.

# The widget each layout zooms into: (focus x, focus y, extra zoom).
WIDGETS = {"hook": (360, 700, .16), "host": (360, 470, .14), "keyword": (360, 520, .24),
           "editorial": (360, 470, .2), "card": (360, 520, .2), "quote": (300, 470, .18),
           "split": (360, 380, .18), "statement": (330, 430, .18)}


def palette(index: int, pack_id: str = "kapsul") -> dict:
    """Main palette, two accent palettes, back to main: 0 M, 1 A, 2 B, 3 M, 4 C, 5 D..."""
    main, *accents = PACKS[pack_id]["scenes"]
    if index % 3 == 0:
        return main
    return accents[(index - index // 3 - 1) % len(accents)]


def _wave(width: int, base: float, amplitude: float, period: float, phase: float, bottom: float) -> str:
    points = [(x, base + amplitude * math.sin(x / period + phase)) for x in range(0, width + 1, 20)]
    path = f"m 0 {bottom:.0f} l " + " ".join(f"{x} {y:.1f}" for x, y in points)
    return path + f" {width} {bottom:.0f}"


def _round_rect_reversed(x: int, y: int, w: int, h: int, r: int) -> str:
    """Counter-clockwise rounded rectangle, used to punch a hole into the frame."""
    return (f"m {x + r} {y} b {x} {y} {x} {y} {x} {y + r} l {x} {y + h - r} b {x} {y + h} {x} {y + h} {x + r} {y + h} "
            f"l {x + w - r} {y + h} b {x + w} {y + h} {x + w} {y + h} {x + w} {y + h - r} l {x + w} {y + r} "
            f"b {x + w} {y} {x + w} {y} {x + w - r} {y} l {x + r} {y}")


def keyword(phrase: str) -> str:
    """The longest verbatim word of a phrase, trimmed of surrounding punctuation."""
    words = [word.strip(".,;:!?…\"'“”‘’()[]") for word in phrase.split()]
    return max((word for word in words if word), key=len, default=phrase.strip())


def keyword_size(word: str) -> int:
    from .media import _glyph_width
    # Fits inside the frame even at the zoom's peak.
    return max(40, min(104, round(440 / max(1.0, sum(map(_glyph_width, word))))))


def keyword_pill(word: str) -> tuple[int, int]:
    from .media import _glyph_width
    size = keyword_size(word)
    return round(sum(map(_glyph_width, word)) * size) + 64, round(size * 1.3)


def perches(scenes: list[dict]) -> list[dict]:
    """Where a roaming host lands in each scene: (time, feet x, feet y, scale).

    The bird sits on the interface itself - the stage, the "Gündemde" pill, the
    keyword, the quote mark, the cards, the "+" button - so every cut gives the
    eye one moving, living thing to follow.
    """
    planned = []
    for scene in scenes:
        scene = dict(scene)
        start, end, layout = scene["start"], scene["end"], scene["layout"]
        if layout in ("hook", "host"):
            spots = [(start, 360.0, 926.0, .66 if layout == "hook" else .6)]
        elif layout == "card":
            spots = [(start, 292.0, 290.0, .24)]
        elif layout == "keyword":
            width, height = keyword_pill(keyword(scene["phrase"]))
            spots = [(start, 360.0 + width / 2 - 70, 520.0 - height / 2, .26)]
        elif layout == "quote":
            spots = [(start, 110.0, 278.0, .22)]
        elif layout == "split":
            spots = [(start, 590.0, 290.0, .24), (start + (end - start) * .45, 590.0, 500.0, .24)]
        elif layout == "statement":
            spots = [(start, 640.0, 206.0, .22)]
        else:
            spots = [(start, 590.0, 712.0, .3)]
        scene["perch"] = spots
        planned.append(scene)
    return planned


def emphasis_moments(segments, duration: float) -> list[dict]:
    """The typography map's chosen moments for this narration."""
    return emphasis.choose_moments(emphasis.typography_map(caption_chunks(segments)), duration)


def camera(scenes: list[dict], duration: float, moments: list[dict] | None = None) -> tuple[str, str, str]:
    """zoompan expressions (z, x, y): a still frame, punching in only at emphasis moments.

    Each moment eases in just before its word, holds while it is spoken, then
    eases back out; the camera aims at the widget of the scene on screen then.
    """
    def scene_at(t):
        return next((scene for scene in scenes if scene["start"] <= t < scene["end"]), scenes[-1])

    terms, focus_x, focus_y = [], [], []
    for moment in moments or []:
        start, end = moment["start"] - .28, moment["end"] + .5
        rise = f"min(1,max(0,(it-{start:.3f})/0.28))"
        fall = f"min(1,max(0,({end + .7:.3f}-it)/0.7))"
        b = f"min({rise},{fall})"
        bump = f"({b}*{b}*(3-2*{b}))"
        fx, fy, _extra = WIDGETS.get(scene_at(moment["start"])["layout"], (360, 480, .16))
        strength = min(.2, .12 + .03 * moment["score"])
        terms.append(f"{strength:.3f}*{bump}")
        focus_x.append(f"{fx - 360}*{bump}")
        focus_y.append(f"{fy - 640}*{bump}")
    z = "1.0" + "".join(f"+{term}" for term in terms)
    fx = "(360" + "".join(f"+{term}" for term in focus_x) + f")*{CANVAS_SCALE}"
    fy = "(640" + "".join(f"+{term}" for term in focus_y) + f")*{CANVAS_SCALE}"
    x = f"max(0,min(iw-iw/zoom,{fx}-iw/zoom/2))"
    y = f"max(0,min(ih-ih/zoom,{fy}-ih/zoom/2))"
    return z, x, y


def sfx_cues(scenes: list[dict], moments: list[dict] | None = None) -> tuple[list[float], list[float]]:
    """Whooshes on every cut; pops on emphasis moments, keywords and second cards."""
    whooshes = [scene["start"] for scene in scenes[1:]]
    pops = [moment["start"] for moment in moments or []]
    for scene in scenes:
        if scene["layout"] == "keyword":
            pops.append(scene["start"] + .12)
        elif scene["layout"] == "split":
            pops.append(scene["start"] + (scene["end"] - scene["start"]) * .45)
    return whooshes, pops


def caption_chunks(segments) -> list[tuple[float, float, list[str]]]:
    """Re-cut narration captions into short 1-4 word bursts with per-word timing."""
    from .media import _glyph_width
    bursts = []
    for start, end, caption in segments:
        words = caption.split()
        if not words:
            continue
        weights = [len(word) + 1 for word in words]
        total = sum(weights)
        times, cursor = [], start
        for weight in weights:
            times.append(cursor)
            cursor += (end - start) * weight / total
        group: list[int] = []
        for index, word in enumerate(words):
            candidate = " ".join(words[i] for i in group + [index])
            if group and (len(group) >= 4 or sum(map(_glyph_width, candidate)) > 15):
                bursts.append((group, words, times, end))
                group = []
            group.append(index)
        if group:
            bursts.append((group, words, times, end))
    result = []
    for group, words, times, end in bursts:
        first, last = group[0], group[-1]
        finish = times[last + 1] if last + 1 < len(times) else end
        result.append((times[first], finish, [words[i] for i in group], [times[i] for i in group]))
    return result


def _upper(text: str) -> str:
    return text.replace("i", "İ").replace("ı", "I").upper()


def events(title: str, segments, scenes: list[dict], duration: float, host: dict | None,
           pack_id: str = "kapsul", brand: dict | None = None) -> tuple[list[str], list[str], list[dict]]:
    """World and HUD events plus logo overlays ({file, start, end, x, y, size} in output pixels).

    ``brand`` is {"name", "logo" (path or None), "slugs"}: the story's brand gets a
    logo tile (or a wordmark pill without an uploaded logo) in the opening and on
    the "+" button of every scene that mentions it."""
    from .media import _ass_escape, _ass_rgb, _fit_display, _glyph_width, _round_rect, _timestamp

    world: list[str] = []
    hud: list[str] = []
    overlays: list[dict] = []
    pk = PACKS[pack_id]
    frame, pop = pk["frame"], pk["pop"]

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

    def lines_in(target, start, end, fitted, size, x, y, color, extra="", align=7, layer=6):
        event(target, start, end, layer,
              rf"\an{align}\move({x},{y + 30},{x},{y},0,340)\fs{size}\1c{_ass_rgb(color)}\bord0\shad0\b0\fad(120,120){extra}",
              _ass_escape(fitted))

    count = len(scenes)
    # --- HUD chassis: frame with a window onto the moving world ------------------------
    shape(hud, 0, duration, 0, "m 0 0 l 720 0 720 1280 0 1280 " + _round_rect_reversed(18, 150, 684, 1112, 44), frame)
    bar, idle_dot = ("141B2B", "39445C") if pk.get("cyber") else ("FFFFFF", PANEL_DEEP)
    shape(hud, 0, duration, 1, _round_rect(640, 66, 33), bar, r"\pos(40,1158)")
    disc(hud, 80, 1191, 26, frame, 0, duration, 2)
    shape(hud, 0, duration, 3, _round_rect(18, 16, 4), pop, r"\pos(71,1183)")
    dots = [round(150 + (630 - 150) * (i + .5) / count) for i in range(count)]
    for x in dots:
        disc(hud, x, 1191, 6, idle_dot, 0, duration, 2)

    shape(world, 0, duration, 0, "m -100 -100 l 820 -100 820 1380 -100 1380", PANEL)
    if pk.get("cyber"):
        # HUD corner brackets around the window and faint CRT scanlines.
        brackets = []
        for x, y, sx, sy in ((30, 162, 1, 1), (690, 162, -1, 1), (30, 1250, 1, -1), (690, 1250, -1, -1)):
            brackets.append(f"m {x} {y} l {x + 46 * sx} {y} {x + 46 * sx} {y + 4 * sy} {x + 4 * sx} {y + 4 * sy} "
                            f"{x + 4 * sx} {y + 46 * sy} {x} {y + 46 * sy}")
        shape(hud, 0, duration, 5, " ".join(brackets), pop, extra=r"\blur1", alpha="20")
        scan = " ".join(f"m 0 {y} l 720 {y} 720 {y + 1} 0 {y + 1}" for y in range(150, 1262, 5))
        shape(hud, 0, duration, 3, scan, "000000", alpha="E8")
    big_name = presenter.display_name(host["name"]) if host else ""
    for index, scene in enumerate(scenes):
        start, end = scene["start"], scene["end"]
        milliseconds = max(1, round((end - start) * 1000))
        layout = scene["layout"]
        pal = palette(index, pack_id)
        ink, card_ink, soft, accent, on_accent = pal["ink"], pal["card_ink"], pal["soft"], pal["accent"], pal["on_accent"]
        last = index == count - 1
        label = ("Son söz" if last else "Ara sahne") if layout == "host" else LABELS.get(layout, "Gündem")

        # HUD: the tab takes the scene colour so it stays merged with the panel.
        shape(hud, start, end, 0, _round_rect(372, 132, 44) + " m 0 62 l 372 62 372 176 0 176", pal["panel"], r"\pos(18,18)")
        shape(hud, start, end, 0, "m 390 104 l 390 150 l 436 150 b 411 150 390 129 390 104", pal["panel"])
        disc(hud, 74, 84, 30, "FFFFFF", start, end, 1)
        text(hud, start, end, BRAND[:1].upper(), 74, 84, 30, frame, 5, layer=2, bold=True)
        text(hud, start, end, BRAND, 120, 50, 46, ink)
        text(hud, start, end, "Teknoloji gündemi", 122, 104, 17, soft)
        chip = width_of(label, 18) + 44
        shape(hud, start, end, 1, _round_rect(chip, 52, 26), CARD, r"\pos(408,49)", r"\fad(120,0)")
        text(hud, start, end, label, 408 + chip // 2, 75, 18, INK, 5, r"\fad(120,0)", layer=2)
        shape(hud, start, end, 1, _round_rect(104, 52, 26), "57585B", rf"\pos({416 + chip},49)")
        text(hud, start, end, f"{index + 1:02d} / {count:02d}", 468 + chip, 75, 17, "FFFFFF", 5, layer=2)
        shape(hud, start, end, 2, _round_rect(64, 44, 22), "2A3450" if pk.get("cyber") else frame,
              rf"\pos({dots[index] - 32},1169)", r"\fad(100,0)")
        disc(hud, dots[index], 1191, 7, pop, start, end, 3, r"\fscx0\fscy0\t(0,220,\fscx100\fscy100)")
        for past in dots[:index]:
            disc(hud, past, 1191, 6, pop if pk.get("cyber") else frame, start, end, 3, alpha="40")

        # World backdrop in the scene colour with a faint grid that makes zooms readable.
        shape(world, start, end, 0, "m -100 -100 l 820 -100 820 1380 -100 1380", pal["panel"])
        grid = " ".join(f"m {x} 0 l {x + 1} 0 {x + 1} 1280 {x} 1280" for x in range(40, 720, 80))
        grid += " " + " ".join(f"m 0 {y} l 720 {y} 720 {y + 1} 0 {y + 1}" for y in range(300, 1280, 80))
        shape(world, start, end, 0, grid, ink, alpha="EC")
        shape(world, start, end, 1, "m 0 0 l 360 0 360 2 0 2", SIGNAL_RED, rf"\pos(0,{TIMELINE_Y - 1})", alpha="40")
        shape(world, start, end, 1, "m 360 0 l 720 0 720 2 360 2", SIGNAL_GREEN, rf"\pos(0,{TIMELINE_Y - 1})", alpha="40")
        disc(world, 640, TIMELINE_Y, 30, ink, start, end, 2)
        shape(world, start, end, 3, "m -10 -1.5 l 10 -1.5 10 1.5 -10 1.5 m -1.5 -10 l 1.5 -10 1.5 10 -1.5 10",
              pal["panel"], rf"\pos(640,{TIMELINE_Y})")
        disc(world, 96, TIMELINE_Y, 32, accent, start, end, 2,
             r"\fscx0\fscy0\t(0,260,\fscx112\fscy112)\t(260,380,\fscx100\fscy100)")
        shape(world, start, end, 3, "m -9 -9 l 9 -9 9 -5 -9 -5 m -9 -2 l 9 -2 9 2 -9 2 m -9 5 l 4 5 4 9 -9 9", on_accent,
              rf"\pos(96,{TIMELINE_Y})", r"\fad(200,0)")
        shape(world, start, end, 1, "m 0 0 l 512 0 512 3 0 3", ink, rf"\pos(128,{TIMELINE_Y - 1})",
              r"\fscx0\t(0,520,\fscx100)", "90")

        mode = scene.get("host")
        roaming = bool(host and scene.get("perch"))
        if host and mode == "big":
            shape(world, start, end, 1, _round_rect(640, 430, 40), pal["deep"], r"\move(40,540,40,500,0,360)", r"\fad(120,0)")
            disc(world, 360, 720, 170, pal["card"], start, end, 1, r"\fscx60\fscy60\t(0,420,\fscx100\fscy100)\fad(120,0)", "60")
            tag = width_of(big_name, 22) + 64
            shape(world, start, end, 5, _round_rect(tag, 46, 23), accent, r"\move(-220,860,52,860,0,320)")
            disc(world, 78, 883, 7, on_accent, start, end, 5, r"\move(-194,883,78,883,0,320)")
            text(world, start, end, big_name, 96, 871, 22, on_accent, extra=r"\move(-176,871,96,871,0,320)", layer=5)
        elif host and mode == "pip" and not roaming:
            cx, cy, radius = PIP_CIRCLE
            disc(world, cx, cy, radius, pal["deep"], start, end, 3, r"\fscx0\fscy0\t(0,260,\fscx100\fscy100)")
            ring = presenter.screen_circle(cx, cy, radius - 4) + " " + presenter.screen_circle(cx, cy, radius - 10, reverse=True)
            shape(world, start, end, 5, ring, accent, extra=r"\fad(220,0)\blur1.5")
            name = presenter.display_name(host["name"])
            tag = width_of(name, 16) + 30
            shape(world, start, end, 5, _round_rect(tag, 30, 15), accent,
                  rf"\pos({round(cx - tag / 2)},{round(cy + radius - 20)})", r"\fad(220,0)")
            text(world, start, end, name, round(cx), round(cy + radius - 5), 16, on_accent, 5, r"\fad(220,0)", layer=5, bold=True)

        if brand and (layout == "hook" or any(
                stem in scene.get("phrase", "").lower() for stem in brand["stems"])):
            # The story's brand: an uploaded logo on a white tile, else a wordmark pill.
            hero = layout == "hook"
            if brand.get("logo"):
                size = 150 if hero else 72
                x, y = (66, 516) if hero else (604, 200)
                shape(world, start, end, 5, _round_rect(size, size, size // 4), "FFFFFF", rf"\pos({x},{y})",
                      r"\fscx0\fscy0\t(0,220,\fscx100\fscy100)")
                inset = round(size * .12)
                overlays.append({"file": brand["logo"], "start": start + .2, "end": end, "x": x + inset, "y": y + inset,
                                 "size": size - 2 * inset})
            else:
                name = brand["name"]
                size = 34 if hero else 22
                width = width_of(name, size) + (48 if hero else 30)
                height = round(size * 1.7)
                x, y = (66, 520) if hero else (604 - width, 236 - height // 2)
                shape(world, start, end, 5, _round_rect(width, height, height // 2), accent, rf"\pos({x},{y})",
                      r"\fscy0\t(0,200,\fscy100)")
                text(world, start + .1, end, name, x + width // 2, y + height // 2, size, on_accent, 5,
                     r"\fad(120,0)", layer=6, bold=True)

        if layout == "hook":
            text(world, start, end, "Bugünün konusu", 62, 274, 19, soft, extra=r"\fad(120,0)")
            size, fitted = _fit_display(title, sizes=(62, 56, 50, 44, 40, 36), width=600, lines=4,
                                        height=190 if host else 520)
            height = round(size * 1.12)
            for number, line in enumerate(fitted.splitlines()):
                y = 308 + number * height
                event(world, start + min(.1 * number, (end - start) * .15), end, 6,
                      rf"\an7\move(62,{y + 34},62,{y},0,380)\fs{size}\1c{_ass_rgb(ink)}\bord0\shad0\b0\fad(160,120)",
                      _ass_escape(line))
        elif layout == "host":
            size, fitted = _fit_display(scene["phrase"], sizes=(50, 46, 42, 38, 34, 30), width=548, lines=5, height=170)
            box = len(fitted.splitlines()) * round(size * 1.18) + 96
            top = 268
            shape(world, start, end, 6, _round_rect(640, box, 36), pal["card"], rf"\move(40,{top + 40},40,{top},0,320)", r"\fad(100,120)")
            shape(world, start, end, 6, f"m 300 {top + box - 2} l 364 {top + box - 2} l 318 {top + box + 46}", pal["card"],
                  r"\move(0,40,0,0,0,320)", r"\fad(100,120)")
            chip = width_of(label, 16) + 36
            shape(world, start + .06, end, 6, _round_rect(chip, 32, 16), accent, rf"\pos(76,{top + 26})", r"\fad(120,120)")
            text(world, start + .06, end, label, 76 + chip // 2, top + 42, 16, on_accent, 5, r"\fad(120,120)")
            lines_in(world, start + .1, end, fitted, size, 76, top + 74, card_ink)
        elif layout == "editorial":
            shape(world, start, end, 1, "m 0 0 l 2 0 2 36 0 36", ink, rf"\pos(95,{TIMELINE_Y + 30})", alpha="40")
            shape(world, start, end, 3, _round_rect(640, 410, 36), pal["card"], r"\move(40,346,40,300,0,320)", r"\fad(100,120)")
            text(world, start, end, "Odak noktası", 76, 332, 18, card_ink, extra=r"\1a&H60&" + r"\move(76,378,76,332,0,320)\fad(100,120)")
            disc(world, 632, 348, 26, "FFFFFF", start, end, 4, r"\fad(160,120)")
            disc(world, 632, 348, 8, accent, start, end, 4, r"\fad(200,120)")
            size, fitted = _fit_display(scene["phrase"], sizes=(52, 46, 42, 38, 34, 30), width=560, lines=5, height=230)
            lines_in(world, start + .08, end, fitted, size, 76, 380, card_ink)
            clip = r"\clip(40,610,680,710)"
            shape(world, start, end, 4, _wave(1400, 630, 16, 60, 0, 700), accent,
                  rf"\move(-680,0,0,0,0,{milliseconds})", clip + r"\fad(200,120)")
            shape(world, start, end, 4, _wave(1400, 656, 12, 44, 1.3, 700), "A9A7A0",
                  rf"\move(0,0,-640,0,0,{milliseconds})", clip + r"\fad(200,120)", "40")
        elif layout == "card":
            shape(world, start, end, 3, _round_rect(300, 64, 32), accent, r"\move(-260,290,40,290,0,320)")
            disc(world, 72, 322, 24, on_accent, start, end, 4, r"\move(-228,322,72,322,0,320)")
            shape(world, start, end, 5, _round_rect(22, 10, 5), accent, r"\move(-239,317,61,317,0,320)", r"\frz35")
            text(world, start, end, "Gündemde", 112, 308, 20, on_accent, extra=r"\move(-188,308,112,308,0,320)", layer=5)
            shape(world, start, end, 1, "m 0 0 l 2 0 2 34 0 34", ink, r"\pos(190,354)", alpha="40")
            shape(world, start, end, 3, _round_rect(640, 330, 36), pal["card"], r"\move(40,430,40,388,0,320)", r"\fad(100,120)")
            size, fitted = _fit_display(scene["phrase"], sizes=(52, 46, 42, 38, 34, 30), width=560, lines=5, height=250)
            lines_in(world, start + .1, end, fitted, size, 360, 553, card_ink, align=5)
        elif layout == "keyword":
            word = keyword(scene["phrase"])
            size = keyword_size(word)
            pill_w, pill_h = keyword_pill(word)
            text(world, start, end, "Anahtar kelime", 62, 300, 19, soft, extra=r"\fad(120,0)")
            shape(world, start, end, 4, _round_rect(pill_w, pill_h, pill_h // 2), accent,
                  rf"\pos({360 - pill_w // 2},{520 - pill_h // 2})", r"\fscy0\t(0,180,\fscy100)")
            event(world, start + .06, end, 6,
                  rf"\an5\pos(360,520)\fs{size}\1c{_ass_rgb(on_accent)}\bord0\shad0\b1\fscx150\fscy150\t(0,200,\fscx100\fscy100)",
                  _ass_escape(word))
            small, context = _fit_display(scene["phrase"], sizes=(34, 30, 28, 26), width=600, lines=4, height=170)
            event(world, start + .35, end, 6,
                  rf"\an8\move(360,720,360,690,0,340)\fs{small}\1c{_ass_rgb(soft)}\bord0\shad0\b0\fad(160,120)",
                  _ass_escape(context))
        elif layout == "quote":
            shape(world, start, end, 3, "m 0 30 b 0 10 14 0 30 0 l 30 22 b 20 22 16 30 18 40 l 34 40 l 34 74 l 0 74 "
                                        "m 46 30 b 46 10 60 0 76 0 l 76 22 b 66 22 62 30 64 40 l 80 40 l 80 74 l 46 74",
                  accent, r"\move(62,300,62,276,0,300)", r"\fscx140\fscy140\t(0,260,\fscx100\fscy100)")
            shape(world, start, end, 3, "m 0 0 l 6 0 6 330 0 330", ink, r"\pos(62,380)", r"\fscy0\t(80,520,\fscy100)")
            size, fitted = _fit_display(scene["phrase"], sizes=(54, 48, 44, 40, 36, 32), width=560, lines=6, height=320)
            lines_in(world, start + .1, end, fitted, size, 92, 386, ink, extra=r"\i1")
        elif layout == "split":
            words = scene["phrase"].split()
            half = max(1, len(words) // 2)
            parts = [" ".join(words[:half]), " ".join(words[half:])] if len(words) > 1 else [scene["phrase"], ""]
            reveal = start + (end - start) * .45
            for number, (part, appear, top) in enumerate(((parts[0], start, 290), (parts[1], reveal, 500))):
                if not part:
                    continue
                size, fitted = _fit_display(part, sizes=(44, 40, 36, 32, 28), width=480, lines=3, height=150)
                shape(world, appear, end, 3, _round_rect(640, 180, 32), pal["card"],
                      rf"\move(40,{top + 40},40,{top},0,300)", r"\fad(100,120)")
                disc(world, 88, top + 48, 24, accent if number else card_ink, appear, end, 4,
                     r"\fscx0\fscy0\t(0,240,\fscx100\fscy100)")
                text(world, appear, end, str(number + 1), 88, top + 48, 24, on_accent if number else pal["card"], 5,
                     r"\fad(120,0)", layer=5, bold=True)
                lines_in(world, appear + .06, end, fitted, size, 130, top + 28, card_ink)
            shape(world, reveal, end, 2, "m 0 0 l 2 0 2 30 0 30", ink, r"\pos(87,470)", r"\fscy0\t(0,200,\fscy100)", "40")
        else:
            text(world, start, end, "Yakın plan", 62, 274, 19, soft, extra=r"\fad(120,0)")
            size, fitted = _fit_display(scene["phrase"], sizes=(60, 54, 48, 44, 40, 36), width=600, lines=6, height=380)
            first = fitted.splitlines()[0] if fitted else ""
            shape(world, start + .36, end, 5, _round_rect(round(width_of(first, size) * .82) + 24, round(size * .38), 6), accent,
                  rf"\pos(50,{316 + round(size * .74)})", r"\fscx0\t(0,440,\fscx100)", "60")
            event(world, start, end, 6, rf"\an7\move(62,340,62,316,0,360)\fs{size}\1c{_ass_rgb(ink)}\bord0\shad0\b0\fad(120,120)",
                  _ass_escape(fitted))

        if index:
            # A wipe in the new scene colour plus a scan line covers each cut.
            shape(world, max(0, start - .16), min(duration, start + .16), 7, "m -100 -100 l 820 -100 820 1380 -100 1380",
                  pal["panel"], extra=r"\fad(140,140)")
            shape(world, max(0, start - .18), min(duration, start + .24), 7, "m -100 0 l 820 0 820 12 -100 12", accent,
                  r"\move(0,262,0,1100,0,420)")

    # Burned-in kinetic captions: short bursts, each word pops in as it is spoken
    # and the spoken word lights up. No box: thick outline and shadow over the scene.
    lime = rf"&H{pop[4:6]}{pop[2:4]}{pop[0:2]}&"
    stressed = {round(moment["start"], 3) for moment in emphasis_moments(segments, duration)}
    for number, (start, end, words, times) in enumerate(caption_chunks(segments)):
        tilt = (-2.5, 1.5, -1, 2.5)[number % 4]
        upper = [_upper(word) for word in words]
        lines, current = [], []
        for i, word in enumerate(upper):
            if current and sum(map(_glyph_width, " ".join(upper[j] for j in current + [i]))) > 11:
                lines.append(current)
                current = []
            current.append(i)
        lines.append(current)
        boundaries = times[1:] + [end]
        for active, (word_start, word_end) in enumerate(zip(times, boundaries)):
            rendered = []
            for line in lines:
                pieces = []
                for i in line:
                    escaped = _ass_escape(upper[i])
                    if i < active:
                        pieces.append(r"{\1c&HFFFFFF&\alpha&H00&}" + escaped)
                    elif i == active and round(times[i], 3) in stressed:
                        # Typography-map moment: the word lands big and stays enlarged.
                        pieces.append(rf"{{\1c{lime}\alpha&H00&\fscx175\fscy175\t(0,140,\fscx145\fscy145)}}" + escaped +
                                      r"{\fscx100\fscy100}")
                    elif i == active:
                        pieces.append(rf"{{\1c{lime}\alpha&H00&\fscx122\fscy122\t(0,110,\fscx100\fscy100)}}" + escaped +
                                      r"{\fscx100\fscy100}")
                    else:
                        pieces.append(r"{\alpha&HFF&}" + escaped)
                rendered.append(" ".join(pieces))
            entrance = r"\fscx70\fscy70\t(0,120,\fscx100\fscy100)" if active == 0 else ""
            event(hud, word_start, word_end, 9,
                  rf"\an2\pos(360,{CAPTION_Y})\fs62\b1\bord6\3c&H2E2C2B&\shad4\4c&H000000&\4a&H80&\frz{tilt}{entrance}",
                  r"\N".join(rendered))
    if host:
        world.extend(presenter.puppet_events(
            look_id=host["look"], spans=host["spans"], scenes=scenes,
            accent_for=lambda index: palette(index, pack_id)["bird" if presenter.LOOKS[host["look"]].get("kind") == "raven"
                                                              else "accent"],
            duration=duration, levels=host.get("levels"), seed=title, layer=4,
            placements=PLACEMENTS, pip_circle=PIP_CIRCLE))
    return world, hud, overlays
