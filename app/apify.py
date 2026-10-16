"""Optional Apify integration: social trends and news images.

Apify is a paid cloud scraping platform (a free plan includes monthly credits).
Nothing here runs unless the user sets APIFY_TOKEN in their local .env. The token
is sent only in the Authorization header, never in URLs or logs.

* ``fetch_trends`` runs Store actors that search YouTube, TikTok and X for tech
  topics, then ``hype_matches`` boosts news items that share keywords with what is
  trending, weighted by engagement.
* ``discover_images`` runs the Cheerio Scraper on a news article and returns the
  page's share image and article images for the user to choose from.

Actor IDs and inputs follow each actor's public input schema; they can be
overridden with APIFY_*_ACTOR variables when an actor changes.
"""
from __future__ import annotations

import ipaddress
import json
import math
import os
import re
import socket
from urllib.parse import urljoin, urlsplit

import requests

API = "https://api.apify.com/v2"
MAX_RESPONSE = 5 * 1024 * 1024
TOPICS = ("yapay zeka", "teknoloji", "artificial intelligence", "ChatGPT", "Claude AI", "iPhone")
STOPWORDS = {"için", "ile", "olan", "gibi", "daha", "çok", "yeni", "this", "that", "with", "from", "your", "have",
             "will", "what", "about", "into", "just", "they", "their", "there", "these", "bir", "ama", "veya",
             "nasıl", "neden", "kadar", "sonra", "önce", "olarak", "video", "shorts", "https", "www", "com"}

IMAGE_PAGE_FUNCTION = """async function pageFunction(context) {
  const { $, request } = context;
  const pick = (selector, attr) => $(selector).map((i, el) => $(el).attr(attr)).get().filter(Boolean);
  const meta = pick('meta[property="og:image"], meta[name="twitter:image"], meta[property="og:image:secure_url"]', 'content');
  const images = $('article img, main img, figure img').map((i, el) => ({
    src: $(el).attr('src') || $(el).attr('data-src') || '',
    alt: $(el).attr('alt') || '',
    width: Number($(el).attr('width')) || null,
  })).get().filter((image) => image.src);
  return { url: request.loadedUrl || request.url, meta, images: images.slice(0, 24),
           title: $('meta[property="og:title"]').attr('content') || $('title').text() };
}"""


class ApifyError(RuntimeError):
    """A user-actionable Apify problem (missing token, quota, actor failure)."""


def token() -> str:
    return os.environ.get("APIFY_TOKEN", "").strip()


def configured() -> bool:
    return bool(re.fullmatch(r"apify_api_[A-Za-z0-9]{20,80}", token()))


def run_actor(actor: str, actor_input: dict, *, timeout: int = 120, session=requests) -> list[dict]:
    """Run an actor synchronously and return its dataset items."""
    if not configured():
        raise ApifyError("Apify kullanmak için yerel .env dosyasına APIFY_TOKEN ekleyin.")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+[/~][A-Za-z0-9_.-]+", actor):
        raise ApifyError("Geçersiz Apify actor kimliği.")
    url = f"{API}/acts/{actor.replace('/', '~')}/run-sync-get-dataset-items"
    try:
        response = session.post(url, params={"timeout": timeout, "format": "json", "clean": "true"},
                                headers={"Authorization": f"Bearer {token()}", "Content-Type": "application/json"},
                                data=json.dumps(actor_input), timeout=(10, timeout + 30), stream=True)
    except requests.RequestException:
        raise ApifyError("Apify'a bağlanılamadı. İnternet bağlantısını kontrol edin.") from None
    try:
        if response.status_code in (401, 403):
            raise ApifyError("Apify token geçersiz veya yetkisiz. Token'ı Apify Console'dan kontrol edin.")
        if response.status_code == 402:
            raise ApifyError("Apify kredisi yetersiz. Aylık ücretsiz kredi bitmiş olabilir.")
        if response.status_code >= 400:
            raise ApifyError(f"Apify actor çalıştırılamadı ({actor}, HTTP {response.status_code}).")
        chunks, size = [], 0
        for chunk in response.iter_content(65536):
            size += len(chunk)
            if size > MAX_RESPONSE:
                raise ApifyError("Apify yanıtı çok büyük.")
            chunks.append(chunk)
    finally:
        response.close()
    try:
        items = json.loads(b"".join(chunks) or b"[]")
    except ValueError:
        raise ApifyError("Apify geçerli bir yanıt döndürmedi.") from None
    if not isinstance(items, list):
        raise ApifyError("Apify geçerli bir yanıt döndürmedi.")
    return [item for item in items if isinstance(item, dict)]


# --- social trends --------------------------------------------------------------------

def _number(*values) -> float:
    for value in values:
        try:
            if value is not None:
                return float(value)
        except (TypeError, ValueError):
            continue
    return 0.0


def _trend(platform: str, item: dict) -> dict | None:
    if platform == "youtube":
        title = item.get("title") or ""
        engagement = _number(item.get("viewCount"), item.get("views"))
        url = item.get("url") or ""
    elif platform == "tiktok":
        title = item.get("text") or item.get("desc") or ""
        engagement = _number(item.get("playCount"), item.get("diggCount"))
        url = item.get("webVideoUrl") or item.get("url") or ""
    else:
        title = item.get("text") or item.get("fullText") or ""
        engagement = _number(item.get("viewCount")) or (
            _number(item.get("likeCount")) * 20 + _number(item.get("retweetCount")) * 40)
        url = item.get("url") or item.get("twitterUrl") or ""
    title = re.sub(r"\s+", " ", str(title)).strip()[:300]
    if not title:
        return None
    return {"platform": platform, "title": title, "url": str(url)[:500], "engagement": engagement}


def actors() -> dict:
    return {
        "youtube": (os.environ.get("APIFY_YOUTUBE_ACTOR", "streamers/youtube-scraper"),
                    {"searchQueries": list(TOPICS[:4]), "maxResults": 8, "sortingOrder": "date"}),
        "tiktok": (os.environ.get("APIFY_TIKTOK_ACTOR", "clockworks/tiktok-scraper"),
                   {"hashtags": ["yapayzeka", "teknoloji", "ai", "tech"], "resultsPerPage": 10}),
        "x": (os.environ.get("APIFY_X_ACTOR", "apidojo/tweet-scraper"),
              {"searchTerms": list(TOPICS[:4]), "maxItems": 40, "sort": "Top"}),
    }


def fetch_trends(platforms=("youtube", "tiktok", "x"), *, session=requests) -> dict:
    """Run the trend actors; each platform fails independently."""
    trends, status = [], []
    for platform in platforms:
        actor, actor_input = actors()[platform]
        try:
            items = run_actor(actor, actor_input, session=session)
            rows = [row for row in (_trend(platform, item) for item in items) if row]
            trends.extend(rows)
            status.append({"platform": platform, "status": "ok", "count": len(rows), "error": None})
        except ApifyError as exc:
            status.append({"platform": platform, "status": "error", "count": 0, "error": str(exc)})
    return {"items": sorted(trends, key=lambda row: row["engagement"], reverse=True)[:150], "sources": status}


def _keywords(text: str) -> set[str]:
    words = re.findall(r"[\wçğıöşüâîû]+", text.lower().replace("İ", "i").replace("I", "ı"))
    return {word for word in words if len(word) > 3 and word not in STOPWORDS and not word.isdigit()}


def hype_matches(news_items: list[dict], trends: list[dict]) -> list[dict]:
    """News items with a trend boost (0-25) and the trending posts that matched."""
    weights: dict[str, float] = {}
    posts: dict[str, list[dict]] = {}
    for trend in trends:
        weight = 1 + math.log10(1 + trend["engagement"])
        for word in _keywords(trend["title"]):
            weights[word] = weights.get(word, 0) + weight
            posts.setdefault(word, []).append(trend)
    top = max(weights.values(), default=1)
    boosted = []
    for item in news_items:
        shared = _keywords(item.get("title", "") + " " + item.get("summary", "")) & set(weights)
        raw = sum(weights[word] for word in shared)
        boost = min(25, round(25 * raw / (top * 3))) if shared else 0
        matched = []
        for word in sorted(shared, key=lambda word: -weights[word]):
            for trend in posts[word]:
                if trend not in matched:
                    matched.append(trend)
        boosted.append({**item, "trend_boost": boost, "hype_score": min(99, item.get("score", 0) + boost),
                        "trend_words": sorted(shared, key=lambda word: -weights[word])[:5],
                        "trend_posts": [{"platform": t["platform"], "title": t["title"][:120], "url": t["url"]}
                                        for t in matched[:3]]})
    return boosted


# --- news images ----------------------------------------------------------------------

def public_url(url: str) -> bool:
    """Only fetch public http(s) hosts: blocks localhost and private networks (SSRF)."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname or parts.username or parts.password:
        return False
    try:
        addresses = {info[4][0] for info in socket.getaddrinfo(parts.hostname, parts.port or 443)}
    except (socket.gaierror, UnicodeError, ValueError):
        return False
    return bool(addresses) and all(ipaddress.ip_address(address.split("%")[0]).is_global for address in addresses)


def discover_images(article_url: str, *, session=requests) -> list[dict]:
    """Share image first, then article images, as absolute public URLs."""
    actor = os.environ.get("APIFY_IMAGE_ACTOR", "apify/cheerio-scraper")
    items = run_actor(actor, {"startUrls": [{"url": article_url}], "pageFunction": IMAGE_PAGE_FUNCTION,
                              "maxRequestsPerCrawl": 1, "proxyConfiguration": {"useApifyProxy": True}},
                      timeout=90, session=session)
    found, seen = [], set()
    for item in items[:1]:
        base = item.get("url") or article_url
        candidates = [{"src": src, "alt": "Paylaşım görseli", "kind": "og"} for src in item.get("meta") or []]
        candidates += [{"src": image.get("src", ""), "alt": image.get("alt", ""), "kind": "article"}
                       for image in item.get("images") or [] if isinstance(image, dict)]
        for candidate in candidates:
            absolute = urljoin(base, str(candidate["src"]))
            if absolute in seen or not absolute.startswith(("http://", "https://")) or absolute.endswith(".svg"):
                continue
            seen.add(absolute)
            found.append({"url": absolute[:1000], "alt": str(candidate["alt"])[:200], "kind": candidate["kind"]})
    return found[:12]


def download_image(url: str, target, *, session=requests, limit: int = 8 * 1024 * 1024) -> None:
    """Download an image from a public host with size and type limits."""
    if not public_url(url):
        raise ApifyError("Bu görsel adresi indirilemez (yalnızca herkese açık http/https adresleri).")
    try:
        response = session.get(url, timeout=(5, 20), stream=True, allow_redirects=False,
                               headers={"User-Agent": "HypeStudio/0.5 image fetch"})
    except requests.RequestException:
        raise ApifyError("Görsel indirilemedi.") from None
    try:
        if response.status_code != 200 or not str(response.headers.get("Content-Type", "")).startswith("image/"):
            raise ApifyError("Adres geçerli bir görsel döndürmedi.")
        size = 0
        with open(target, "xb") as output:
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > limit:
                    raise ApifyError("Görsel çok büyük (en fazla 8 MB).")
                output.write(chunk)
    finally:
        response.close()
