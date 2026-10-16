"""Capsule: the dashboard video theme specified in docs/TEMA.md.

This module plans the video; the Remotion composition in ``remotion/`` draws it.
The plan holds the scenes and their palettes, the burned-in caption bursts with
per-word timing, the typography-map camera moments, the brand mark and the
host's per-frame SVG rig. Remotion renders two layers: a ``world`` the camera
moves over (panel, cards, host) and a still ``hud`` (frame, tab, chips, captions,
scene bar), so the viewer always has a fixed anchor.

Scene colours cycle: two accent palettes, then back to the main palette, so the
eye registers every cut. Every visible phrase still comes verbatim from the
script; chart waves are decoration only.
"""
from __future__ import annotations

import os

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


def build_plan(title: str, segments, scenes: list[dict], duration: float, host: dict | None,
               pack_id: str = "kapsul", brand: dict | None = None, fps: int = 24) -> dict:
    """Everything the Remotion composition needs to draw the video, as plain JSON.

    ``brand`` is {"name", "logo" (data URI or None), "stems"}: the story's brand gets
    a logo tile (or a wordmark pill) in the opening and on the "+" button of every
    scene that mentions it.
    """
    from .media import _fit_display

    pk = PACKS[pack_id]
    moments = emphasis_moments(segments, duration)
    stressed = {round(moment["start"], 3) for moment in moments}

    def scene_at(t):
        return next((scene for scene in scenes if scene["start"] <= t < scene["end"]), scenes[-1])

    planned = []
    count = len(scenes)
    for index, scene in enumerate(scenes):
        layout = scene["layout"]
        last = index == count - 1
        item = {"index": index, "start": scene["start"], "end": scene["end"], "layout": layout,
                "label": ("Son söz" if last else "Ara sahne") if layout == "host" else LABELS.get(layout, "Gündem"),
                "phrase": scene.get("phrase", ""), "host": scene.get("host") if host else None,
                "roaming": bool(host and scene.get("perch")), "palette": palette(index, pack_id),
                "brandHere": bool(brand and (layout == "hook" or any(
                    stem in scene.get("phrase", "").lower() for stem in brand["stems"])))}
        if layout == "hook":
            item["size"], item["text"] = _fit_display(title, sizes=(62, 56, 50, 44, 40, 36), width=600, lines=4,
                                                      height=190 if host else 520)
        elif layout == "host":
            item["size"], item["text"] = _fit_display(item["phrase"], sizes=(50, 46, 42, 38, 34, 30), width=548,
                                                      lines=5, height=170)
        elif layout in ("editorial", "card"):
            item["size"], item["text"] = _fit_display(item["phrase"], sizes=(52, 46, 42, 38, 34, 30), width=560,
                                                      lines=5, height=230 if layout == "editorial" else 250)
        elif layout == "keyword":
            item["keyword"] = keyword(item["phrase"])
            item["keywordSize"] = keyword_size(item["keyword"])
            item["size"], item["text"] = _fit_display(item["phrase"], sizes=(34, 30, 28, 26), width=600, lines=4,
                                                      height=170)
        elif layout == "quote":
            item["size"], item["text"] = _fit_display(item["phrase"], sizes=(54, 48, 44, 40, 36, 32), width=560,
                                                      lines=6, height=320)
        elif layout == "split":
            words = item["phrase"].split()
            half = max(1, len(words) // 2)
            parts = [" ".join(words[:half]), " ".join(words[half:])] if len(words) > 1 else [item["phrase"], ""]
            item["reveal"] = scene["start"] + (scene["end"] - scene["start"]) * .45
            item["parts"] = [{"size": size, "text": text} for size, text in
                             (_fit_display(part, sizes=(44, 40, 36, 32, 28), width=480, lines=3, height=150)
                              for part in parts if part)]
        else:
            item["size"], item["text"] = _fit_display(item["phrase"], sizes=(60, 54, 48, 44, 40, 36), width=600,
                                                      lines=6, height=380)
        planned.append(item)

    captions = []
    for number, (start, end, words, times) in enumerate(caption_chunks(segments)):
        finishes = times[1:] + [end]
        captions.append({"start": start, "end": end, "tilt": (-2.5, 1.5, -1, 2.5)[number % 4],
                         "words": [{"text": _upper(word), "start": at, "end": finish,
                                    "stressed": round(at, 3) in stressed}
                                   for word, at, finish in zip(words, times, finishes)]})

    camera = []
    for moment in moments:
        fx, fy, _extra = WIDGETS.get(scene_at(moment["start"])["layout"], (360, 480, .16))
        camera.append({"start": moment["start"], "end": moment["end"], "word": moment["word"],
                       "focus": [fx, fy], "strength": min(.2, .12 + .03 * moment["score"])})

    plan = {"fps": fps, "width": 720, "height": 1280, "duration": duration, "title": title, "brand": BRAND,
            "pack": {"frame": pk["frame"], "pop": pk["pop"], "cyber": bool(pk.get("cyber"))},
            "scenes": planned, "captions": captions, "camera": camera,
            "brandMark": {"name": brand["name"], "logo": brand.get("logo")} if brand else None, "host": None}
    if host:
        look = presenter.LOOKS[host["look"]]
        bird = look.get("kind") == "raven"
        plan["host"] = {
            "name": presenter.display_name(host["name"]), "pip": list(PIP_CIRCLE),
            "track": presenter.svg_track(
                look_id=host["look"], spans=host["spans"], scenes=scenes, duration=duration,
                accent_for=lambda index: palette(index, pack_id)["bird" if bird else "accent"],
                levels=host.get("levels"), seed=title, placements=PLACEMENTS, pip_circle=PIP_CIRCLE, fps=fps)}
    return plan
