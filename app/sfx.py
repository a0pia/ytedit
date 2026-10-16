"""Locally synthesized transition sounds (no downloaded audio).

A soft filtered-noise whoosh marks each cut and a short pitched pop marks a
keyword or a card landing: audible pattern interrupts that re-capture a viewer
whose attention drifted, mixed under the narration.
"""
from __future__ import annotations

from array import array
import math
from pathlib import Path
import random
import wave

WHOOSH_SECONDS = .42
POP_SECONDS = .09


def _whoosh(rate: int) -> list[float]:
    rng = random.Random(7)
    length = int(WHOOSH_SECONDS * rate)
    out, low, band = [], 0.0, 0.0
    for index in range(length):
        progress = index / length
        envelope = math.sin(math.pi * progress) ** 2
        # A sweeping one-pole low-pass over white noise sounds like passing air.
        cutoff = .02 + .22 * math.sin(math.pi * progress)
        low += cutoff * (rng.uniform(-1, 1) - low)
        band += .5 * (low - band)
        out.append((low - band * .6) * envelope * 1.6)
    return out


def _pop(rate: int) -> list[float]:
    length = int(POP_SECONDS * rate)
    out, phase = [], 0.0
    for index in range(length):
        progress = index / length
        phase += 2 * math.pi * (980 - 520 * progress) / rate
        out.append(math.sin(phase) * (1 - progress) ** 3 * .55)
    return out


def mix(narration: Path, target: Path, whooshes: list[float], pops: list[float], volume: float = .32) -> None:
    """Write narration plus effects to ``target``; the narration file is untouched."""
    with wave.open(str(narration), "rb") as audio:
        rate, channels, width = audio.getframerate(), audio.getnchannels(), audio.getsampwidth()
        samples = array("h")
        samples.frombytes(audio.readframes(audio.getnframes()))
    if channels != 1 or width != 2:
        raise ValueError("Efekt karışımı mono 16 bit WAV bekler.")
    mixed = [float(value) for value in samples]
    for cues, sound, lead in ((whooshes, _whoosh(rate), WHOOSH_SECONDS / 2), (pops, _pop(rate), 0.0)):
        for at in cues:
            offset = int((at - lead) * rate)
            for index, value in enumerate(sound):
                position = offset + index
                if 0 <= position < len(mixed):
                    mixed[position] += value * volume * 32767
    output = array("h", (max(-32768, min(32767, round(value))) for value in mixed))
    with wave.open(str(target), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(rate)
        audio.writeframes(output.tobytes())
