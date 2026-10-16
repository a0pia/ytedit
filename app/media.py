"""Local, free video production. No network calls unless ElevenLabs is selected."""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
from functools import lru_cache
import re
import selectors
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
import urllib.error
import urllib.request
import unicodedata
import wave
from typing import Callable


class MediaError(RuntimeError):
    """A user-actionable production error."""


MAX_SCRIPT_LENGTH = 1200
MAX_DURATION = 90.0
SAMPLE_RATE = 24000


def _run(command: list[str], *, timeout: int = 60, cwd: Path | None = None,
         env: dict | None = None) -> subprocess.CompletedProcess:
    try:
        result = subprocess.run(command, capture_output=True, timeout=timeout,
                                cwd=cwd, env=env, check=False)
    except subprocess.TimeoutExpired as exc:
        raise MediaError("Medya işlemi zaman aşımına uğradı. Metni kısaltıp yeniden deneyin.") from exc
    except OSError as exc:
        raise MediaError(f"Medya aracı çalıştırılamadı: {Path(command[0]).name}.") from exc
    if result.returncode:
        # Only local programs go through this helper; secrets never enter their arguments.
        detail = result.stderr.decode("utf-8", errors="replace")[-1200:]
        raise MediaError(f"{Path(command[0]).name} işlemi başarısız: {detail}")
    return result


def _file_stamp(path: str | None) -> tuple:
    try:
        info = Path(path).stat()
        return (info.st_mtime_ns, info.st_size)
    except (OSError, TypeError):
        return ()


@lru_cache(maxsize=16)
def _say_voices(binary: str, stamp: tuple, cache_epoch: int = 0) -> tuple[str, ...]:
    listing = _run([binary, "-v", "?"], timeout=10).stdout.decode("utf-8", errors="replace")
    voices = []
    for line in listing.splitlines():
        match = re.match(r"^(.+?)\s+tr[_-]TR\b", line)
        if match:
            voices.append(match.group(1).strip())
    return tuple(voices)


@lru_cache(maxsize=32)
def _espeak_voice_error(binary: str, stamp: tuple, voice: str, data: str, libraries: str, cache_epoch: int = 0) -> str:
    environment = dict(os.environ)
    if data:
        environment["ESPEAK_DATA_PATH"] = data
    if libraries:
        environment["LD_LIBRARY_PATH"] = libraries
    try:
        # -q synthesizes without opening an audio device or writing a file.
        _run([binary, "-q", "-v", voice, "Merhaba"], timeout=10, env=environment)
        if "+" in voice:
            variant = voice.rsplit("+", 1)[1]
            listing = _run([binary, "--voices=variant"], timeout=10, env=environment).stdout.decode("utf-8", errors="replace")
            if not any(line.split()[4].rsplit("/", 1)[-1] == variant for line in listing.splitlines()[1:] if len(line.split()) >= 5):
                return "LOCAL_TTS_VOICE içinde seçilen ses varyantı kurulu değil. Varsayılan Türkçe ses için tr kullanın."
    except MediaError:
        return "Seçilen yerel ses çalıştırılamadı. LOCAL_TTS_VOICE ayarını ve ses paketlerini kontrol edin; Türkçe için tr kullanın."
    return ""


def _local_engine() -> dict:
    requested = os.environ.get("LOCAL_TTS_VOICE", "").strip()
    say = shutil.which("say") if sys.platform == "darwin" else None
    if say:
        try:
            turkish = _say_voices(say, _file_stamp(say), int(time.monotonic() // 15))
        except MediaError:
            turkish = ()
        voice = requested if requested in turkish else next((v for v in turkish if v == "Yelda"), turkish[0] if turkish else "")
        if voice and (not requested or requested in turkish):
            return {"binary": say, "provider": "macOS say", "voice": voice, "env": None, "error": ""}
        if requested and requested != "tr":
            return {"binary": None, "provider": "macOS say", "voice": requested, "env": None,
                    "error": "LOCAL_TTS_VOICE için seçilen Türkçe ses kurulu değil. Sistem Ayarları’ndan bu sesi indirin veya ayarı kaldırın."}
        # A Mac without a downloaded Turkish system voice may still have eSpeak.
    binary = shutil.which("espeak-ng") or shutil.which("espeak")
    environment = None
    candidates = [Path(__file__).resolve().parents[2] / ".tools" / "espeak"]
    if os.environ.get("LOCAL_TTS_ROOT"):
        candidates.insert(0, Path(os.environ["LOCAL_TTS_ROOT"]).expanduser())
    if not binary and sys.platform.startswith("linux"):
        for root in candidates:
            candidate = root / "usr" / "bin" / "espeak-ng"
            if candidate.is_file():
                binary = str(candidate)
                environment = dict(os.environ)
                library_dirs = sorted(path for path in (root / "usr" / "lib").glob("*-linux-gnu") if path.is_dir())
                library_dirs.append(root / "usr" / "lib")
                environment["LD_LIBRARY_PATH"] = ":".join(map(str, library_dirs)) + (":" + os.environ["LD_LIBRARY_PATH"] if os.environ.get("LD_LIBRARY_PATH") else "")
                data_dirs = [path / "espeak-ng-data" for path in library_dirs] + [root / "usr" / "share" / "espeak-ng-data"]
                data_dir = next((path for path in data_dirs if path.is_dir()), None)
                if data_dir:
                    environment["ESPEAK_DATA_PATH"] = str(data_dir)
                break
    voice = requested or "tr"
    error = "Yerel Türkçe ses bulunamadı. Mac’te Yelda sesini indirin veya brew install espeak-ng çalıştırın; Linux’ta espeak-ng kurun."
    if binary:
        variables = environment or os.environ
        error = _espeak_voice_error(binary, _file_stamp(binary), voice, variables.get("ESPEAK_DATA_PATH", ""), variables.get("LD_LIBRARY_PATH", ""), int(time.monotonic() // 15))
    return {"binary": binary if not error else None, "provider": "eSpeak NG" if binary and "espeak-ng" in binary else "eSpeak",
            "voice": voice, "env": environment, "error": error}


@lru_cache(maxsize=8)
def _ffmpeg_probe(binary: str, stamp: tuple, probe: str, probe_stamp: tuple, cache_epoch: int = 0) -> dict:
    try:
        encoders = _run([binary, "-hide_banner", "-encoders"], timeout=10).stdout.decode("utf-8", errors="replace")
        filters = _run([binary, "-hide_banner", "-filters"], timeout=10).stdout.decode("utf-8", errors="replace")
        _run([probe, "-version"], timeout=10)
    except MediaError:
        return {"ready": False, "error": "FFmpeg araçları çalıştırılamadı. FFmpeg kurulumunu ve çalıştırma izinlerini kontrol edin.", "features": {}}
    features = {"h264": bool(re.search(r"\blibx264\s", encoders)), "aac": bool(re.search(r"\baac\s", encoders)),
                "subtitles": bool(re.search(r"\bass\s+V->V", filters)), "zoompan": bool(re.search(r"\bzoompan\s+V->V", filters))}
    missing = [name for name, ready in features.items() if not ready]
    error = ("FFmpeg kurulumunda eksik özellikler: " + ", ".join(missing) + ". libass ve libx264 destekli FFmpeg kurun; Mac’te brew reinstall ffmpeg kullanın.") if missing else ""
    return {"ready": not missing, "error": error, "features": features}


def _ffmpeg_state() -> dict:
    binary, probe = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if not binary or not probe:
        return {"ready": False, "error": "FFmpeg bulunamadı. Mac’te brew install ffmpeg komutunu çalıştırıp uygulamayı yeniden başlatın.", "features": {}}
    return _ffmpeg_probe(binary, _file_stamp(binary), probe, _file_stamp(probe), int(time.monotonic() // 15))


def capabilities() -> dict:
    engine = _local_engine()
    available = bool(engine["binary"])
    ffmpeg = _ffmpeg_state()
    return {
        "ffmpeg": ffmpeg["ready"],
        "ffmpeg_error": ffmpeg["error"],
        "ffmpeg_features": dict(ffmpeg["features"]),
        "tts": available,
        "tts_error": engine.get("error", ""),
        "voice": engine["voice"] if available else "",
        "provider": engine["provider"] if available else "Kurulu değil",
        "elevenlabs": bool(os.environ.get("ELEVENLABS_API_KEY") and os.environ.get("ELEVENLABS_VOICE_ID")),
        "subtitle_timing": "Cümlelerin gerçek ses sürelerinden üretilir",
        "local_tts_help": "Mac: Sistem Ayarları → Erişilebilirlik → Okunan İçerik → Sistem Sesi bölümünden Türkçe Yelda sesini indirin. Linux: espeak-ng kurun.",
    }


def _sentences(script: str) -> list[str]:
    # Preserve decimals, initials and common Turkish/news abbreviations so they do
    # not gain a new synthesized pause and an independent subtitle interval.
    honorifics = {"dr", "prof", "doç", "yrd", "sn", "say", "av", "arş", "öğr"}
    abbreviations = {"vb", "vs", "vd", "bkz", "örn", "yak", "no", "ltd", "inc", "a.ş", "tic", "san"}
    pieces = []
    for paragraph in script.splitlines():
        paragraph = paragraph.strip()
        start = 0
        for match in re.finditer(r"[.!?…]+[\"”’')\]]*(?:\s+|$)", paragraph):
            candidate = paragraph[start:match.end()].strip()
            remainder = paragraph[match.end():].lstrip()
            last = candidate.split()[-1].strip("\"“”‘’'()[]").rstrip(".") if candidate else ""
            next_lowercase = bool(remainder and remainder[0].islower())
            if remainder and (last.lower() in honorifics or (last.lower() in abbreviations and next_lowercase)
                              or (len(last) == 1 and last.isupper()) or (last.isdigit() and len(last) <= 2 and next_lowercase)):
                continue
            if candidate:
                pieces.append(candidate)
            start = match.end()
        if paragraph[start:].strip():
            pieces.append(paragraph[start:].strip())
    return pieces


def _glyph_width(character: str) -> float:
    """Conservative em widths for Arial/DejaVu, including wide Unicode glyphs."""
    if unicodedata.combining(character):
        return 0.0
    if unicodedata.east_asian_width(character) in ("W", "F"):
        return 1.1
    if character in "MW@%wm":
        return 1.1
    if character in " iljft.,':;!|ı":
        return .38
    return .85 if character.isupper() else .67


def _wrap_lines(text: str, characters: int, em_width: float) -> list[str]:
    """Wrap at words while breaking long tokens before they leave the safe area."""
    result: list[str] = []
    for initial in textwrap.wrap(text, width=characters, break_long_words=True, break_on_hyphens=False):
        remaining = initial
        while remaining:
            width = 0.0
            boundary = len(remaining)
            for index, character in enumerate(remaining):
                width += _glyph_width(character)
                if width > em_width:
                    boundary = max(1, index)
                    break
            if boundary < len(remaining):
                last_space = remaining.rfind(" ", 0, boundary + 1)
                if last_space > 0:
                    boundary = last_space
            result.append(remaining[:boundary].strip())
            remaining = remaining[boundary:].lstrip()
    return result


def _subtitle_chunks(sentence: str) -> list[str]:
    lines = _wrap_lines(sentence, characters=27, em_width=600 / 44)
    return ["\n".join(lines[i:i + 2]) for i in range(0, len(lines), 2)]


def _timestamp(seconds: float, ass: bool = False) -> str:
    ticks = round(seconds * (100 if ass else 1000))
    unit = 100 if ass else 1000
    whole, fraction = divmod(ticks, unit)
    minutes, second = divmod(whole, 60)
    hour, minute = divmod(minutes, 60)
    return f"{hour}:{minute:02d}:{second:02d}.{fraction:02d}" if ass else f"{hour:02d}:{minute:02d}:{second:02d},{fraction:03d}"


def _ass_escape(text: str) -> str:
    return text.replace("\\", "＼").replace("{", "｛").replace("}", "｝").replace("\r", "").replace("\n", r"\N")


def _title_layout(title: str) -> tuple[int, str]:
    title = " ".join(title.split())
    # Reserve a compact block for the complete headline instead of letting it
    # dominate the entire frame. Mark truncation rather than dropping words.
    for size in (46, 42, 38, 34, 30):
        lines = _wrap_lines(title, characters=34, em_width=570 / size)
        if len(lines) <= 4:
            return size, "\n".join(lines)
    last = lines[3].rstrip()
    while last and sum(map(_glyph_width, last + "…")) > 570 / 30:
        last = last[:-1].rstrip()
    return 30, "\n".join(lines[:3] + [last + "…"])


def _fit_display(text: str, *, sizes: tuple[int, ...], width: int = 590, lines: int = 4,
                 height: int = 430) -> tuple[int, str]:
    for size in sizes:
        wrapped = _wrap_lines(" ".join(text.split()), characters=38, em_width=width / size)
        orphan = len(wrapped) > 1 and len(wrapped[-1].strip(".,!?…:; ")) < 3
        if len(wrapped) <= lines and len(wrapped) * size * 1.2 <= height and not orphan:
            return size, "\n".join(wrapped)
    if len(wrapped) <= lines:
        return size, "\n".join(wrapped)
    tail = wrapped[lines - 1].rstrip()
    while tail and sum(map(_glyph_width, tail + "…")) > width / size:
        tail = tail[:-1].rstrip()
    return size, "\n".join(wrapped[:lines - 1] + [tail + "…"])


def _source_phrase(sentence: str, position: float = .5) -> str:
    """An exact contiguous source excerpt, never a generated fact or statistic."""
    normalized = " ".join(sentence.split())
    matches = list(re.finditer(r"\S+", normalized))
    if len(normalized) <= 82 or len(matches) <= 7:
        return normalized
    center = min(len(matches) - 1, max(0, int(position * len(matches))))
    start = max(0, min(center - 3, len(matches) - 7))
    end = min(len(matches), start + 9)
    while end - start > 4 and matches[end - 1].end() - matches[start].start() > 90:
        end -= 1
    return normalized[matches[start].start():matches[end - 1].end()]


def _kinetic_plan(duration: float, spans: list[tuple[float, float, str]]) -> list[dict]:
    hook = min(2.6, duration * .45)
    remaining = duration - hook
    count = max(1, round(remaining / 3.6))
    scenes = [{"start": 0.0, "end": hook, "layout": "hook", "phrase": ""}]
    for index in range(count):
        start = hook + remaining * index / count
        end = duration if index == count - 1 else hook + remaining * (index + 1) / count
        span = max(spans, key=lambda item: max(0, min(end, item[1]) - max(start, item[0])))
        relative = max(0.0, min(1.0, ((start + end) / 2 - span[0]) / max(.01, span[1] - span[0])))
        scenes.append({"start": start, "end": end, "layout": ("editorial", "card", "statement")[index % 3],
                       "phrase": _source_phrase(span[2], relative)})
    return scenes


def _ass_rgb(hexadecimal: str) -> str:
    return "&H" + hexadecimal[4:6] + hexadecimal[2:4] + hexadecimal[0:2] + "&"


def _round_rect(width: int, height: int, radius: int = 20) -> str:
    r, w, h = radius, width, height
    return (f"m {r} 0 l {w-r} 0 b {w} 0 {w} 0 {w} {r} l {w} {h-r} "
            f"b {w} {h} {w} {h} {w-r} {h} l {r} {h} b 0 {h} 0 {h} 0 {h-r} "
            f"l 0 {r} b 0 0 0 0 {r} 0")


def _circle(radius: int) -> str:
    r, k = radius, round(radius * .5523)
    return (f"m {r} 0 b {r+k} 0 {2*r} {r-k} {2*r} {r} "
            f"b {2*r} {r+k} {r+k} {2*r} {r} {2*r} "
            f"b {r-k} {2*r} 0 {r+k} 0 {r} b 0 {r-k} {r-k} 0 {r} 0")


def _kinetic_events(title: str, segments: list[tuple[float, float, str]],
                    scenes: list[dict], duration: float, style: str) -> list[str]:
    """Original vector motion design. Every visible source phrase is verbatim."""
    events: list[str] = []
    colors = [("111B22", "C8FF58"), ("211737", "C2A3FF"),
              ("33201E", "FFB584"), ("122B33", "81DEFF")]
    if style == "sunset":
        colors = [colors[2], colors[1], colors[3], colors[0]]

    def event(start, end, layer, tags, content):
        events.append(f"Dialogue: {layer},{_timestamp(start, True)},{_timestamp(end, True)},Motion,,0,0,0,,{{{tags}}}{content}")

    def shape(start, end, layer, path, color, placement, extra="", alpha="00"):
        event(start, end, layer, rf"\an7\bord0\shad0\1c{_ass_rgb(color)}\1a&H{alpha}&{placement}{extra}\p1", path + r"{\p0}")

    def text(start, end, content, x, y, size, color="FFFFFF", align=7, extra="", layer=6):
        event(start, end, layer, rf"\an{align}\pos({x},{y})\fs{size}\1c{_ass_rgb(color)}\bord0\shad0{extra}", _ass_escape(content))

    for index, scene in enumerate(scenes):
        start, end = scene["start"], scene["end"]
        milliseconds = max(1, round((end - start) * 1000))
        base, accent = colors[index % len(colors)]
        layout = scene["layout"]
        shape(start, end, 0, "m 0 0 l 720 0 720 1280 0 1280", base, r"\pos(0,0)")
        # Independently moving oversized geometry makes the canvas move even
        # between typography entrances. Shapes are generated locally as vectors.
        shape(start, end, 1, _circle(220), accent,
              rf"\move(480,-140,350,40,0,{milliseconds})", alpha="D5")
        shape(start, end, 1, "m 0 0 l 200 0 200 200 0 200", accent,
              rf"\move(-140,650,70,720,0,{milliseconds})", rf"\frz-28\t(0,{milliseconds},\frz18)", "C0")
        shape(start, end, 1, _round_rect(390, 100, 48), accent,
              rf"\move(430,760,285,680,0,{milliseconds})", rf"\frz-24\t(0,{milliseconds},\frz-8)", "C8")
        for grid_y in (320, 520, 720, 920):
            shape(start, end, 1, "m 0 0 l 720 0 720 1 0 1", "FFFFFF", rf"\pos(0,{grid_y})", alpha="F0")

        text(start, end, "HYPE / TEKNOLOJİ", 60, 104, 21, accent, extra=r"\fsp3\fad(80,100)")
        text(start, end, f"{index+1:02d} / {len(scenes):02d}", 660, 104, 20, "FFFFFF", 9,
             extra=r"\1a&H55&\fad(80,100)")
        if layout == "hook":
            text(start, end, "BUGÜNÜN KONUSU", 62, 225, 21, accent, extra=r"\fsp2\fad(0,160)")
            size, fitted = _fit_display(title, sizes=(88, 80, 72, 64, 56, 48), width=585, lines=4)
            line_height = round(size * 1.14)
            for line_number, line in enumerate(fitted.splitlines()):
                delay = min(.10 * line_number, (end - start) * .15)
                y = 330 + line_number * line_height
                # Lines enter separately with a quick overshoot; user-provided
                # ASS control syntax is always escaped before reaching libass.
                event(start + delay, end, 6,
                      rf"\an7\move(92,{y+30},60,{y},0,380)\fs{size}\1c&HFFFFFF&\bord0\shad0\fscx108\fscy108\t(0,330,\fscx100\fscy100)\fad(0,140)",
                      _ass_escape(line))
            shape(start, end, 3, _round_rect(160, 10, 5), accent, r"\pos(62,825)",
                  rf"\fscx0\t(0,480,\fscx100)\fad(0,120)")
        elif layout == "editorial":
            text(start, end, "ODAK NOKTASI", 62, 225, 20, accent, extra=r"\fsp2\fad(100,130)")
            size, fitted = _fit_display(scene["phrase"], sizes=(72, 64, 56, 50, 44, 38), width=585, lines=6, height=400)
            event(start, end, 6, rf"\an7\move(12,355,62,325,0,360)\fs{size}\1c&HFFFFFF&\bord0\shad0\fad(100,140)", _ass_escape(fitted))
            shape(start, end, 3, _round_rect(9, 370, 4), accent, r"\pos(28,320)", r"\fscy0\t(0,450,\fscy100)\fad(0,120)")
            for bar in range(5):
                shape(start, end, 3, _round_rect(28, 60 + bar * 20, 12), accent,
                      rf"\pos({64+bar*44},818)", rf"\fscy25\t({bar*70},{600+bar*70},\fscy100)\t(900,{milliseconds},\fscy55)", "44")
        elif layout == "card":
            shape(start, end, 3, _round_rect(600, 440, 34), accent,
                  r"\move(60,365,60,315,0,420)", r"\fad(90,140)")
            size, fitted = _fit_display(scene["phrase"], sizes=(64, 58, 52, 46, 40, 34), width=500, lines=6, height=280)
            text(start + .10, end, "GÜNDEMDE", 98, 350, 19, base, extra=r"\fsp3\fad(80,140)")
            text(start + .14, end, fitted, 360, 540, size, base, 5,
                 extra=r"\fscx96\fscy96\t(0,300,\fscx100\fscy100)\fad(90,140)")
            text(start + .20, end, "HYPE / GÜNDEM", 98, 702, 15, base, extra=r"\fsp1\1a&H55&\fad(90,140)")
        else:
            text(start, end, "YAKINDAN BAKIŞ", 62, 225, 20, accent, extra=r"\fsp2\fad(100,140)")
            shape(start, end, 3, "m 0 0 l 505 0 505 6 0 6", accent, r"\pos(62,302)",
                  rf"\fscx0\t(0,420,\fscx100)\fad(0,140)")
            size, fitted = _fit_display(scene["phrase"], sizes=(68, 60, 54, 48, 42, 36), width=580, lines=6, height=400)
            event(start, end, 6, rf"\an7\move(62,440,62,378,0,420)\fs{size}\1c{_ass_rgb(accent)}\bord0\shad0\fad(100,140)", _ass_escape(fitted))
            shape(start, end, 2, "m 0 0 l 70 0 70 70 0 70", accent,
                  rf"\move(520,790,570,720,0,{milliseconds})", rf"\frz0\t(0,{milliseconds},\frz90)", "77")

    # The captions remain tied to recorded sentence durations across all cuts.
    shape(0, duration, 7, _round_rect(624, 180, 24), "070B12", r"\pos(48,932)", alpha="30")
    for start, end, caption in segments:
        event(start, end, 9,
              r"\an2\pos(360,1084)\fs44\1c&HFFFFFF&\bord1.5\3c&H120B07&\shad0\fscx97\fscy97\t(0,100,\fscx100\fscy100)\fad(0,35)",
              _ass_escape(caption))
    accent = colors[0][1]
    shape(0, duration, 8, "m 0 0 l 600 0 600 4 0 4", "FFFFFF", r"\pos(60,1172)", alpha="D8")
    shape(0, duration, 9, "m 0 0 l 600 0 600 4 0 4", accent, r"\pos(60,1172)",
          rf"\fscx0\t(0,{round(duration*1000)},\fscx100)")
    return events


def _write_subtitles(output_dir: Path, title: str, segments: list[tuple[float, float, str]], duration: float,
                     *, scenes: list[dict] | None = None, style: str = "aurora") -> tuple[Path, Path]:
    subtitle_path = output_dir / "captions.srt"
    subtitle_path.write_text("\n\n".join(
        f"{i}\n{_timestamp(start)} --> {_timestamp(end)}\n{text}"
        for i, (start, end, text) in enumerate(segments, 1)) + "\n", encoding="utf-8")
    font = "Arial" if sys.platform == "darwin" else "DejaVu Sans"
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 720
PlayResY: 1280
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,{font},44,&H00FFFFFF,&H000000FF,&H00140F15,&H80000000,-1,0,0,0,100,100,0,0,1,3,1,2,48,48,270,1
Style: Title,{font},46,&H00FFFFFF,&H000000FF,&H00301B20,&H00000000,-1,0,0,0,100,100,0,0,1,1,0,8,66,66,205,1
Style: Label,{font},20,&H00CCFFC5,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,3,0,1,0,0,8,50,50,138,1
Style: Motion,{font},44,&H00FFFFFF,&H000000FF,&H00120B07,&H00000000,-1,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    if scenes:
        events = _kinetic_events(title, segments, scenes, duration, style)
    else:
        title_size, fitted_title = _title_layout(title)
        events = [f"Dialogue: 0,0:00:00.00,{_timestamp(duration, True)},Label,,0,0,0,,TEKNOLOJİ GÜNDEMİ",
                  f"Dialogue: 0,0:00:00.00,{_timestamp(duration, True)},Title,,0,0,0,,{{\\fs{title_size}}}{_ass_escape(fitted_title)}"]
        events.extend(f"Dialogue: 1,{_timestamp(start, True)},{_timestamp(end, True)},Caption,,0,0,0,,{_ass_escape(text)}"
                      for start, end, text in segments)
    ass_path = output_dir / "captions.ass"
    ass_path.write_text(header + "\n".join(events) + "\n", encoding="utf-8")
    return subtitle_path, ass_path


def _background(path: Path, style: str) -> None:
    """An original procedural background; no downloaded footage or licensed assets."""
    width, height = 360, 640
    palette = ((27, 20, 55), (9, 47, 50), (130, 244, 152)) if style == "aurora" else ((67, 25, 48), (20, 22, 52), (251, 150, 113))
    top, bottom, glow = palette
    pixels = bytearray()
    for y in range(height):
        mix = y / (height - 1)
        for x in range(width):
            bloom = math.exp(-(((x - 320) / 190) ** 2 + ((y - 310) / 270) ** 2)) * .25
            ring_distance = math.hypot(x - 180, y - 360)
            ring = .12 if abs(ring_distance - 112) < 1.2 or abs(ring_distance - 126) < .7 else 0
            grid = .025 if (x % 36 == 0 or y % 36 == 0) else 0
            for c in range(3):
                base = top[c] * (1 - mix) + bottom[c] * mix
                pixels.append(max(0, min(255, round(base + glow[c] * (bloom + ring + grid)))))
    path.write_bytes(f"P6\n{width} {height}\n255\n".encode("ascii") + pixels)


def _elevenlabs(sentence: str, target: Path) -> None:
    api_key = os.environ.get("ELEVENLABS_API_KEY", "")
    voice_id = os.environ.get("ELEVENLABS_VOICE_ID", "")
    if not api_key or not re.fullmatch(r"[A-Za-z0-9_-]{5,100}", voice_id):
        raise MediaError("ElevenLabs için sunucuda ELEVENLABS_API_KEY ve ELEVENLABS_VOICE_ID tanımlayın. Ücretsiz üretim için yerel sesi seçin.")
    request = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}?output_format=pcm_24000",
        data=json.dumps({"text": sentence, "model_id": "eleven_multilingual_v2"}).encode("utf-8"),
        headers={"xi-api-key": api_key, "Content-Type": "application/json", "Accept": "application/octet-stream"},
        method="POST")
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            data = response.read(16 * 1024 * 1024 + 1)
    except urllib.error.HTTPError as exc:
        raise MediaError(f"ElevenLabs isteği başarısız (HTTP {exc.code}). Anahtar, ses ve kota durumunu kontrol edin.") from None
    except (OSError, urllib.error.URLError) as exc:
        raise MediaError("ElevenLabs bağlantısı kurulamadı. İnternet bağlantısını kontrol edin veya yerel sesi seçin.") from None
    if not data or len(data) > 16 * 1024 * 1024 or len(data) % 2:
        raise MediaError("ElevenLabs geçerli PCM ses döndürmedi.")
    with wave.open(str(target), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(SAMPLE_RATE)
        audio.writeframes(data)


def _speak(sentence: str, output_dir: Path, index: int, engine: dict, provider: str, rate: int) -> Path:
    target = output_dir / f"sentence-{index:03d}.wav"
    if provider == "elevenlabs":
        _elevenlabs(sentence, target)
        return target
    source_text = output_dir / f"sentence-{index:03d}.txt"
    source_text.write_text(sentence, encoding="utf-8")
    if engine["provider"] == "macOS say":
        source_audio = output_dir / f"sentence-{index:03d}.aiff"
        _run([engine["binary"], "-v", engine["voice"], "-r", str(rate), "-f", str(source_text), "-o", str(source_audio)], timeout=60)
    else:
        source_audio = output_dir / f"sentence-{index:03d}-raw.wav"
        _run([engine["binary"], "-v", engine["voice"], "-s", str(rate), "-f", str(source_text), "-w", str(source_audio)], timeout=60, env=engine["env"])
    _run([shutil.which("ffmpeg"), "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-i", str(source_audio),
          "-ac", "1", "-ar", str(SAMPLE_RATE), "-acodec", "pcm_s16le", "-threads", "2", str(target)])
    source_audio.unlink(missing_ok=True)
    source_text.unlink(missing_ok=True)
    return target


def _encode(command: list[str], output_dir: Path, duration: float, report: Callable[[int], None]) -> None:
    """Read FFmpeg's media-time progress without buffering unbounded output."""
    deadline = time.monotonic() + 300
    last_progress = 65
    with tempfile.TemporaryFile() as error_log:
        try:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=error_log, cwd=output_dir)
        except OSError as exc:
            raise MediaError("FFmpeg başlatılamadı. Kurulumu ve çalıştırma izinlerini kontrol edin.") from exc
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                pending = ""
                while selector.get_map():
                    if time.monotonic() >= deadline:
                        raise MediaError("Video kodlama zaman aşımına uğradı. Metni kısaltıp yeniden deneyin.")
                    for key, _ in selector.select(timeout=.25):
                        data = os.read(key.fileobj.fileno(), 8192)
                        if not data:
                            selector.unregister(key.fileobj)
                            continue
                        pending += data.decode("ascii", errors="replace")
                        while "\n" in pending:
                            line, pending = pending.split("\n", 1)
                            if line.startswith("out_time_us="):
                                try:
                                    value = int(line.split("=", 1)[1]) / 1_000_000
                                except ValueError:
                                    continue
                                percent = 65 + min(30, max(0, int(30 * value / duration)))
                                if percent > last_progress:
                                    report(percent)
                                    last_progress = percent
            process.wait(timeout=max(.1, deadline - time.monotonic()))
            if process.returncode:
                error_log.seek(0, os.SEEK_END)
                error_log.seek(max(0, error_log.tell() - 1200))
                detail = error_log.read().decode("utf-8", errors="replace")
                raise MediaError(f"Video kodlanamadı. FFmpeg: {detail}")
        except subprocess.TimeoutExpired as exc:
            raise MediaError("Video kodlama zaman aşımına uğradı. Metni kısaltıp yeniden deneyin.") from exc
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=10)
            if process.stdout:
                process.stdout.close()


def _render_work(project: dict, output_dir: Path, options: dict | None = None,
           progress: Callable[[int], None] | None = None) -> dict:
    options = options or {}
    report = progress or (lambda _percent: None)
    script = str(project.get("script", "")).strip()
    title = str(project.get("title", "Teknolojide bugün")).strip() or "Teknolojide bugün"
    if not script:
        raise MediaError("Video üretmek için önce senaryo yazın.")
    if len(script) > MAX_SCRIPT_LENGTH:
        raise MediaError(f"Senaryo en fazla {MAX_SCRIPT_LENGTH} karakter olabilir; Shorts için metni kısaltın.")
    ffmpeg = _ffmpeg_state()
    if not ffmpeg["ready"]:
        raise MediaError(ffmpeg["error"])
    speech = options.get("speech", True)
    if not isinstance(speech, bool):
        raise MediaError("Seslendirme seçeneği true veya false olmalı.")
    provider = options.get("tts_provider", "local")
    if provider not in ("local", "elevenlabs"):
        raise MediaError("Desteklenmeyen ses sağlayıcısı. local veya elevenlabs seçin.")
    style = options.get("style", "aurora")
    if style not in ("aurora", "sunset"):
        raise MediaError("Desteklenmeyen video teması. aurora veya sunset seçin.")
    design = options.get("video_design", "kinetic")
    if design not in ("kinetic", "classic"):
        raise MediaError("Desteklenmeyen video tasarımı. kinetic veya classic seçin.")
    try:
        rate = int(options.get("speech_rate", 170))
    except (ValueError, TypeError):
        raise MediaError("Konuşma hızı 100 ile 240 arasında olmalı.") from None
    if not 100 <= rate <= 240:
        raise MediaError("Konuşma hızı 100 ile 240 arasında olmalı.")
    engine = _local_engine() if speech and provider == "local" else {"binary": None, "provider": "", "voice": "", "env": None}
    if speech and provider == "local" and not engine["binary"]:
        raise MediaError(engine.get("error") or "Yerel Türkçe ses çalıştırılamadı. Ses ayarlarını ve kurulu sesleri kontrol edin.")
    report(5)
    sentences = _sentences(script)
    segments = []
    spans = []
    cursor = 0.0
    audio_files = []
    for index, sentence in enumerate(sentences):
        if speech:
            audio_path = _speak(sentence, output_dir, index, engine, provider, rate)
            audio_files.append(audio_path)
            with wave.open(str(audio_path), "rb") as audio:
                duration = audio.getnframes() / audio.getframerate()
        else:
            duration = max(2.0, len(sentence.split()) / 2.6)
        if not duration or cursor + duration > MAX_DURATION:
            raise MediaError("Video 90 saniyeyi aşıyor. Senaryoyu kısaltıp yeniden deneyin.")
        spans.append((cursor, cursor + duration, sentence))
        chunks = _subtitle_chunks(sentence)
        weight = sum(len(chunk) for chunk in chunks)
        minimum = min(.65, duration / len(chunks) * .7)
        remainder = duration - minimum * len(chunks)
        chunk_cursor = cursor
        for chunk_index, chunk in enumerate(chunks):
            end = cursor + duration if chunk_index == len(chunks) - 1 else chunk_cursor + minimum + remainder * len(chunk) / weight
            segments.append((chunk_cursor, end, chunk))
            chunk_cursor = end
        cursor += duration
        report(10 + round(45 * (index + 1) / len(sentences)))
    narration_path = output_dir / "narration.wav"
    if speech:
        with wave.open(str(narration_path), "wb") as combined:
            combined.setnchannels(1)
            combined.setsampwidth(2)
            combined.setframerate(SAMPLE_RATE)
            for path in audio_files:
                with wave.open(str(path), "rb") as audio:
                    combined.writeframes(audio.readframes(audio.getnframes()))
    else:
        with wave.open(str(narration_path), "wb") as combined:
            combined.setnchannels(1)
            combined.setsampwidth(2)
            combined.setframerate(SAMPLE_RATE)
            combined.writeframes(b"\0\0" * math.ceil(cursor * SAMPLE_RATE))
    scenes = _kinetic_plan(cursor, spans) if design == "kinetic" else None
    subtitle_path, _ = _write_subtitles(output_dir, title, segments, cursor, scenes=scenes, style=style)
    if design == "classic":
        _background(output_dir / "background.ppm", style)
        inputs = ["-loop", "1", "-framerate", "24", "-i", "background.ppm", "-i", "narration.wav"]
        filters = "scale=720:1280,zoompan=z='min(zoom+0.00020,1.035)':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s=720x1280:fps=24,ass=captions.ass"
    else:
        inputs = ["-f", "lavfi", "-i", f"color=c=0x111B22:s=720x1280:r=24:d={cursor:.6f}", "-i", "narration.wav"]
        filters = "ass=captions.ass"
    report(65)
    video_path = output_dir / "reel.mp4"
    _encode([shutil.which("ffmpeg"), "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-nostats", "-stats_period", "0.1", "-progress", "pipe:1",
          *inputs,
          "-vf", filters, "-t", f"{cursor:.6f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
          "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
          "-threads", "2", "-filter_threads", "2", "-shortest", "reel.mp4"], output_dir, cursor, report)
    probe = _run([shutil.which("ffprobe"), "-v", "error", "-show_entries", "format=duration:stream=codec_name,codec_type,width,height",
                  "-of", "json", str(video_path)])
    try:
        metadata = json.loads(probe.stdout)
        actual_duration = float(metadata["format"]["duration"])
        valid_video = any(stream.get("codec_name") == "h264" and stream.get("width") == 720 and stream.get("height") == 1280 for stream in metadata["streams"])
        valid_audio = any(stream.get("codec_name") == "aac" and stream.get("codec_type") == "audio" for stream in metadata["streams"])
    except (ValueError, TypeError, KeyError) as exc:
        raise MediaError("Video çıktısı doğrulanamadı. Yeniden deneyin.") from exc
    if not valid_video or not valid_audio or not 0 < actual_duration <= MAX_DURATION + .1 or not video_path.is_file() or video_path.stat().st_size < 1024:
        raise MediaError("Video çıktısı doğrulanamadı. Yeniden deneyin.")
    for path in audio_files:
        path.unlink(missing_ok=True)
    (output_dir / "background.ppm").unlink(missing_ok=True)
    report(98)
    return {"video_path": str(video_path), "subtitle_path": str(subtitle_path),
            "duration": round(actual_duration, 2), "speech": speech,
            "provider": ("ElevenLabs" if provider == "elevenlabs" else engine["provider"]) if speech else "Sessiz video",
            "voice": engine["voice"] if speech and provider == "local" else "",
            "subtitle_timing": "sentence_audio" if speech else "estimated",
            "design": design, "scene_count": len(scenes) if scenes else 1}


def render(project: dict, output_dir: Path, options: dict | None = None,
           progress: Callable[[int], None] | None = None) -> dict:
    """Produce atomically from a private staging folder, cleaning failed attempts."""
    output_dir = Path(output_dir).resolve()
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise MediaError("Çıktı klasörüne yazılamıyor. Yazma iznini ve boş disk alanını kontrol edin.") from exc
    exports = ("reel.mp4", "captions.srt", "captions.ass", "narration.wav")
    if any((output_dir / name).exists() for name in exports):
        raise MediaError("Bu klasörde daha önce üretilmiş medya var. Yeni bir çıktı klasörü kullanın.")
    report = progress or (lambda _percent: None)
    published: list[Path] = []
    try:
        with tempfile.TemporaryDirectory(prefix=".render-", dir=output_dir) as temporary:
            work = Path(temporary)
            result = _render_work(project, work, options, report)
            for name in exports:
                # Same-filesystem links publish without overwriting another job.
                destination = output_dir / name
                os.link(work / name, destination)
                published.append(destination)
    except BaseException as exc:
        for path in published:
            path.unlink(missing_ok=True)
        if isinstance(exc, FileExistsError):
            raise MediaError("Çıktı dosyaları başka bir işlem tarafından oluşturuldu. Yeni bir çıktı klasörü kullanın.") from exc
        if isinstance(exc, OSError):
            raise MediaError("Video kaydedilemedi. Yazma iznini ve boş disk alanını kontrol edin.") from exc
        raise
    result["video_path"] = str(output_dir / "reel.mp4")
    result["subtitle_path"] = str(output_dir / "captions.srt")
    report(100)
    return result
