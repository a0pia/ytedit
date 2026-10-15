"""Credential-free RSS discovery with independent source health and bounded downloads."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
import hashlib
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
import xml.etree.ElementTree as ET

import requests

FEEDS = (
    ("ShiftDelete.Net", "https://shiftdelete.net/feed"),
    ("The Verge", "https://www.theverge.com/rss/index.xml"),
    ("TechCrunch", "https://techcrunch.com/feed/"),
    ("Ars Technica", "https://feeds.arstechnica.com/arstechnica/index"),
)
AI_WORDS = ('ai', 'openai', 'chatgpt', 'claude', 'anthropic', 'llm', 'yapay zekâ', 'yapay zeka', 'artificial intelligence')
KEYWORDS = AI_WORDS + ('apple', 'google', 'nvidia', 'robot', 'chip')


def clean(value, limit=1200):
    value = re.sub(r'<(script|style)\b[^>]*>.*?</\1>', ' ', value or '', flags=re.I | re.S)
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", unescape(value)).strip()[:limit]


def has_keywords(text, words):
    return any(re.search(r'(?<!\w)' + re.escape(word) + r'(?!\w)', text, re.I) for word in words)


def canonical_url(value):
    try:
        parsed = urlsplit(value)
        if parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username or parsed.password:
            return ''
        pairs = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)
                 if not k.lower().startswith('utm_') and k.lower() not in {'fbclid', 'gclid'}]
        return urlunsplit((parsed.scheme, parsed.netloc.lower(), parsed.path or '/', urlencode(sorted(pairs)), ''))
    except ValueError:
        return ''


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
                if found is not None:
                    text = ''.join(found.itertext())
                    if text:
                        return text
            return ""
        title = clean(value("title", f"{atom}title"), 300)
        link = value('link').strip()
        if not link:
            link = next((el.get('href', '') for el in entry.findall(f'{atom}link')
                         if el.get('rel', 'alternate') == 'alternate'), '')
        canonical = canonical_url(link)
        if not title or not canonical:
            continue
        date_raw = value('pubDate', f'{atom}published', f'{atom}updated')
        try:
            try:
                published = parsedate_to_datetime(date_raw)
            except (ValueError, TypeError):
                published = datetime.fromisoformat(date_raw.replace('Z', '+00:00'))
            if published.tzinfo is None:
                published = published.replace(tzinfo=timezone.utc)
            age = max(0, (now - published).total_seconds() / 3600)
            if age > 168:
                continue
        except (ValueError, TypeError, OverflowError):
            published, age = None, 168
        summary = clean(value('description', f'{atom}summary', f'{atom}content'), 650)
        text = title + ' ' + summary
        score = min(99, round(max(0, 70 - age * 1.3) + (20 if has_keywords(text, KEYWORDS) else 5)))
        items.append(dict(id=hashlib.sha256(canonical.encode()).hexdigest()[:20], title=title, summary=summary,
                          url=canonical, source=source, published=published.isoformat() if published else None,
                          fetched_at=now.isoformat(), score=score,
                          category='Yapay zekâ' if has_keywords(text, AI_WORDS) else 'Teknoloji'))
    return items


def fetch_news_detailed():
    def fetch(feed):
        source, url = feed
        response = None
        try:
            response = requests.get(url, timeout=(5, 12), headers={'User-Agent': 'HypeStudio/0.2 RSS Reader'}, stream=True)
            response.raise_for_status()
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 2_000_000:
                    raise ValueError('RSS boyut sınırı aşıldı')
                chunks.append(chunk)
            articles = parse_feed(b''.join(chunks), source)
            return articles, dict(source=source, status='ok', count=len(articles), error=None)
        except (requests.RequestException, ValueError, ET.ParseError):
            return [], dict(source=source, status='error', count=0, error=f'{source} kaynağına erişilemedi.')
        finally:
            if response is not None and hasattr(response, 'close'):
                response.close()
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(fetch, FEEDS))
    unique = {}
    for rows, _ in results:
        for item in rows:
            unique.setdefault(item['url'], item)
    items = sorted(unique.values(), key=lambda item: item['score'], reverse=True)[:60]
    sources = [status for _, status in results]
    return dict(items=items, sources=sources, warning=' '.join(status['error'] for status in sources if status['error']))


def fetch_news():
    """Compatibility helper for callers that only need the article list and warning."""
    result = fetch_news_detailed()
    return result['items'], result['warning']
