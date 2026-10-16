"""Colour packs and brand detection for Capsule videos.

A pack is a main scene palette plus accent scene palettes; scenes cycle main,
accent, accent, main... (see ``capsule.palette``). Packs come from current
trend sources and Anthropic's Apache-2.0 ``theme-factory`` skill, plus brand
packs chosen automatically when a story is about a company or product.

Brand colours are approximations used for news context only; logos are never
bundled. A user may upload an official logo for a brand (``logos`` data dir).
"""
from __future__ import annotations

import re
import zlib


def _rgb(color: str) -> tuple[int, int, int]:
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))


def _hex(rgb) -> str:
    return "".join(f"{max(0, min(255, round(v))):02X}" for v in rgb)


def _mix(a: str, b: str, amount: float) -> str:
    return _hex(x + (y - x) * amount for x, y in zip(_rgb(a), _rgb(b)))


def luminance(color: str) -> float:
    def channel(value):
        value /= 255
        return value / 12.92 if value <= .03928 else ((value + .055) / 1.055) ** 2.4
    r, g, b = map(channel, _rgb(color))
    return .2126 * r + .7152 * g + .0722 * b


def contrast(a: str, b: str) -> float:
    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + .05) / (low + .05)


def scene(name: str, panel: str, ink: str, accent: str, on_accent: str | None = None,
          card: str | None = None) -> dict:
    """A scene palette with derived card, soft text and silhouette colours."""
    dark = luminance(panel) < .18
    card = card or ("F4F3EF" if dark else _mix(panel, "FFFFFF", .78))
    card_ink = ink if contrast(ink, card) >= 4.5 else ("1B1C1F" if luminance(card) > .4 else "F4F3EF")
    on_accent = on_accent or ("1B1C1F" if luminance(accent) > .35 else "FFFFFF")
    deep = _mix(panel, "FFFFFF", .07) if dark else _mix(panel, "000000", .08)
    return {"name": name, "panel": panel, "deep": deep,
            "card": card, "ink": ink, "card_ink": card_ink, "soft": _mix(ink, panel, .42), "accent": accent,
            "on_accent": on_accent, "bird": "EEECE6" if dark else "17181C"}


def pack(label: str, frame: str, pop: str, scenes: list[dict], source: str) -> dict:
    return {"label": label, "frame": frame, "pop": pop, "scenes": scenes, "source": source}


PACKS = {
    "kapsul": pack("Kapsül", "3C3D3F", "D9F23A", [
        scene("main", "E8E7E2", "2B2C2E", "D9F23A", "2B2C2E", "F6F5F1"),
        scene("lime", "D9F23A", "1E220C", "2B2C2E"),
        scene("night", "34405A", "F4F3EF", "D9F23A"),
        scene("lilac", "CFC6F5", "211D3A", "2B2C2E"),
        scene("coral", "F4B49B", "3A1C12", "2B2C2E"),
    ], "Hype Studio"),
    "pinterest-2026": pack("Pinterest 2026", "351E28", "E9F056", [
        scene("cool-blue", "D7EFFF", "351E28", "FF5C34", card="FFFFFF"),
        scene("wasabi", "E9F056", "351E28", "351E28", "E9F056"),
        scene("plum-noir", "351E28", "F7EEF2", "E9F056"),
        scene("persimmon", "FF5C34", "2A0E06", "351E28"),
        scene("jade", "AEB8A0", "1E2419", "FF5C34"),
    ], "Pinterest Palette 2026"),
    "teal-2026": pack("Transformative Teal", "0E2E33", "F2C14E", [
        scene("cloud-dancer", "F0EEE9", "0F3B3F", "0F6B6E", card="FFFFFF"),
        scene("teal", "0F6B6E", "F0EEE9", "F2C14E"),
        scene("gold", "F2C14E", "0F3B3F", "0F3B3F"),
        scene("deep", "16292E", "F0EEE9", "5FD3C8"),
        scene("sand", "E6D8C3", "2C2620", "0F6B6E"),
    ], "WGSN x Coloro 2026 + Pantone 2026 Cloud Dancer"),
    "ocean": pack("Ocean Depths", "1A2332", "A8DADC", [
        scene("cream", "F1FAEE", "1A2332", "2D8B8B", card="FFFFFF"),
        scene("teal", "2D8B8B", "F1FAEE", "1A2332"),
        scene("navy", "1A2332", "F1FAEE", "A8DADC"),
        scene("seafoam", "A8DADC", "1A2332", "1A2332"),
    ], "theme-factory: Ocean Depths"),
    "sunset": pack("Sunset Boulevard", "264653", "E9C46A", [
        scene("sand", "FBF1DF", "264653", "E76F51", card="FFFFFF"),
        scene("burnt", "E76F51", "1F2A30", "264653"),
        scene("deep", "264653", "FBF1DF", "E9C46A"),
        scene("coral", "F4A261", "264653", "264653"),
        scene("warm-sand", "E9C46A", "264653", "E76F51"),
    ], "theme-factory: Sunset Boulevard"),
    "tech": pack("Tech Innovation", "1E1E1E", "00FFFF", [
        scene("white", "F4F6FA", "1E1E1E", "0066FF", card="FFFFFF"),
        scene("electric", "0066FF", "FFFFFF", "00FFFF"),
        scene("dark", "1E1E1E", "FFFFFF", "00FFFF"),
        scene("cyan", "7FF5F5", "0B1B2B", "0066FF"),
    ], "theme-factory: Tech Innovation"),
    "golden": pack("Golden Hour", "4A403A", "F4A900", [
        scene("beige", "F3E9DA", "4A403A", "C1666B", card="FFFFFF"),
        scene("mustard", "F4A900", "2E2723", "4A403A"),
        scene("chocolate", "4A403A", "F3E9DA", "F4A900"),
        scene("terracotta", "C1666B", "FFFFFF", "F4A900"),
    ], "theme-factory: Golden Hour"),
    "forest": pack("Forest Canopy", "2D4A2B", "A4AC86", [
        scene("ivory", "FAF9F6", "2D4A2B", "7D8471", card="FFFFFF"),
        scene("forest", "2D4A2B", "FAF9F6", "A4AC86"),
        scene("olive", "A4AC86", "1F2A1E", "2D4A2B"),
        scene("sage", "7D8471", "FAF9F6", "FAF9F6"),
    ], "theme-factory: Forest Canopy"),
    # Brand packs: picked automatically when the story is about the brand.
    "anthropic": pack("Claude / Anthropic", "141413", "D97757", [
        scene("ivory", "F0EEE6", "141413", "D97757", card="FFFFFF"),
        scene("clay", "D97757", "141413", "141413", "F0EEE6"),
        scene("slate", "141413", "F0EEE6", "D97757"),
        scene("oat", "E3DACC", "141413", "D97757"),
        scene("sky", "C6D4DF", "141413", "141413"),
    ], "Marka renklerine yakın"),
    "openai": pack("OpenAI", "0D0D0D", "10A37F", [
        scene("white", "F7F7F8", "0D0D0D", "10A37F", card="FFFFFF"),
        scene("green", "10A37F", "FFFFFF", "0D0D0D"),
        scene("black", "0D0D0D", "F7F7F8", "10A37F"),
    ], "Marka renklerine yakın"),
    "google": pack("Google", "202124", "FBBC05", [
        scene("white", "F8F9FA", "202124", "4285F4", card="FFFFFF"),
        scene("blue", "4285F4", "FFFFFF", "FBBC05"),
        scene("green", "34A853", "FFFFFF", "202124"),
        scene("yellow", "FBBC05", "202124", "EA4335"),
        scene("red", "EA4335", "FFFFFF", "202124"),
    ], "Marka renklerine yakın"),
    "apple": pack("Apple", "1D1D1F", "0071E3", [
        scene("silver", "F5F5F7", "1D1D1F", "0071E3", card="FFFFFF"),
        scene("graphite", "1D1D1F", "F5F5F7", "2997FF"),
        scene("mist", "E8E8ED", "1D1D1F", "1D1D1F"),
    ], "Marka renklerine yakın"),
    "nvidia": pack("NVIDIA", "000000", "76B900", [
        scene("light", "F2F2F2", "111111", "76B900", card="FFFFFF"),
        scene("green", "76B900", "0B0B0B", "0B0B0B"),
        scene("black", "111111", "F2F2F2", "76B900"),
    ], "Marka renklerine yakın"),
    "meta": pack("Meta", "1C2B33", "0866FF", [
        scene("light", "F0F2F5", "1C2B33", "0866FF", card="FFFFFF"),
        scene("blue", "0866FF", "FFFFFF", "1C2B33"),
        scene("ink", "1C2B33", "F0F2F5", "0866FF"),
    ], "Marka renklerine yakın"),
    "microsoft": pack("Microsoft", "2B2B2B", "00A4EF", [
        scene("light", "F3F3F3", "2B2B2B", "00A4EF", card="FFFFFF"),
        scene("orange", "F25022", "FFFFFF", "2B2B2B"),
        scene("green", "7FBA00", "1B1B1B", "2B2B2B"),
        scene("blue", "00A4EF", "0B1B2B", "2B2B2B"),
        scene("yellow", "FFB900", "2B2B2B", "2B2B2B"),
    ], "Marka renklerine yakın"),
    "samsung": pack("Samsung", "0B1A5C", "1428A0", [
        scene("light", "F4F6FB", "0B1A5C", "1428A0", card="FFFFFF"),
        scene("blue", "1428A0", "FFFFFF", "F4F6FB"),
        scene("navy", "0B1A5C", "F4F6FB", "7FA2FF"),
    ], "Marka renklerine yakın"),
    "tesla": pack("Tesla / X", "171A20", "E31937", [
        scene("light", "F4F4F4", "171A20", "E31937", card="FFFFFF"),
        scene("red", "E31937", "FFFFFF", "171A20"),
        scene("black", "171A20", "F4F4F4", "E31937"),
    ], "Marka renklerine yakın"),
}

GENERAL_PACKS = ("pinterest-2026", "teal-2026", "ocean", "sunset", "tech", "golden", "forest")

# Brand registry: slug -> (display name, pack, keyword stems). Stems match word
# starts so Turkish suffixes still match ("Claude'un", "Google'ın").
BRANDS = {
    "claude": ("Claude", "anthropic", ("claude",)),
    "anthropic": ("Anthropic", "anthropic", ("anthropic",)),
    "openai": ("OpenAI", "openai", ("openai",)),
    "chatgpt": ("ChatGPT", "openai", ("chatgpt", "gpt-")),
    "google": ("Google", "google", ("google",)),
    "gemini": ("Gemini", "google", ("gemini",)),
    "apple": ("Apple", "apple", ("apple", "iphone", "ipad", "macbook", "macos", "ios ")),
    "nvidia": ("NVIDIA", "nvidia", ("nvidia",)),
    "meta": ("Meta", "meta", ("meta ", "meta'", "facebook", "instagram", "whatsapp", "llama")),
    "microsoft": ("Microsoft", "microsoft", ("microsoft", "windows", "copilot", "xbox")),
    "samsung": ("Samsung", "samsung", ("samsung", "galaxy")),
    "tesla": ("Tesla", "tesla", ("tesla", "spacex", "starlink")),
    "x": ("X", "tesla", ("twitter", "x.com", "grok", "xai")),
}


def _stems_in(text: str, stem: str) -> int:
    pattern = r"(?<![\w])" + re.escape(stem.strip())
    if stem.endswith(" "):
        pattern += r"\b"
    return len(re.findall(pattern, text, flags=re.IGNORECASE))


def mentions(text: str) -> dict[str, int]:
    """Brand slug -> mention count in the given text."""
    found = {}
    for slug, (_name, _pack, stems) in BRANDS.items():
        count = sum(_stems_in(text, stem) for stem in stems)
        if count:
            found[slug] = count
    return found


def primary_brand(title: str, script: str) -> str | None:
    counts = mentions(f"{title} {title} {script}")  # The title counts double.
    return max(counts, key=counts.get) if counts else None


def choose_pack(choice: str, title: str, script: str) -> str:
    """Resolve "auto" to the story's brand pack, else a stable trend pack per story."""
    if choice != "auto":
        return choice
    brand = primary_brand(title, script)
    if brand:
        return BRANDS[brand][1]
    return GENERAL_PACKS[zlib.crc32(title.encode("utf-8")) % len(GENERAL_PACKS)]
