"""An original, code-drawn presenter puppet for the "host" video design.

The rig follows the way 2D puppet tools (Adobe Character Animator, PNGTuber and
VTuber rigs) split a character into independently driven parts: body, head,
eyes, pupils, eyebrows and mouth. Every part is a local vector path rendered by
libass, so no downloaded artwork, fonts or licensed sprites are involved.

Drivers, all deterministic for a given title and narration:
  * mouth  - the narration's loudness picks how far the mouth opens and the
             caption text under the playhead picks a viseme (A/E/I/O/U, M-B-P,
             F-V), similar to Rhubarb-style mouth charts;
  * eyes   - automatic blinks and short gaze shifts (saccades);
  * brows  - lift with speech energy and on scene cuts, questions and exclamations;
  * head   - idle sway, a talking bob and an emphasis tilt on every cut.
"""
from __future__ import annotations

from array import array
import math
from pathlib import Path
import random
import wave
import zlib

FPS = 12
PIVOT = (200.0, 460.0)  # Neck pivot inside the 400x560 local character frame.
MAX_NAME = 18

LOOKS = {
    # Vega, the default host: a sleek android news anchor for a grown-up tech
    # audience. Matte metal face, a dark visor with glowing eyes, a light-bar mouth
    # that becomes a voice equalizer, ear modules and circuit lines that glow in
    # the scene's accent colour.
    "vega": {"label": "Vega", "kind": "android", "skin": "D3DAE3", "shade": "A9B3C1", "hair": "6B7686",
             "hairstyle": "none", "glasses": False, "beard": False, "hoodie": "1B2433",
             "glow": {"eyes", "mouth-eq", "circuits", "core", "ear-lights", "temple"}},
    # Kuzgun, the default host: a glossy raven whose beak is the mouth. Spiky crown
    # feathers, a lime-ringed eye and a lime scarf make the silhouette iconic.
    # It roams like a real bird: flies between cuts, perches on cards and buttons,
    # hops, pecks and snaps its head in small jerky steps.
    "kuzgun": {"label": "Kuzgun", "kind": "raven", "skin": "1B1E29", "shade": "2E3446", "hair": "4C5675",
               "hairstyle": "none", "glasses": False, "beard": False, "hoodie": "1B1E29", "roam": True,
               "pivot": (282.0, 330.0), "feet": (200.0, 640.0)},
    # Volt is the Capsule theme's mascot: capsule head, antenna and headphones
    # form a silhouette that stays recognizable even as a flat shadow.
    "volt": {"label": "Volt", "kind": "mascot", "skin": "F2F1EC", "shade": "C9C7C0", "hair": "2B2C2E",
             "hairstyle": "none", "glasses": False, "beard": False, "hoodie": "34363A"},
    "nova": {"label": "Nova", "skin": "D9956A", "shade": "B9774F", "hair": "2A1F3D",
             "hairstyle": "quiff", "glasses": True, "beard": False, "hoodie": "3A4F7A"},
    "kaan": {"label": "Kaan", "skin": "9A6440", "shade": "7C4C2E", "hair": "201C1B",
             "hairstyle": "short", "glasses": True, "beard": True, "hoodie": "4E5560"},
    "ece": {"label": "Ece", "skin": "F1C6A2", "shade": "D9A47F", "hair": "5A2E1E",
            "hairstyle": "bob", "glasses": False, "beard": False, "hoodie": "7A4A8C"},
}

# Base mouth sizes (half width, opening) per viseme family.
VISEMES = {"C": (22, 18), "E": (26, 12), "I": (24, 8), "O": (14, 17), "U": (10, 11),
           "F": (20, 6), "B": (16, 8)}
_VOWELS = {"a": "C", "â": "C", "e": "E", "ı": "I", "i": "I", "î": "I",
           "o": "O", "ö": "O", "u": "U", "ü": "U", "û": "U"}


def display_name(name: str) -> str:
    """Upper-case a host name with Turkish dotted/dotless i rules."""
    return name.replace("i", "İ").replace("ı", "I").upper()


def clean_name(value, look: str) -> str:
    text = " ".join(str(value or "").split())[:MAX_NAME]
    return text or LOOKS[look]["label"]


# --- vector helpers ------------------------------------------------------------------

def _n(value: float) -> str:
    value = round(value, 1)
    return str(int(value)) if value == int(value) else f"{value:.1f}"


def _ellipse(cx, cy, rx, ry, reverse=False) -> str:
    kx, ky = rx * .5523, ry * .5523
    if reverse:
        points = [(cx + rx, cy), (cx + rx, cy - ky, cx + kx, cy - ry, cx, cy - ry),
                  (cx - kx, cy - ry, cx - rx, cy - ky, cx - rx, cy),
                  (cx - rx, cy + ky, cx - kx, cy + ry, cx, cy + ry),
                  (cx + kx, cy + ry, cx + rx, cy + ky, cx + rx, cy)]
    else:
        points = [(cx + rx, cy), (cx + rx, cy + ky, cx + kx, cy + ry, cx, cy + ry),
                  (cx - kx, cy + ry, cx - rx, cy + ky, cx - rx, cy),
                  (cx - rx, cy - ky, cx - kx, cy - ry, cx, cy - ry),
                  (cx + kx, cy - ry, cx + rx, cy - ky, cx + rx, cy)]
    start, *curves = points
    return f"m {_n(start[0])} {_n(start[1])} " + " ".join("b " + " ".join(_n(v) for v in c) for c in curves)


def _rrect(x, y, w, h, r) -> str:
    return (f"m {_n(x+r)} {_n(y)} l {_n(x+w-r)} {_n(y)} b {_n(x+w)} {_n(y)} {_n(x+w)} {_n(y)} {_n(x+w)} {_n(y+r)} "
            f"l {_n(x+w)} {_n(y+h-r)} b {_n(x+w)} {_n(y+h)} {_n(x+w)} {_n(y+h)} {_n(x+w-r)} {_n(y+h)} "
            f"l {_n(x+r)} {_n(y+h)} b {_n(x)} {_n(y+h)} {_n(x)} {_n(y+h)} {_n(x)} {_n(y+h-r)} "
            f"l {_n(x)} {_n(y+r)} b {_n(x)} {_n(y)} {_n(x)} {_n(y)} {_n(x+r)} {_n(y)}")


def _polygon(points) -> str:
    first, *rest = points
    return f"m {_n(first[0])} {_n(first[1])} l " + " ".join(f"{_n(x)} {_n(y)}" for x, y in rest)


def _rotated(points, angle, cx, cy):
    c, s = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    return [(cx + x * c - y * s, cy + x * s + y * c) for x, y in points]


def screen_circle(cx: float, cy: float, r: float, reverse: bool = False) -> str:
    return _ellipse(cx, cy, r, r, reverse)


def _darker(color: str, factor: float) -> str:
    return "".join(f"{max(0, min(255, round(int(color[i:i+2], 16) * factor))):02X}" for i in (0, 2, 4))


# --- the character ---------------------------------------------------------------------

def _brow(cx, cy, raise_, tilt, mirror) -> str:
    shape = [(-28, 3), (-12, -4), (8, -6), (27, -1), (27, 5), (8, 2), (-12, 3), (-28, 8)]
    if mirror:
        shape = [(-x, y) for x, y in reversed(shape)]
    angle = -tilt if mirror else tilt
    return _polygon(_rotated(shape, angle, cx, cy - raise_ * 13))


def _mouth(pose) -> list[tuple[str, str, str]]:
    kind, w, h = pose["mouth"]
    cx, cy = 200, 344
    if kind == "X":
        return [("lip", "5A2028", f"m {cx-24} {cy-4} b {cx-12} {cy+6} {cx+12} {cy+6} {cx+24} {cy-4} "
                                  f"b {cx+14} {cy+12} {cx-14} {cy+12} {cx-24} {cy-4}")]
    top = cy - h * .35
    parts = [("mouth", "4A1520",
              f"m {_n(cx-w)} {_n(cy)} b {_n(cx-w*.5)} {_n(top)} {_n(cx+w*.5)} {_n(top)} {_n(cx+w)} {_n(cy)} "
              f"b {_n(cx+w*.75)} {_n(cy+h*1.05)} {_n(cx-w*.75)} {_n(cy+h*1.05)} {_n(cx-w)} {_n(cy)}")]
    if h >= 8:
        parts.append(("teeth", "FFFFFF", _ellipse(cx, cy - h * .02, w * .6, max(2.2, h * .2))))
    if h >= 11:
        parts.append(("tongue", "E2697C", _ellipse(cx, cy + h * .6, w * .45, h * .24)))
    return parts


def _stroke(points, width):
    """A polyline as a closed polygon, for circuit traces and seams."""
    left, right = [], []
    for index, (x, y) in enumerate(points):
        ax, ay = points[max(0, index - 1)]
        bx, by = points[min(len(points) - 1, index + 1)]
        dx, dy = bx - ax, by - ay
        length = math.hypot(dx, dy) or 1
        nx, ny = -dy / length * width / 2, dx / length * width / 2
        left.append((x + nx, y + ny))
        right.append((x - nx, y - ny))
    return _polygon(left + right[::-1])


def android_body_parts(look: dict, accent: str, pose: dict) -> list[tuple[str, str, str]]:
    suit, plate = look["hoodie"], "2A3446"
    level = pose.get("level", 0.0)
    return [
        ("torso", suit, "m 20 560 b 24 480 90 440 160 430 l 240 430 b 310 440 376 480 380 560 l 20 560"),
        ("shoulders", plate, "m 34 540 b 44 476 100 448 156 440 l 146 474 b 104 482 72 506 62 540 l 34 540 "
                             "m 366 540 b 356 476 300 448 244 440 l 254 474 b 296 482 328 506 338 540 l 366 540"),
        ("neck", "5B6677", _rrect(168, 340, 64, 100, 22)),
        ("neck-rings", "3A4455", _rrect(162, 368, 76, 9, 4) + " " + _rrect(162, 394, 76, 9, 4)),
        ("collar", plate, _rrect(146, 414, 108, 36, 18)),
        ("circuits", accent + ("&\\1a&H" + f"{round(120 - 100 * min(1.0, level)):02X}"),
         " ".join(_stroke(points, 4) for points in (
             [(170, 452), (170, 492), (130, 520), (96, 520)], [(230, 452), (230, 492), (270, 520), (304, 520)],
             [(186, 452), (186, 540)], [(214, 452), (214, 540)]))),
        ("core", accent, _ellipse(200, 500, 11, 11)),
    ]


def android_head_parts(look: dict, accent: str, pose: dict) -> list[tuple[str, str, str]]:
    metal, shade, brow = look["skin"], look["shade"], look["hair"]
    gx, gy = pose["gaze"]
    level = pose.get("level", 0.0)
    parts = [
        ("ears", "2A3446", _ellipse(92, 262, 24, 36) + " " + _ellipse(308, 262, 24, 36)),
        ("ear-lights", accent, _ellipse(88, 262, 7, 18) + " " + _ellipse(312, 262, 7, 18)),
        ("head", metal, "m 200 108 b 278 108 312 170 312 250 b 312 332 276 394 200 402 "
                        "b 124 394 88 332 88 250 b 88 170 122 108 200 108"),
        ("head-shade", shade + "&\\1a&H50", "m 264 130 b 300 160 312 206 312 250 b 312 332 276 394 200 402 "
                                             "b 250 380 286 330 288 252 b 290 196 282 160 264 130"),
        ("forehead-glare", "FFFFFF&\\1a&HB0", "m 140 140 b 170 122 230 122 262 140 b 230 132 170 132 140 152"),
        ("seams", "7C8796&\\1a&H70", " ".join([
            _stroke([(112, 196), (150, 176), (200, 170), (250, 176), (288, 196)], 3),
            _stroke([(122, 306), (146, 356), (176, 384)], 3), _stroke([(278, 306), (254, 356), (224, 384)], 3),
            _stroke([(200, 112), (200, 168)], 3)])),
        ("temple", accent + ("&\\1a&H" + f"{round(150 - 120 * min(1.0, level)):02X}"),
         _stroke([(104, 214), (100, 248)], 5) + " " + _stroke([(296, 214), (300, 248)], 5)),
        # Ski goggles: a strap around the head, a wide frame with a nose cut-out
        # and a mirrored lens; the eye lights still glow through the glass.
        ("goggle-strap", "151A24", "m 80 236 b 120 230 280 230 320 236 l 320 272 b 280 266 120 266 80 272 l 80 236"),
        ("strap-stripe", accent + "&\\1a&H50", _rrect(80, 250, 22, 8, 4) + " " + _rrect(298, 250, 22, 8, 4)),
        ("goggle-frame", "1C2230", "m 120 208 l 280 208 b 304 208 314 222 314 244 l 314 276 b 314 298 300 308 278 308 "
                                   "l 238 308 b 224 308 214 290 200 290 b 186 290 176 308 162 308 l 122 308 "
                                   "b 100 308 86 298 86 276 l 86 244 b 86 222 96 208 120 208"),
        ("goggle-lens", "0D1424", "m 124 218 l 276 218 b 294 218 302 228 302 246 l 302 274 b 302 290 292 298 276 298 "
                                  "l 240 298 b 228 298 218 280 200 280 b 182 280 172 298 160 298 l 124 298 "
                                  "b 108 298 98 290 98 274 l 98 246 b 98 228 106 218 124 218"),
        ("lens-mirror", accent + "&\\1a&H90", "m 124 218 l 276 218 b 294 218 302 228 302 246 l 302 256 "
                                               "b 240 246 160 246 98 256 l 98 246 b 98 228 106 218 124 218"),
        ("lens-glare", "FFFFFF&\\1a&HB8", "m 128 224 l 176 224 l 142 290 l 112 290 m 186 224 l 204 224 l 170 290 l 156 290"),
    ]
    openness = pose["open"]
    height = max(1.6, 9 * openness)
    parts.append(("eyes", accent + "&\\1a&H30", _ellipse(160 + gx, 258 + gy * .6, 24, height) + " " +
                  _ellipse(240 + gx, 258 + gy * .6, 24, height)))
    raise_, tilt = pose["brow"]
    parts.append(("brows", brow, " ".join(_stroke(_rotated([(-24, 0), (24, 0)], (-tilt if right else tilt), x,
                                                            194 - raise_ * 9), 6)
                                         for x, right in ((160, False), (240, True)))))
    parts.append(("mouth-slot", "1A2130", _rrect(156, 334, 88, 16, 8)))
    kind, _w, h = pose["mouth"]
    if kind == "X":
        parts.append(("mouth-eq", accent + "&\\1a&H60", _rrect(166, 340, 68, 4, 2)))
    else:
        # The mouth is a voice equalizer: bar heights follow loudness and viseme.
        bars = []
        for index in range(7):
            wobble = .45 + .55 * abs(math.sin(index * 1.9 + level * 11 + h))
            bar = max(4.0, (h * 1.3 + 6) * wobble)
            bars.append(_rrect(164 + index * 10, 342 - bar / 2, 6, bar, 3))
        parts.append(("mouth-eq", accent, " ".join(bars)))
    return parts


def body_parts(look: dict, accent: str, pose: dict) -> list[tuple[str, str, str]]:
    if look.get("kind") == "android":
        return android_body_parts(look, accent, pose)
    if look.get("kind") == "raven":
        return raven_body_parts(look, accent, pose)
    wave_angle = pose.get("wave")
    hoodie = look["hoodie"]
    parts = [
        ("neck", look["shade"], _rrect(170, 340, 60, 110, 22)),
        ("hoodie", hoodie, "m 24 560 b 24 486 80 444 150 432 b 175 452 225 452 250 432 "
                           "b 320 444 376 486 376 560 l 24 560"),
        ("collar", _darker(hoodie, .7), "m 140 428 b 160 474 240 474 260 428 b 280 436 290 446 294 454 "
                                       "b 260 504 140 504 106 454 b 110 446 120 436 140 428"),
        ("strings", "F2F2F2", _rrect(176, 476, 6, 58, 3) + " " + _rrect(218, 476, 6, 58, 3)),
        ("badge", accent, _polygon([(300, 482), (282, 512), (294, 512), (287, 536), (310, 503),
                                    (297, 503), (305, 482)])),
    ]
    if wave_angle is not None:
        # A hello wave pivoting at the wrist, raised beside the right shoulder.
        wrist = (356, 392)
        def turn(points):
            return _rotated([(x - wrist[0], y - wrist[1]) for x, y in points], wave_angle, *wrist)
        cuff = [(334, 400), (380, 400), (404, 470), (392, 540), (318, 540), (322, 470)]
        palm = [(358 + 30 * math.cos(a), 350 + 36 * math.sin(a)) for a in
                (i * math.pi / 8 for i in range(16))]
        thumb = [(326 + 11 * math.cos(a), 362 + 18 * math.sin(a)) for a in
                 (i * math.pi / 6 for i in range(12))]
        parts.append(("sleeve", hoodie, _polygon(cuff)))
        parts.append(("hand", look["skin"], _polygon(turn(palm)) + " " + _polygon(turn(thumb))))
    return parts


def mascot_head_parts(look: dict, accent: str, pose: dict) -> list[tuple[str, str, str]]:
    ink, face = look["hair"], look["skin"]
    level = pose.get("level", 0.0)
    gx, gy = pose["gaze"]
    parts = [
        ("band", ink, "m 60 252 b 60 158 124 96 200 96 b 276 96 340 158 340 252 l 324 252 "
                      "b 324 170 270 112 200 112 b 130 112 76 170 76 252 l 60 252"),
        ("stem", ink, _rrect(195, 60, 10, 64, 5)),
        ("glow", accent + "&\\1a&H" + f"{round(255 - 150 * min(1.0, level)):02X}", _ellipse(200, 54, 28, 28)),
        ("bulb", accent, _ellipse(200, 54, 15, 15)),
        ("head", face, _rrect(86, 118, 228, 278, 104)),
        ("jaw", look["shade"] + "&\\1a&HA0", "m 92 300 b 96 360 140 396 200 396 b 260 396 304 360 308 300 "
                                              "b 290 352 250 378 200 378 b 150 378 110 352 92 300"),
        ("cups", accent, _rrect(54, 212, 44, 96, 22) + " " + _rrect(302, 212, 44, 96, 22)),
        ("cup-core", ink, _rrect(66, 236, 18, 48, 9) + " " + _rrect(316, 236, 18, 48, 9)),
        ("visor", ink, _rrect(104, 204, 192, 100, 50)),
    ]
    openness = pose["open"]
    height = max(6.0, 44 * openness)
    eyes = " ".join(_rrect(x - 15 + gx * .8, 254 - height / 2 + gy * .8, 30, height, min(15, height / 2))
                    for x in (156, 244))
    parts.append(("leds", accent, eyes))
    if openness > .5:
        parts.append(("led-shine", "FFFFFF&\\1a&H70", " ".join(
            _ellipse(x - 5 + gx * .8, 242 + gy * .8, 4, 6) for x in (156, 244))))
    parts.append(("blush", "F29A84&\\1a&H90", _ellipse(126, 332, 16, 8) + " " + _ellipse(274, 332, 16, 8)))
    for name, color, path in _mouth(pose):
        parts.append((name, ink if name == "lip" else color, path))
    parts.append(("mic", ink, "m 70 296 b 74 344 108 366 150 360 l 150 368 b 102 374 64 350 62 298 l 70 296"))
    parts.append(("mic-tip", accent, _rrect(144, 352, 26, 20, 10)))
    raise_, tilt = pose["brow"]
    parts.append(("brows", ink, _brow(156, 184, raise_, tilt, False) + " " + _brow(244, 184, raise_, tilt, True)))
    return parts


# --- Kuzgun: a realistic raven silhouette -----------------------------------------
# Drawn facing right in a 400x640 frame with the feet at (200, 640); mirrored when
# facing left. Like a classic bird silhouette set, everything is one solid colour
# (passed in as ``accent``): heavy arched bill, nasal bristles, shaggy throat
# hackles, long folded primaries, a wedge tail, and in flight fingered wingtips.


def _raven_path(commands, mirror: bool) -> str:
    """Build a drawing from (command, points) pairs, mirroring around x=200."""
    out = []
    for command, points in commands:
        coordinates = " ".join(f"{_n(400 - x if mirror else x)} {_n(y)}" for x, y in points)
        out.append(f"{command} {coordinates}")
    return " ".join(out)


def _poly(points, mirror):
    first, *rest = points
    return _raven_path([("m", [first]), ("l", rest)], mirror)


def _turn(points, angle, pivot):
    return _rotated([(x - pivot[0], y - pivot[1]) for x, y in points], angle, *pivot)


_SHOULDER = (196, 366)
_FOLDED_WING = [(186, 352), (232, 346), (276, 372), (292, 418), (282, 466), (246, 512), (196, 552), (150, 590),
                (104, 628), (118, 600), (88, 622), (112, 590), (82, 606), (122, 560), (140, 520), (150, 460),
                (160, 400)]
# Raised wing with five separated "finger" primaries, the raven's flight signature.
_SPREAD_WING = [(196, 366), (178, 312), (156, 250), (128, 186), (100, 120), (112, 136), (74, 120), (100, 150),
                (52, 146), (88, 172), (40, 180), (84, 198), (42, 220), (92, 228), (70, 254), (112, 262),
                (100, 290), (132, 300), (124, 326), (156, 336), (152, 358), (182, 372)]


def raven_body_parts(look: dict, accent: str, pose: dict) -> list[tuple[str, str, str]]:
    mirror = pose.get("face", 1) < 0
    ink = accent
    left, right = pose.get("wings", (0.0, 0.0))
    airborne = not pose.get("perched", True)
    flying = airborne
    if pose.get("wave") is not None:
        # Greeting: spread the wings while standing.
        flying, left = True, 40 + pose["wave"] * 2.5
    lift = max(left, right)
    parts = []
    if not airborne:
        parts.append(("shadow", "000000&\\1a&HC8", _raven_path([("m", [(70, 640)]), ("b", [(70, 628), (330, 628), (330, 640)]),
                                                                ("b", [(330, 652), (70, 652), (70, 640)])], False)))
    if flying:
        # Downstroke rotates the spread wing from raised to lowered.
        stroke = -min(1.0, lift / 95) * 115
        parts.append(("far-wing", ink, _poly(_turn([(x + 22, y - 10) for x, y in _SPREAD_WING],
                                                                 stroke * .85, (_SHOULDER[0] + 22, _SHOULDER[1] - 10)),
                                                           mirror)))
    parts += [
        ("tail", ink, _poly([(156, 520), (112, 590), (66, 650), (52, 672), (80, 664), (98, 670), (120, 660),
                              (186, 566)], mirror)),
        ("legs", ink, " ".join([
            _poly([(214, 560), (226, 560), (222, 632), (212, 632)], mirror),
            _poly([(240, 556), (252, 556), (250, 630), (240, 630)], mirror),
            _poly([(208, 630), (248, 628), (266, 636), (262, 642), (244, 638), (226, 642), (186, 642), (176, 638)], mirror),
            _poly([(236, 628), (276, 630), (292, 638), (286, 643), (252, 640), (232, 638)], mirror),
        ]) if not airborne else _poly([(214, 560), (232, 560), (196, 616), (184, 610)], mirror)),
        ("body", ink, _raven_path([("m", [(150, 330)]), ("b", [(206, 296), (300, 314), (332, 386)]),
                                   ("b", [(352, 450), (322, 540), (262, 574)]),
                                   ("b", [(222, 596), (172, 590), (144, 562)]),
                                   ("b", [(104, 524), (100, 400), (150, 330)])], mirror)),
        ("neck", ink, _poly([(244, 250), (330, 262), (344, 330), (318, 396), (196, 360)], mirror)),
        ("hackles", ink, _poly([(318, 272), (350, 286), (338, 296), (356, 314), (336, 316), (352, 338), (330, 338),
                                (342, 362), (322, 358), (326, 386), (300, 372), (296, 300)], mirror)),
    ]
    if flying:
        stroke = -min(1.0, lift / 95) * 115
        parts.append(("wing", ink, _poly(_turn(_SPREAD_WING, stroke, _SHOULDER), mirror)))
    else:
        parts.append(("wing", ink, _poly(_turn(_FOLDED_WING, lift, _SHOULDER), mirror)))
    return parts


def raven_head_parts(look: dict, accent: str, pose: dict) -> list[tuple[str, str, str]]:
    mirror = pose.get("face", 1) < 0
    ink = accent
    kind, _w, h = pose["mouth"]
    gap = 0.0 if kind == "X" else min(26.0, 6 + h * 1.2)
    gape = (354, 252)
    lower = _turn([(356, 250), (392, 252), (424, 256), (440, 260), (426, 270), (388, 272), (352, 262)], gap, gape)
    return [
        ("head", ink, _raven_path([("m", [(250, 282)]), ("b", [(232, 220), (262, 170), (312, 166)]),
                                   ("b", [(350, 164), (374, 192), (376, 226)]),
                                   ("b", [(378, 258), (360, 288), (330, 302)]), ("l", [(258, 312)])], mirror)),
        ("lower-bill", ink, _poly(lower, mirror)),
        ("bill", ink, _raven_path([("m", [(348, 206)]), ("b", [(392, 196), (436, 212), (456, 242)]),
                                   ("b", [(462, 252), (456, 262), (446, 258)]),
                                   ("b", [(420, 248), (386, 246), (354, 252)]), ("l", [(346, 236)])], mirror)),
        ("bristles", ink, _poly([(334, 198), (362, 194), (390, 204), (404, 216), (384, 212), (392, 222), (368, 216),
                                 (372, 228), (348, 222)], mirror)),
    ]


def head_parts(look: dict, accent: str, pose: dict) -> list[tuple[str, str, str]]:
    if look.get("kind") == "android":
        return android_head_parts(look, accent, pose)
    if look.get("kind") == "raven":
        return raven_head_parts(look, accent, pose)
    if look.get("kind") == "mascot":
        return mascot_head_parts(look, accent, pose)
    skin, shade, hair = look["skin"], look["shade"], look["hair"]
    style = look["hairstyle"]
    parts = []
    if style == "bob":
        parts.append(("hair-back", hair, "m 70 384 b 54 220 96 100 200 100 b 304 100 346 220 330 384 "
                                          "b 304 396 290 396 280 384 l 120 384 b 110 396 96 396 70 384"))
    parts.append(("ears", skin, _ellipse(94, 262, 20, 26) + " " + _ellipse(306, 262, 20, 26)))
    parts.append(("ear-shade", shade, _ellipse(96, 264, 9, 14) + " " + _ellipse(304, 264, 9, 14)))
    parts.append(("face", skin, "m 200 128 b 268 128 308 172 308 248 b 308 330 266 398 200 398 "
                                "b 134 398 92 330 92 248 b 92 172 132 128 200 128"))
    parts.append(("blush", "E07A6A&\\1a&H90", _ellipse(138, 318, 20, 10) + " " + _ellipse(262, 318, 20, 10)))
    parts.append(("nose", shade, "m 197 286 b 191 302 188 312 197 317 l 208 317 b 214 313 210 305 205 300"))
    if look["beard"]:
        parts.append(("beard", hair, "m 96 268 b 100 342 140 406 200 406 b 260 406 300 342 304 268 "
                                     "b 290 322 266 354 236 362 b 220 348 180 348 164 362 b 134 354 110 322 96 268"))
        parts.append(("moustache", hair, "m 166 331 b 184 318 216 318 234 331 b 220 337 180 337 166 331"))
    openness = pose["open"]
    gx, gy = pose["gaze"]
    if openness < .15:
        def lid(x):
            return f"m {x-24} 262 b {x-10} 276 {x+10} 276 {x+24} 262 b {x+10} 282 {x-10} 282 {x-24} 262"
        parts.append(("lids", "2A1E1A", lid(160) + " " + lid(240)))
    else:
        ry = 19 * openness
        parts.append(("eyes", "FFFFFF", _ellipse(160, 262, 24, ry) + " " + _ellipse(240, 262, 24, ry)))
        pr = min(11, ry)
        parts.append(("pupils", "2A1E1A", _ellipse(160 + gx, 262 + gy, 11, pr) + " " +
                      _ellipse(240 + gx, 262 + gy, 11, pr)))
        if openness > .5:
            parts.append(("shine", "FFFFFF", _ellipse(165 + gx, 257 + gy, 3.5, 3.5) + " " +
                          _ellipse(245 + gx, 257 + gy, 3.5, 3.5)))
    parts.extend(_mouth(pose))
    if style == "quiff":
        parts.append(("hair", hair, "m 88 250 b 74 150 128 92 206 92 b 286 92 334 148 314 252 "
                                    "b 306 214 292 190 270 176 b 240 192 180 196 140 176 b 116 192 98 214 88 250"))
        parts.append(("quiff", hair, "m 118 152 b 128 70 230 38 302 90 b 318 102 324 124 320 142 "
                                     "b 292 112 240 110 200 138 b 175 125 140 132 118 152"))
        parts.append(("streak", accent, "m 178 98 b 220 60 284 64 308 100 b 282 88 236 92 206 118 "
                                        "b 198 110 190 104 178 98"))
    elif style == "short":
        parts.append(("hair", hair, "m 92 238 b 86 150 136 104 200 104 b 266 104 316 150 308 238 "
                                    "b 298 196 270 168 200 166 b 130 168 102 196 92 238"))
    else:
        parts.append(("bangs", hair, "m 90 252 b 80 150 130 102 204 102 b 280 102 324 150 312 252 "
                                     "b 302 200 282 176 252 166 b 230 196 170 200 118 182 b 102 200 94 222 90 252"))
        parts.append(("clip", accent, _rrect(256, 150, 34, 12, 6)))
    raise_, tilt = pose["brow"]
    parts.append(("brows", hair if style != "bob" else _darker(hair, .8),
                  _brow(160, 226, raise_, tilt, False) + " " + _brow(240, 226, raise_, tilt, True)))
    if look["glasses"]:
        ring = (_ellipse(160, 262, 37, 30) + " " + _ellipse(160, 262, 32, 25, reverse=True) + " " +
                _ellipse(240, 262, 37, 30) + " " + _ellipse(240, 262, 32, 25, reverse=True))
        parts.append(("glasses", "1C1C22", ring + " " + _rrect(196, 252, 8, 6, 3) + " " +
                      _rrect(88, 254, 36, 5, 2) + " " + _rrect(276, 254, 36, 5, 2)))
        parts.append(("lens", "FFFFFF&\\1a&HD8", _ellipse(160, 262, 32, 25) + " " + _ellipse(240, 262, 32, 25)))
    return parts


# --- drivers ---------------------------------------------------------------------------

def speech_levels(path: Path | str | None, duration: float) -> list[float] | None:
    """Loudness per animation frame, normalized to 0..1; None for silent tracks."""
    try:
        with wave.open(str(path), "rb") as audio:
            if audio.getsampwidth() != 2 or audio.getnchannels() != 1:
                return None
            rate = audio.getframerate()
            samples = array("h")
            samples.frombytes(audio.readframes(audio.getnframes()))
    except (OSError, wave.Error, EOFError, TypeError):
        return None
    window = max(1, rate // FPS)
    levels = []
    for index in range(math.ceil(duration * FPS)):
        chunk = samples[index * window:(index + 1) * window]
        levels.append(math.sqrt(sum(v * v for v in chunk[::4]) / max(1, len(chunk[::4]))) if chunk else 0.0)
    loud = sorted(value for value in levels if value > 30)
    if len(loud) < 3:
        return None
    reference = loud[min(len(loud) - 1, int(len(loud) * .9))]
    return [min(1.0, value / reference) for value in levels]


def _text_level(t: float, spans) -> tuple[float, str]:
    for start, end, text in spans:
        if start <= t < end and text:
            index = min(len(text) - 1, int((t - start) / max(.01, end - start) * len(text)))
            return (.05 if not text[index].isalpha() else .45 + .45 * abs(math.sin(t * 17.3))), text
    return 0.0, ""


def _viseme(t: float, spans) -> str:
    for start, end, text in spans:
        if start <= t < end and text:
            lowered = text.lower()
            index = min(len(lowered) - 1, int((t - start) / max(.01, end - start) * len(lowered)))
            if lowered[index] in "mbp":
                return "X"
            if lowered[index] in "fv":
                return "F"
            for offset in (0, 1, -1, 2, -2):
                character = lowered[min(len(lowered) - 1, max(0, index + offset))]
                if character in _VOWELS:
                    return _VOWELS[character]
            return "B"
    return "X"


def _ease_out_back(p: float) -> float:
    p = max(0.0, min(1.0, p)) - 1
    return 1 + 2.4 * p ** 3 + 1.4 * p ** 2


class Rig:
    """Evaluates the puppet's pose for any timestamp."""

    def __init__(self, seed: str, spans, scenes, duration: float, levels: list[float] | None,
                 roam: bool = False):
        self.spans, self.scenes, self.duration = spans, scenes, duration
        rng = random.Random(zlib.crc32(seed.encode("utf-8")))
        self.roam = roam
        self.perches = sorted(perch for scene in scenes for perch in scene.get("perch", ()))
        # Birds move their heads in quick discrete snaps rather than smooth sways.
        self.snaps, cursor = [(0.0, 0.0)], 0.0
        while cursor < duration:
            cursor += rng.uniform(.45, 1.1)
            self.snaps.append((cursor, rng.choice((-16, -9, -4, 0, 5, 10, 17))))
        self.hops, cursor = [], rng.uniform(1.5, 2.5)
        while cursor < duration:
            self.hops.append(cursor)
            cursor += rng.uniform(2.2, 4.0)
        self.levels = levels
        self.blinks, cursor = [], rng.uniform(.8, 1.8)
        while cursor < duration:
            self.blinks.append(cursor)
            cursor += rng.uniform(2.2, 4.6)
        self.gazes, cursor = [], 0.0
        while cursor < duration:
            choice = rng.random()
            target = (0, 0) if choice < .55 else (rng.choice((-6, 6)), rng.choice((-3, 0, 2)))
            self.gazes.append((cursor, target, choice))
            cursor += rng.uniform(1.1, 2.6)
        self.emphasis = []
        for start, end, text in spans:
            if text.rstrip().endswith(("?", "!")):
                self.emphasis.append((start + (end - start) * .55, 1.0))
        self.sides = [rng.choice((-1, 1)) for _ in scenes]

    def level(self, t: float) -> float:
        if self.levels:
            index = int(t * FPS)
            return self.levels[index] if 0 <= index < len(self.levels) else 0.0
        return _text_level(t, self.spans)[0]

    def smooth_level(self, t: float) -> float:
        return sum(self.level(t + d / FPS) for d in (-2, -1, 0, 1, 2)) / 5

    def scene_index(self, t: float) -> int:
        for index, scene in enumerate(self.scenes):
            if scene["start"] <= t < scene["end"]:
                return index
        return len(self.scenes) - 1

    def flight(self, t: float):
        """Feet position, scale and flight progress (None while perched)."""
        if not self.perches:
            return None
        index = max([i for i, perch in enumerate(self.perches) if perch[0] <= t], default=0)
        at, x, y, scale = self.perches[index]
        since = t - at
        if index == 0:
            origin = (x + 320, -260.0, scale)
            since = max(since, t - at)
        else:
            origin = self.perches[index - 1][1:]
        if since < FLIGHT and (index > 0 or t < at + FLIGHT):
            p = max(0.0, since) / FLIGHT
            eased = p * p * (3 - 2 * p)
            fx = origin[0] + (x - origin[0]) * eased
            fy = origin[1] + (y - origin[1]) * eased - 170 * math.sin(math.pi * p) * max(.35, scale)
            fs = origin[2] + (scale - origin[2]) * eased
            return fx, fy, fs, p, x - origin[0]
        hop = 0.0
        for start in self.hops:
            if 0 <= t - start < .3 and start - at > FLIGHT:
                hop = 26 * math.sin(math.pi * (t - start) / .3) * scale
        landing = since - FLIGHT
        bounce = 14 * scale * math.exp(-landing * 9) * math.sin(landing * 30) if 0 <= landing < .6 else 0
        return x, y - hop + bounce, scale, None, 0.0

    def pose(self, t: float) -> dict:
        index = self.scene_index(t)
        scene = self.scenes[index]
        since = t - scene["start"]
        level, energy = self.level(t), self.smooth_level(t)
        kick = math.exp(-since / .45) if since >= 0 else 0
        for at, strength in self.emphasis:
            if 0 <= t - at < 1.2:
                kick = max(kick, strength * math.exp(-(t - at) / .5))
        angle = (2.2 * math.sin(t * 2 * math.pi / 3.7) + 1.2 * math.sin(t * 2 * math.pi / 1.9 + 1)
                 + self.sides[index] * 6 * kick + 1.5 * energy * math.sin(t * 8.2))
        bob = -3 * math.sin(t * 2 * math.pi / 2.6) - 6 * energy
        openness = 1.0
        for blink in self.blinks:
            if 0 <= t - blink < .09:
                openness = 0.0
            elif .09 <= t - blink < .17:
                openness = .4
        gaze = (0, 0)
        for start, target, choice in self.gazes:
            if start <= t:
                gaze = target
                if scene.get("host") == "pip" and choice > .7:
                    gaze = (-6, -4)
        if level < .12:
            mouth = ("X", 0, 0)
        else:
            kind = _viseme(t, self.spans)
            if kind == "X":
                mouth = ("X", 0, 0)
            else:
                w, h = VISEMES[kind]
                mouth = (kind, w * (1 + .2 * level), h * (.55 + .8 * min(1.0, level)))
        brow_raise = min(1.2, .15 + .45 * energy + .9 * kick + (.35 if scene.get("host") == "big" else 0))
        brow_tilt = 4 + 6 * kick
        wave_angle = None
        if scene.get("wave") and since < 1.6:
            wave_angle = 16 * math.sin(since * 2 * math.pi * 2.2)
        pose = {"level": level, "angle": angle, "bob": bob, "open": openness, "gaze": gaze, "mouth": mouth,
                "brow": (brow_raise, brow_tilt), "wave": wave_angle, "mode": scene.get("host", "big"),
                "since": since, "head_dy": 0.0, "wings": (0.0, 0.0), "tilt": 0.0}
        if self.roam:
            flight = self.flight(t)
            if flight:
                fx, fy, fs, progress, dx = flight
                pose["roam"] = (fx, fy, fs)
                snap = 0.0
                for at, target in self.snaps:
                    if at <= t:
                        previous, snap, snap_at = snap, target, at
                pose["angle"] = previous + (snap - previous) * min(1.0, (t - snap_at) / .07) + 3 * energy * math.sin(t * 9)
                caw = min(1.0, energy * 1.4)
                pose["bob"] = -4 * energy
                pose["gaze"] = (-6 if fx > 380 else 6 if fx < 340 else 0, gaze[1])
                # A side-profile bird faces the content: right-hand perches look left.
                face = -1 if fx > 420 else 1
                pose["perched"] = progress is None
                if progress is not None:
                    face = -1 if dx < 0 else 1
                    flap = 95 * (.5 + .5 * math.sin(progress * 2 * math.pi * 3.5))
                    pose["wings"] = (flap, flap)
                    # Pitch forward into the flight direction.
                    pose["tilt"] = -face * 14 * math.sin(math.pi * progress)
                    pose["wave"] = None
                else:
                    landed = min(t - perch_at for perch_at, *_ in self.perches if perch_at <= t) - FLIGHT
                    if 0 <= landed < .9:
                        # Settle the wings, then peck at whatever it landed on.
                        pose["wings"] = (40 * math.exp(-landed * 8), 40 * math.exp(-landed * 8))
                        if .25 <= landed < .55:
                            # Peck: the head dips forward and down.
                            peck = math.sin(math.pi * (landed - .25) / .3)
                            pose["head_dy"] = 18 * peck
                            pose["angle"] -= face * 30 * peck
                pose["face"] = face
                if pose["perched"]:
                    # Caw: the head tips up while the bird talks loudly.
                    pose["angle"] += face * 16 * caw
        return pose


FLIGHT = .55  # Seconds a roaming host takes to fly between perches.

PLACEMENTS = {
    # Local origin and scale per mode; PiP sits in the lower-right badge.
    "big": (180.0, 452.0, .9),
    "pip": (520.0, 704.0, .42),
}
PIP_CIRCLE = (604.0, 822.0, 100.0)


def placement(pose: dict, placements: dict | None = None) -> tuple[float, float, float]:
    x, y, scale = (placements or PLACEMENTS)[pose["mode"]]
    entrance = (1 - _ease_out_back(pose["since"] / .45)) * 300 * scale
    return x, y + entrance, scale


def svg_path(drawing: str) -> str:
    """Convert our ASS-style drawing commands (m/l/b) to an SVG path."""
    return drawing.replace("m ", "M ").replace("l ", "L ").replace("b ", "C ")


def svg_track(*, look_id: str, accent_for, spans, scenes, duration: float, levels: list[float] | None, seed: str,
              placements: dict | None = None, pip_circle: tuple | None = None, fps: int = 24) -> dict:
    """The rig sampled per video frame for the Remotion composition.

    Paths are de-duplicated into ``paths``; each frame lists groups (body, head)
    with an SVG transform in local character coordinates and parts as
    [path index, fill, opacity, glow, stroke, clip]. ``clip`` marks frames shown
    inside the round picture-in-picture badge.
    """
    look = LOOKS[look_id]
    roam = bool(look.get("roam")) and any(scene.get("perch") for scene in scenes)
    rig = Rig(seed, spans, scenes, duration, levels, roam=roam)
    feet_x, feet_y = look.get("feet", (200.0, 560.0))
    pivot = look.get("pivot", PIVOT)
    glow = look.get("glow", set())
    outline = look.get("outline")
    outlined = look.get("outlined", set())
    paths: list[str] = []
    index_of: dict[str, int] = {}
    frames = []

    def path_id(drawing: str) -> int:
        converted = svg_path(drawing)
        if converted not in index_of:
            index_of[converted] = len(paths)
            paths.append(converted)
        return index_of[converted]

    for number in range(max(1, math.ceil(duration * fps))):
        t = number / fps
        pose = rig.pose(t)
        if pose["mode"] == "off" and not (roam and "roam" in pose):
            frames.append(None)
            continue
        if roam and "roam" in pose:
            fx, fy, scale = pose["roam"]
            x0, y0 = fx - feet_x * scale, fy - feet_y * scale
        else:
            x0, y0, scale = placement(pose, placements)
        accent = accent_for(rig.scene_index(t))
        body_y = pose["bob"] * .5 * scale
        head_y = pose["bob"] * scale + pose["head_dy"] * scale
        groups = []
        for parts, offset, rotation in (
                (body_parts(look, accent, pose), body_y,
                 f"rotate({_n(-pose['tilt'])} {_n(feet_x)} {_n(feet_y)})" if pose["tilt"] else ""),
                (head_parts(look, accent, pose), head_y,
                 f"rotate({_n(-(pose['angle'] + pose['tilt']))} {_n(pivot[0])} {_n(pivot[1])})")):
            items = []
            for name, color, drawing in parts:
                color, _, alpha = color.partition("&\\1a&H")
                opacity = round(1 - int(alpha, 16) / 255, 3) if alpha else 1
                stroke = outline if outline and name in outlined else ""
                items.append([path_id(drawing), color, opacity, int(name in glow), stroke])
            groups.append({"transform": f"translate({_n(x0)} {_n(y0 + offset)}) scale({_n(scale)}) {rotation}".strip(),
                           "parts": items})
        frames.append({"clip": pose["mode"] == "pip" and not roam, "groups": groups})
    cx, cy, radius = pip_circle or PIP_CIRCLE
    return {"fps": fps, "paths": paths, "frames": frames, "clip": [cx, cy, radius - 6]}
