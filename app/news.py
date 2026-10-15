"""Credential-free RSS discovery. Scores are editorial heuristics, not view counts."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
import hashlib
import re
import xml.etree.ElementTree as ET

import requests

FEEDS = (
    ("ShiftDelete.Net", "https://shiftdelete.net/feed"),
    ("The Verge", "https://www.theverge.com/rss/index.xml"),
    ("TechCrunch", "https://techcrunch.com/feed/"),
    ("Ars Technica", "https://feeds.arstechnica.com/arstechnica/index"),
)
KEYWORDS = ("ai", "openai", "apple", "google", "nvidia", "robot", "chatgpt", "claude", "chip", "yapay zekâ", "yapay zeka")


def clean(value, limit=1200):
    value = re.sub(r"<[^>]+>", " ", value or "")
    return re.sub(r"\s+", " ", unescape(value)).strip()[:limit]


def parse_feed(data, source, now=None):
    if len(data) > 2_000_000:
        raise ValueError("RSS yanıtı çok büyük")
    root = ET.fromstring(data)
    now = now or datetime.now(timezone.utc)
    items = []
    atom = "{http://www.w3.org/2005/Atom}"
    for entry in root.findall(".//item") + root.findall(f"{atom}entry"):
        def value(*names):
            for name in names:
                found = entry.find(name)
                if found is not None and found.text:
                    return found.text
            return ""
        title = clean(value("title", f"{atom}title"), 300)
        link = value("link")
        if not link:
            links = entry.findall(f"{atom}link")
            link = next((el.get("href", "") for el in links if el.get("rel", "alternate") == "alternate"), "")
        if not title or not link.startswith(("https://", "http://")):
            continue
        date_raw = value("pubDate", f"{atom}published", f"{atom}updated")
        try:
            try:
                published = parsedate_to_datetime(date_raw)
            except (ValueError, TypeError):
                published = datetime.fromisoformat(date_raw.replace("Z", "+00:00"))
            if published.tzinfo is None:
                published = published.replace(tzinfo=timezone.utc)
            age = max(0, (now - published).total_seconds() / 3600)
            if age > 168:
                continue
        except (ValueError, TypeError):
            published, age = None, 168
        summary = clean(value("description", f"{atom}summary", f"{atom}content"), 650)
        topic = any(word in (title + " " + summary).lower() for word in KEYWORDS)
        score = min(99, round(max(0, 70 - age * 1.3) + (20 if topic else 5)))
        items.append(dict(id=hashlib.sha256(link.encode()).hexdigest()[:20], title=title, summary=summary,
                          url=link, source=source, published=published.isoformat() if published else None,
                          score=score, category="Yapay zekâ" if topic else "Teknoloji"))
    return items


def fetch_news():
    def fetch(feed):
        source, url = feed
        try:
            response = requests.get(url, timeout=(5, 12), headers={"User-Agent": "HypeStudio/0.1 RSS Reader"}, stream=True)
            response.raise_for_status()
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 2_000_000:
                    raise ValueError("RSS boyut sınırı aşıldı")
                chunks.append(chunk)
            return parse_feed(b"".join(chunks), source), None
        except (requests.RequestException, ValueError, ET.ParseError):
            return [], f"{source} kaynağına erişilemedi."
    with ThreadPoolExecutor(max_workers=3) as executor:
        results = list(executor.map(fetch, FEEDS))
    unique = {item["url"]: item for rows, _ in results for item in rows}
    items = sorted(unique.values(), key=lambda item: item["score"], reverse=True)[:60]
    warnings = [warning for _, warning in results if warning]
    return items, " ".join(warnings)
