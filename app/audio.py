"""Offline inspection and estimated caption timing for uploaded MP3/WAV narration.

Energy and pauses guide these timings; they are estimates, not speech recognition
or word alignment. No uploaded input is opened by a network-capable demuxer.
"""
from __future__ import annotations

from array import array
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys
import unicodedata
import wave


class AudioError(RuntimeError):
    """An actionable upload or caption error safe to show to the user."""


MAX_DURATION = 90.0
MIN_DURATION = .4
MAX_SCRIPT_LENGTH = 1200
SAMPLE_RATE = 24000
MAX_AUDIO_BYTES = 32 * 1024 * 1024
MAX_CAPTIONS = 100
MIN_CAPTION_DURATION = .04
_ALLOWED_WAV_CODECS = {"pcm_s16le", "pcm_s24le", "pcm_s32le", "pcm_u8", "pcm_f32le", "pcm_f64le"}


def _text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFC", value).split())


def _script(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AudioError("Altyazı oluşturmak için önce senaryo yazın.")
    if len(value) > MAX_SCRIPT_LENGTH:
        raise AudioError("Senaryo en fazla 1200 karakter olabilir.")
    return _text(value)


def _run(command: list[str]) -> bytes:
    try:
        result = subprocess.run(command, capture_output=True, check=False, timeout=25)
    except subprocess.TimeoutExpired as exc:
        raise AudioError("Ses dosyası işlenirken zaman aşımı oluştu. Daha kısa bir MP3 veya WAV yükleyin.") from exc
    except OSError as exc:
        raise AudioError("Ses işlemek için FFmpeg ve ffprobe kurulu olmalı.") from exc
    if result.returncode:
        raise AudioError("Ses dosyası okunamadı. Geçerli bir MP3 veya WAV yükleyin.")
    return result.stdout


def _binary(name: str) -> str:
    binary = shutil.which(name)
    if not binary:
        raise AudioError("Ses işlemek için FFmpeg ve ffprobe kurulu olmalı.")
    return binary


def _local_file(value: str | Path) -> Path:
    try:
        path = Path(value).resolve(strict=True)
        if not path.is_file() or not 0 < path.stat().st_size <= MAX_AUDIO_BYTES:
            raise AudioError("Ses dosyası boş veya 32 MB sınırını aşıyor.")
        return path
    except (OSError, TypeError, ValueError) as exc:
        raise AudioError("Yüklenen ses dosyası bulunamadı.") from exc


def _decode(path: str | Path) -> tuple[dict, bytes]:
    source = _local_file(path)
    raw = _run([_binary("ffprobe"), "-v", "error", "-protocol_whitelist", "file",
                "-format_whitelist", "mp3,wav", "-show_entries",
                "format=format_name,duration:stream=codec_type,codec_name,channels,sample_rate",
                "-of", "json", str(source)])
    try:
        probe = json.loads(raw)
        streams = probe["streams"]
        if not isinstance(streams, list) or len(streams) != 1 or streams[0].get("codec_type") != "audio":
            raise AudioError("Yalnızca tek ses kanalı akışı içeren MP3 veya WAV yükleyin; video desteklenmiyor.")
        stream = streams[0]
        container = probe["format"]["format_name"]
        codec = stream["codec_name"]
        channels = int(stream["channels"])
        sample_rate = int(stream["sample_rate"])
        if container not in {"mp3", "wav"} or (container == "mp3" and codec != "mp3") or (container == "wav" and codec not in _ALLOWED_WAV_CODECS):
            raise AudioError("Desteklenmeyen ses biçimi. MP3 veya PCM WAV yükleyin.")
        if channels not in {1, 2} or not 8000 <= sample_rate <= 192000:
            raise AudioError("Ses dosyası mono veya stereo ve 8–192 kHz örnekleme hızında olmalı.")
        reported = float(probe["format"].get("duration", 0))
        if not math.isfinite(reported) or reported > MAX_DURATION + .2:
            raise AudioError("Ses en fazla 90 saniye olabilir. Kaydı kısaltıp yeniden yükleyin.")
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise AudioError("Ses dosyasının bilgileri okunamadı. Geçerli bir MP3 veya WAV yükleyin.") from exc
    # Bound decoded output even if a malformed header understates the duration.
    pcm = _run([_binary("ffmpeg"), "-nostdin", "-hide_banner", "-loglevel", "error",
                "-protocol_whitelist", "file", "-format_whitelist", "mp3,wav", "-threads", "2",
                "-i", str(source), "-map", "0:a:0", "-vn", "-sn", "-dn", "-t", "90.04",
                "-ac", "1", "-ar", str(SAMPLE_RATE), "-c:a", "pcm_s16le", "-f", "s16le", "pipe:1"])
    duration = len(pcm) / (2 * SAMPLE_RATE)
    if duration > MAX_DURATION:
        raise AudioError("Ses en fazla 90 saniye olabilir. Kaydı kısaltıp yeniden yükleyin.")
    if duration < MIN_DURATION or len(pcm) % 2:
        raise AudioError("Ses en az 0,4 saniye olmalı ve geçerli ses verisi içermeli.")
    intervals = _voiced_intervals(pcm)
    return {"duration": duration, "channels": channels, "codec": codec, "sample_rate": sample_rate,
            "format": container, "voiced_duration": sum(end - start for start, end in intervals)}, pcm


def _voiced_intervals(pcm: bytes) -> list[tuple[float, float]]:
    samples = array("h")
    samples.frombytes(pcm)
    if sys.byteorder != "little":
        samples.byteswap()
    step = SAMPLE_RATE // 50  # 20 ms energy envelope, without an ML dependency.
    energy = []
    for offset in range(0, len(samples), step):
        window = samples[offset:offset + step]
        mean = sum(window) / len(window)
        energy.append(math.sqrt(max(0.0, sum(value * value for value in window) / len(window) - mean * mean)))
    peak = max(energy, default=0.0)
    threshold = max(32.0, peak * .10)
    voiced = [index for index, value in enumerate(energy) if value >= threshold]
    if peak < 64 or len(voiced) * .02 < .12:
        raise AudioError("Ses kaydı sessiz veya konuşma algılanamayacak kadar düşük. Duyulabilir bir ses kaydı yükleyin.")
    duration = len(samples) / SAMPLE_RATE
    intervals: list[tuple[float, float]] = []
    for index in voiced:
        start, end = max(0.0, index * .02 - .04), min(duration, (index + 1) * .02 + .06)
        if intervals and start <= intervals[-1][1] + .12:
            intervals[-1] = (intervals[-1][0], end)
        else:
            intervals.append((start, end))
    return intervals


def inspect_audio(path: str | Path) -> dict:
    """Validate a local upload and report its actual decoded (not header) duration."""
    metadata, _pcm = _decode(path)
    return metadata


def normalize_audio(source: str | Path, target_wav: str | Path) -> float:
    """Decode locally once to mono 24 kHz signed 16-bit WAV, preserving amplitude."""
    metadata, pcm = _decode(source)
    try:
        with wave.open(str(target_wav), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(SAMPLE_RATE)
            output.writeframes(pcm)
    except (OSError, wave.Error) as exc:
        raise AudioError("Ses dosyası kaydedilemedi. Disk alanını ve yazma iznini kontrol edin.") from exc
    return metadata["duration"]


def validate_captions(segments: list, script: str, duration: float) -> list[dict]:
    """Validate all timing fields and require the complete script in source order."""
    expected = _script(script)
    if isinstance(duration, bool) or not isinstance(duration, (int, float)) or not math.isfinite(duration) or not MIN_DURATION <= duration <= MAX_DURATION:
        raise AudioError("Altyazı için geçerli, en fazla 90 saniyelik ses gerekli.")
    if not isinstance(segments, list) or not 1 <= len(segments) <= MAX_CAPTIONS:
        raise AudioError("Altyazı listesi 1 ile 100 arasında bölüm içermeli.")
    result = []
    previous_end = 0.0
    for item in segments:
        if not isinstance(item, dict) or not isinstance(item.get("text"), str):
            raise AudioError("Her altyazı bölümü metin, başlangıç ve bitiş içermeli.")
        start, end = item.get("start"), item.get("end")
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) for value in (start, end)):
            raise AudioError("Altyazı zamanları geçerli sayılar olmalı.")
        if start < 0 or end > duration or end - start < MIN_CAPTION_DURATION - 1e-8 or start < previous_end:
            raise AudioError("Altyazılar sıralı, çakışmasız ve ses süresi içinde olmalı; her bölüm en az 0,04 saniye sürmeli.")
        text = _text(item["text"])
        if not text:
            raise AudioError("Altyazı bölümleri boş olamaz.")
        result.append({"start": float(start), "end": float(end), "text": text})
        previous_end = end
    if _text(" ".join(item["text"] for item in result)) != expected:
        raise AudioError("Altyazı metni senaryoyla aynı sırada ve eksiksiz olmalı. Kelime eklemeyin veya çıkarmayın.")
    return result


def _chunks(script: str) -> list[str]:
    chunks: list[str] = []
    current = ""
    for token in script.split():
        if current and (len(current) + len(token) + 1 > 72 or len(current.split()) >= 12):
            chunks.append(current)
            current = ""
        current = f"{current} {token}".strip()
        if len(current) >= 28 and re.search(r"[.!?…][\"”’')\]]*$", token):
            chunks.append(current)
            current = ""
    if current:
        chunks.append(current)
    return chunks


def plan_captions(script: str, audio_path: str | Path) -> list[dict]:
    """ESTIMATED: distribute complete text over audible intervals using text weight.

    This detects energy and pauses only. The user should review/edit the result;
    it makes no claim to recognize the words spoken in the recording.
    """
    text = _script(script)
    metadata, pcm = _decode(audio_path)
    intervals = _voiced_intervals(pcm)
    voiced_duration = sum(end - start for start, end in intervals)
    chunks = _chunks(text)
    # Avoid implausibly short captions when a long script accompanies short audio.
    limit = max(1, min(MAX_CAPTIONS, int(voiced_duration / .06)))
    if len(chunks) > limit:
        chunks = [" ".join(chunks[len(chunks) * i // limit:len(chunks) * (i + 1) // limit]) for i in range(limit)]
    weights = [max(1, len(re.sub(r"\s", "", chunk))) for chunk in chunks]
    minimum = min(.06, voiced_duration / len(chunks))
    remainder = max(0.0, voiced_duration - minimum * len(chunks))

    def position(offset: float, *, end: bool) -> float:
        consumed = 0.0
        for index, (start, finish) in enumerate(intervals):
            length = finish - start
            if offset < consumed + length - 1e-9 or (end and offset <= consumed + length + 1e-9):
                return min(finish, max(start, start + offset - consumed))
            consumed += length
        return intervals[-1][1]

    cursor = 0.0
    result = []
    for index, (chunk, weight) in enumerate(zip(chunks, weights)):
        finish = voiced_duration if index == len(chunks) - 1 else cursor + minimum + remainder * weight / sum(weights)
        result.append({"start": round(position(cursor, end=False), 6),
                       "end": round(position(finish, end=True), 6), "text": chunk})
        cursor = finish
    # Clamp rounding at the exact decoded sample boundary.
    result[-1]["end"] = min(result[-1]["end"], metadata["duration"])
    return validate_captions(result, text, metadata["duration"])
