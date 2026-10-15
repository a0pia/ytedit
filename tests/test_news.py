"""Credential-free discovery and deterministic drafting; no live network calls."""
from datetime import datetime, timezone
import json

import pytest
import requests

from app import news, writing


NOW = datetime(2026, 10, 16, 12, tzinfo=timezone.utc)


def rss(*entries):
    return ("<rss><channel>" + "".join(entries) + "</channel></rss>").encode()


def item(title, date="Fri, 16 Oct 2026 11:00:00 +0000", url="https://example.org/news", summary="Bir teknoloji haberi."):
    return f"<item><title>{title}</title><link>{url}</link><pubDate>{date}</pubDate><description><![CDATA[{summary}]]></description></item>"


def test_rss_parses_timestamp_strips_html_and_decodes_entities():
    result = news.parse_feed(rss(item("OpenAI yeni model", summary="<p>Yeni <b>çip</b> &amp; araştırma.</p>")), "Kaynak", NOW)
    assert len(result) == 1
    article = result[0]
    assert article["summary"] == "Yeni çip & araştırma."
    assert article["published"] == "2026-10-16T11:00:00+00:00"
    assert article["category"] == "Yapay zekâ"
    assert article["url"] == "https://example.org/news"
    assert len(article["id"]) == 20


def test_atom_parses_alternate_links_and_iso_dates():
    feed = b'''<feed xmlns="http://www.w3.org/2005/Atom"><entry>
      <title>Google chip launch</title><link rel="self" href="https://example.org/feed"/>
      <link rel="alternate" href="https://example.org/article"/>
      <updated>2026-10-16T10:00:00Z</updated><summary>&lt;p&gt;New chip&lt;/p&gt;</summary>
      </entry></feed>'''
    article = news.parse_feed(feed, "Atom source", NOW)[0]
    assert article["url"] == "https://example.org/article"
    assert article["summary"] == "New chip"
    assert article["published"] == "2026-10-16T10:00:00+00:00"


def test_ranking_rewards_recent_relevant_topics_and_drops_week_old_items():
    feed = rss(
        item("AI research", url="https://example.org/ai"),
        item("General technology update", url="https://example.org/general"),
        item("AI older research", date="Thu, 15 Oct 2026 12:00:00 +0000", url="https://example.org/older"),
        item("AI expired", date="Thu, 08 Oct 2026 11:00:00 +0000", url="https://example.org/expired"),
    )
    by_url = {article["url"]: article for article in news.parse_feed(feed, "Kaynak", NOW)}
    assert "https://example.org/expired" not in by_url
    assert by_url["https://example.org/ai"]["score"] > by_url["https://example.org/general"]["score"]
    assert by_url["https://example.org/ai"]["score"] > by_url["https://example.org/older"]["score"]
    assert all(0 <= article["score"] <= 99 for article in by_url.values())


def test_missing_dates_have_low_confidence_and_future_dates_are_bounded():
    articles = news.parse_feed(rss(
        item("AI unknown date", date="nonsense", url="https://example.org/unknown"),
        item("AI future date", date="Sat, 17 Oct 2026 12:00:00 +0000", url="https://example.org/future"),
    ), "Kaynak", NOW)
    assert articles[0]["published"] is None
    assert articles[0]["score"] < articles[1]["score"]
    assert articles[1]["score"] <= 99


def test_invalid_urls_and_empty_titles_are_not_discovered():
    feed = rss(item("", url="https://example.org/empty"), item("Bad scheme", url="javascript:alert(1)"),
               item("Relative", url="/local"), item("Valid", url="https://example.org/good"))
    assert [entry["url"] for entry in news.parse_feed(feed, "Kaynak", NOW)] == ["https://example.org/good"]


def test_article_urls_drop_tracking_and_keep_meaningful_query_parameters():
    first = news.canonical_url("https://EXAMPLE.org/story?utm_source=feed&utm_campaign=launch&page=2&q=chip#section")
    second = news.canonical_url("https://example.org/story?q=chip&page=2&fbclid=tracking&gclid=tracking")
    assert first == second == "https://example.org/story?page=2&q=chip"
    assert news.canonical_url("https://user:password@example.org/story") == ""
    assert news.canonical_url("https:///missing-host") == ""


def test_keyword_matching_does_not_confuse_substrings_or_brand_topics_with_ai():
    articles = news.parse_feed(rss(
        item("Retail mail fails", summary="A plain product update.", url="https://example.org/retail"),
        item("Apple announces a new chip", summary="Product update.", url="https://example.org/apple"),
        item("AI model announced", summary="Research update.", url="https://example.org/ai"),
    ), "Kaynak", NOW)
    by_url = {article["url"]: article for article in articles}
    assert by_url["https://example.org/retail"]["category"] == "Teknoloji"
    assert by_url["https://example.org/apple"]["category"] == "Teknoloji"
    assert by_url["https://example.org/ai"]["category"] == "Yapay zekâ"
    assert by_url["https://example.org/retail"]["score"] < by_url["https://example.org/ai"]["score"]


def test_oversized_feeds_are_rejected_before_parsing():
    with pytest.raises(ValueError, match="büyük"):
        news.parse_feed(b" " * 2_000_001, "Kaynak", NOW)


def test_fetch_news_deduplicates_sources_and_reports_partial_failures(monkeypatch):
    class Response:
        def raise_for_status(self):
            pass

        def iter_content(self, size):
            yield rss(item("AI update", date="bad date"))

    def fetch(url, **kwargs):
        if "bad" in url:
            raise requests.ConnectionError("private debug detail")
        return Response()

    monkeypatch.setattr(news, "FEEDS", (("One", "https://one.invalid/feed"), ("Two", "https://two.invalid/feed"), ("Unavailable", "https://bad.invalid/feed")))
    monkeypatch.setattr(news.requests, "get", fetch)
    articles, warning = news.fetch_news()
    assert len(articles) == 1
    assert "Unavailable" in warning
    assert "private debug detail" not in warning


def test_configured_sources_include_turkish_feed_and_are_all_discovered(monkeypatch):
    sources = dict(news.FEEDS)
    assert sources["ShiftDelete.Net"] == "https://shiftdelete.net/feed"
    calls = set()

    class Response:
        def __init__(self, url):
            self.url = url

        def raise_for_status(self):
            pass

        def iter_content(self, size):
            yield rss(item("Türkçe yapay zekâ haberi", date="bad date", url=self.url + "/article",
                           summary="Teknolojide güncel Türkçe haber."))

    def fetch(url, **kwargs):
        calls.add(url)
        return Response(url)

    monkeypatch.setattr(news.requests, "get", fetch)
    articles, warning = news.fetch_news()
    assert calls == set(sources.values())
    assert {article["source"] for article in articles} == set(sources)
    assert any(article["source"] == "ShiftDelete.Net" and "Türkçe" in article["summary"] for article in articles)
    assert not warning


def test_detailed_refresh_exposes_per_source_health_without_private_exception_text(monkeypatch):
    monkeypatch.setattr(news, "FEEDS", (("Healthy", "https://healthy.invalid/feed"),
                                     ("Unavailable", "https://unavailable.invalid/feed")))

    class Response:
        def raise_for_status(self):
            pass

        def iter_content(self, size):
            yield rss(item("Healthy AI story", date="bad date"))

    def fetch(url, **kwargs):
        if "unavailable" in url:
            raise requests.ConnectionError("never-show-this-credential")
        return Response()

    monkeypatch.setattr(news.requests, "get", fetch)
    result = news.fetch_news_detailed()
    assert len(result["items"]) == 1
    health = {item["source"]: item for item in result["sources"]}
    assert health["Healthy"]["status"] == "ok"
    assert health["Healthy"]["count"] == 1
    assert not health["Healthy"]["error"]
    assert health["Unavailable"]["status"] == "error"
    assert health["Unavailable"]["count"] == 0
    assert health["Unavailable"]["error"]
    assert "never-show-this-credential" not in json.dumps(result)


def test_template_preserves_source_language_without_calling_an_api(monkeypatch):
    monkeypatch.setattr(writing.requests, "post", lambda *args, **kwargs: pytest.fail("Template called an API"))
    article = {"title": "A new chip", "summary": "Verified source wording.", "source": "Publication", "url": "https://example.org/report"}
    result = writing.generate(article, "template")
    assert "Verified source wording." in result["script"]
    assert article["url"] in result["description"]
    assert result["generation_mode"] == "template"
    assert result["editorial_note"]


def test_local_ollama_is_explicit_and_source_link_is_preserved(monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    monkeypatch.setenv("OLLAMA_MODEL", "local-test-model")
    calls = []

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            content = json.dumps({"title": "Türkçe başlık", "script": "Türkçe seslendirme.", "description": "Açıklama", "tags": ["Teknoloji"]})
            return {"message": {"content": "```json\n" + content + "\n```"}}

    def local_post(url, **kwargs):
        calls.append((url, kwargs))
        return Response()

    monkeypatch.setattr(writing.requests, "post", local_post)
    article = {"title": "Source title", "summary": "Source facts", "url": "https://example.org/source"}
    result = writing.generate(article, "ollama")
    assert calls[0][0] == "http://127.0.0.1:11434/api/chat"
    assert calls[0][1]["json"]["model"] == "local-test-model"
    assert article["url"] in result["description"]
    assert result["generation_mode"] == "ollama"


def test_model_output_cannot_override_project_identity_or_inject_internal_fields(monkeypatch):
    model_fields = {"title": "Türkçe başlık", "script": "Türkçe seslendirme.", "description": "Açıklama",
                    "tags": ["Teknoloji"], "id": "attacker-id", "status": "ready",
                    "video_path": "/private/secret.mp4", "access_token": "never-save-this-token",
                    "generation_mode": "injected"}

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"message": {"content": json.dumps(model_fields)}}

    monkeypatch.setattr(writing.requests, "post", lambda *args, **kwargs: Response())
    result = writing.generate({"title": "Source", "url": "https://example.org/story"}, "ollama")
    for field in ("id", "status", "video_path", "access_token"):
        assert field not in result
    assert result["generation_mode"] == "ollama"


@pytest.mark.parametrize("mode", ["openai", "anthropic", "unknown"])
def test_unavailable_or_unknown_providers_fail_before_network(monkeypatch, mode):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(writing.requests, "post", lambda *args, **kwargs: pytest.fail("Unavailable provider called network"))
    with pytest.raises(ValueError):
        writing.generate({"title": "Haber"}, mode)
