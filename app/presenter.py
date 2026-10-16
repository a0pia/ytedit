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


def body_parts(look: dict, accent: str, wave_angle: float | None) -> list[tuple[str, str, str]]:
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


def head_parts(look: dict, accent: str, pose: dict) -> list[tuple[str, str, str]]:
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

    def __init__(self, seed: str, spans, scenes, duration: float, levels: list[float] | None):
        self.spans, self.scenes, self.duration = spans, scenes, duration
        rng = random.Random(zlib.crc32(seed.encode("utf-8")))
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
        return {"angle": angle, "bob": bob, "open": openness, "gaze": gaze, "mouth": mouth,
                "brow": (brow_raise, brow_tilt), "wave": wave_angle, "mode": scene.get("host", "big"),
                "since": since}


PLACEMENTS = {
    # Local origin and scale per mode; PiP sits in the lower-right badge.
    "big": (180.0, 452.0, .9),
    "pip": (520.0, 704.0, .42),
}
PIP_CIRCLE = (604.0, 822.0, 100.0)


def placement(pose: dict) -> tuple[float, float, float]:
    x, y, scale = PLACEMENTS[pose["mode"]]
    entrance = (1 - _ease_out_back(pose["since"] / .45)) * 300 * scale
    return x, y + entrance, scale


def _cs(seconds: float) -> int:
    return round(seconds * 100)


def _stamp(cs: int) -> str:
    whole, fraction = divmod(cs, 100)
    minutes, second = divmod(whole, 60)
    hour, minute = divmod(minutes, 60)
    return f"{hour}:{minute:02d}:{second:02d}.{fraction:02d}"


def puppet_events(*, look_id: str, accent_for, spans, scenes, duration: float,
                  levels: list[float] | None, seed: str, layer: int = 4) -> list[str]:
    """ASS events drawing the rig at FPS, interpolating translation between frames."""
    look = LOOKS[look_id]
    rig = Rig(seed, spans, scenes, duration, levels)
    total = _cs(duration)
    cuts = {_cs(scene["start"]) for scene in scenes} | {total}
    marks = sorted({round(i * 100 / FPS) for i in range(math.ceil(duration * FPS) + 1)} | cuts)
    marks = [mark for mark in marks if 0 <= mark <= total]
    events = []
    cx, cy, radius = PIP_CIRCLE
    pip_clip = rf"\clip({screen_circle(cx, cy, radius - 6)})"
    for a, b in zip(marks, marks[1:]):
        if b <= a:
            continue
        t0, t1 = a / 100, b / 100 - .001
        pose = rig.pose(t0)
        if rig.scene_index(t0) != rig.scene_index(t1):
            t1 = t0
        x0, y0, scale = placement(pose)
        x1, y1, _ = placement(rig.pose(t1))
        body_y, head_y = pose["bob"] * .5 * scale, pose["bob"] * scale
        accent = accent_for(rig.scene_index(t0))
        clip = pip_clip if pose["mode"] == "pip" else ""
        start, end = _stamp(a), _stamp(b)
        pivot_x, pivot_y = x0 + PIVOT[0] * scale, y0 + head_y + PIVOT[1] * scale
        common = rf"\bord0\shad0\fscx{_n(scale * 100)}\fscy{_n(scale * 100)}{clip}"
        groups = ((body_parts(look, accent, pose["wave"]), body_y, ""),
                  (head_parts(look, accent, pose), head_y,
                   rf"\org({_n(pivot_x)},{_n(pivot_y)})\frz{_n(pose['angle'])}"))
        for parts, offset, rotation in groups:
            move = rf"\move({_n(x0)},{_n(y0 + offset)},{_n(x1)},{_n(y1 + offset)})"
            for _name, color, path in parts:
                color, _, alpha = color.partition("&\\1a&H")
                alpha_tag = rf"\1a&H{alpha}&" if alpha else ""
                rgb = "&H" + color[4:6] + color[2:4] + color[0:2] + "&"
                events.append(f"Dialogue: {layer},{start},{end},Motion,,0,0,0,,"
                              f"{{\\an7{move}{rotation}{common}\\1c{rgb}{alpha_tag}\\p1}}{path}{{\\p0}}")
    return events
