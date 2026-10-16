"""Typography map: read the narration word by word and decide where to emphasize.

Every spoken word gets a score from simple, explainable signals: numbers and
units, brand names, turning words ("ama", "ancak", "peki"), intensifiers ("en",
"ilk", "rekor"), and the end of questions and exclamations. Only the strongest
few moments, spaced apart, are chosen; the camera punches in and the caption
word is enlarged only there, so most scenes stay calm and emphasis keeps its
meaning.
"""
from __future__ import annotations

import re

from .palettes import mentions

TURNS = {"ama", "ancak", "fakat", "peki", "oysa", "rağmen", "yine", "halbuki", "aslında", "çünkü"}
INTENSIFIERS = {"en", "ilk", "rekor", "dev", "büyük", "tamamen", "sadece", "yalnızca", "hiç", "asla", "mutlaka",
                "resmen", "ilk kez", "tarihi", "yeni", "kritik", "önemli", "inanılmaz", "şok", "sızdı", "yasak",
                "ücretsiz", "bedava", "son", "dünyanın", "türkiye'nin"}
UNITS = {"milyon", "milyar", "bin", "trilyon", "tl", "dolar", "euro", "gb", "tb", "mb", "ghz", "mah", "nm", "kat",
         "yüzde", "saat", "dakika", "saniye", "yıl", "gün"}

SPACING = 3.5      # Seconds between emphasis moments.
PER_SECONDS = 6.5  # At most one moment per this many seconds of video.


def _clean(word: str) -> str:
    return word.strip(".,;:!?…\"'“”‘’()[]").lower()


def score_word(word: str, previous: str, following: str, sentence_end: str) -> tuple[float, str]:
    """A word's emphasis score and the reason, for the typography map."""
    clean = _clean(word)
    if not clean:
        return 0.0, ""
    if re.search(r"\d", clean) or "%" in word:
        return 3.0, "sayı"
    if clean in UNITS and re.search(r"\d", previous):
        return 2.6, "birim"
    if mentions(word):
        return 2.4, "marka"
    if _clean(previous) in TURNS and len(clean) > 3:
        return 2.0, "dönüş sonrası"
    if _clean(previous) in INTENSIFIERS and len(clean) > 2:
        return 1.8, "güçlü ifade"
    if clean in INTENSIFIERS and len(clean) > 3:
        return 1.4, "güçlü ifade"
    if sentence_end in ("?", "!") and not following:
        return 1.6, "soru" if sentence_end == "?" else "ünlem"
    return 0.0, ""


def typography_map(bursts) -> list[dict]:
    """Score every caption word: [{word, start, end, score, reason}]."""
    words = []
    for start, end, chunk, times in bursts:
        for index, (word, at) in enumerate(zip(chunk, times)):
            finish = times[index + 1] if index + 1 < len(times) else end
            words.append({"word": word, "start": at, "end": finish})
    for index, item in enumerate(words):
        previous = words[index - 1]["word"] if index else ""
        following = words[index + 1]["word"] if index + 1 < len(words) else ""
        ends_here = item["word"][-1:] if item["word"][-1:] in "?!." else ""
        next_sentence = bool(ends_here)
        score, reason = score_word(item["word"], previous, "" if next_sentence else following, ends_here)
        item.update(score=score, reason=reason)
    return words


def choose_moments(words: list[dict], duration: float) -> list[dict]:
    """The strongest, well-spaced moments; never more than one per ~6.5 s."""
    limit = max(1, round(duration / PER_SECONDS))
    chosen: list[dict] = []
    for item in sorted((w for w in words if w["score"] >= 1.4 and w["start"] > .8),
                       key=lambda w: (-w["score"], w["start"])):
        if len(chosen) >= limit:
            break
        if all(abs(item["start"] - other["start"]) >= SPACING for other in chosen):
            chosen.append(item)
    return sorted(chosen, key=lambda item: item["start"])
