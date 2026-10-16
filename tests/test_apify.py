"""Apify integration with a fake HTTP session: no network, no real token."""
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from app import apify, server

TOKEN = "apify_api_" + "x" * 36


class FakeResponse:
    def __init__(self, status=200, payload=None, content_type="application/json", body=None):
        self.status_code = status
        self.headers = {"Content-Type": content_type}
        self._body = body if body is not None else json.dumps(payload or []).encode()

    def iter_content(self, size):
        for index in range(0, len(self._body), size):
            yield self._body[index:index + size]

    def close(self):
        pass


class FakeSession:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append(("POST", url, kwargs))
        return self.responses.pop(0)

    def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        return self.responses.pop(0)


@pytest.fixture
def token(monkeypatch):
    monkeypatch.setenv("APIFY_TOKEN", TOKEN)


def test_missing_token_never_calls_apify(monkeypatch):
    monkeypatch.delenv("APIFY_TOKEN", raising=False)
    session = FakeSession([])
    with pytest.raises(apify.ApifyError, match="APIFY_TOKEN"):
        apify.run_actor("apify/cheerio-scraper", {}, session=session)
    assert session.calls == []


def test_token_travels_only_in_the_authorization_header(token):
    session = FakeSession([FakeResponse(payload=[{"title": "ok"}])])
    items = apify.run_actor("streamers/youtube-scraper", {"q": 1}, session=session)
    assert items == [{"title": "ok"}]
    _method, url, kwargs = session.calls[0]
    assert url == "https://api.apify.com/v2/acts/streamers~youtube-scraper/run-sync-get-dataset-items"
    assert TOKEN not in url and TOKEN not in json.dumps(kwargs["params"])
    assert kwargs["headers"]["Authorization"] == f"Bearer {TOKEN}"


@pytest.mark.parametrize("status,message", [(401, "geçersiz"), (402, "kredisi"), (500, "HTTP 500")])
def test_apify_errors_are_actionable(token, status, message):
    with pytest.raises(apify.ApifyError, match=message):
        apify.run_actor("apify/cheerio-scraper", {}, session=FakeSession([FakeResponse(status=status)]))


def test_trends_parse_each_platform_and_fail_independently(token):
    session = FakeSession([
        FakeResponse(payload=[{"title": "Claude yeni sürüm inceleme", "viewCount": 120000, "url": "https://y/1"}]),
        FakeResponse(status=402),
        FakeResponse(payload=[{"text": "Claude kod yazmada çok hızlı", "likeCount": 900, "retweetCount": 50,
                               "url": "https://x/1"}]),
    ])
    result = apify.fetch_trends(session=session)
    assert [row["platform"] for row in result["items"]] == ["youtube", "x"]
    assert [source["status"] for source in result["sources"]] == ["ok", "error", "ok"]


def test_hype_matches_boost_news_that_share_trending_words():
    trends = [{"platform": "youtube", "title": "Claude modeli kodlama testinde", "url": "u", "engagement": 500000},
              {"platform": "tiktok", "title": "Yeni telefon kamerası", "url": "t", "engagement": 1000}]
    news = [{"title": "Anthropic Claude modeli güncellendi", "summary": "", "score": 50},
            {"title": "Belediye otobüs saatleri", "summary": "", "score": 60}]
    ranked = apify.hype_matches(news, trends)
    assert ranked[0]["trend_boost"] > 0 and "claude" in ranked[0]["trend_words"]
    assert ranked[0]["trend_posts"][0]["platform"] == "youtube"
    assert ranked[1]["trend_boost"] == 0 and ranked[1]["hype_score"] == 60


def test_private_and_local_addresses_are_never_downloaded(tmp_path):
    for url in ("http://127.0.0.1/a.jpg", "http://localhost/a.jpg", "file:///etc/passwd", "http://10.0.0.5/x.png",
                "http://user:pass@example.com/a.jpg"):
        assert not apify.public_url(url)
    session = FakeSession([])
    with pytest.raises(apify.ApifyError, match="herkese açık"):
        apify.download_image("http://127.0.0.1/a.jpg", tmp_path / "x", session=session)
    assert session.calls == []


def test_discovered_images_are_absolute_and_deduplicated(token):
    session = FakeSession([FakeResponse(payload=[{"url": "https://news.example/a/b", "meta": ["/og.jpg"],
                                                   "images": [{"src": "img/1.png", "alt": "Çip"},
                                                              {"src": "/og.jpg", "alt": "tekrar"},
                                                              {"src": "logo.svg", "alt": "svg"}]}])])
    images = apify.discover_images("https://news.example/a/b", session=session)
    assert [image["url"] for image in images] == ["https://news.example/og.jpg", "https://news.example/a/img/1.png"]
    assert images[0]["kind"] == "og"


@pytest.fixture
def client(tmp_path):
    app = server.create_app(tmp_path, testing=True)
    return app.test_client(), tmp_path


def test_trends_endpoint_requires_token_and_reranks_news(client, monkeypatch):
    test_client, _ = client
    monkeypatch.delenv("APIFY_TOKEN", raising=False)
    assert test_client.get("/api/trends").get_json()["configured"] is False
    assert test_client.post("/api/trends/refresh").status_code == 400
    monkeypatch.setenv("APIFY_TOKEN", TOKEN)
    monkeypatch.setattr(server.apify, "fetch_trends", lambda: {
        "items": [{"platform": "x", "title": "Claude çok konuşuluyor", "url": "u", "engagement": 1000}],
        "sources": [{"platform": "x", "status": "ok", "count": 1, "error": None}]})
    response = test_client.post("/api/trends/refresh")
    assert response.status_code == 200
    assert response.get_json()["items"][0]["title"] == "Claude çok konuşuluyor"
    assert test_client.get("/api/trends").get_json()["last_refreshed"]


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg is required")
def test_image_must_come_from_discovered_candidates_and_is_normalized(client, monkeypatch, tmp_path):
    test_client, _ = client
    created = test_client.post("/api/projects", json={"title": "Claude yeni sürüm", "summary": "Anthropic duyurdu.",
                                                     "source": "Örnek", "url": "https://news.example/a"}).get_json()
    ident = created["id"]
    assert test_client.post(f"/api/projects/{ident}/image", json={"url": "https://evil.example/x.jpg"}).status_code == 400
    monkeypatch.setattr(server.apify, "public_url", lambda url: True)
    monkeypatch.setattr(server.apify, "discover_images",
                        lambda url: [{"url": "https://news.example/og.jpg", "alt": "", "kind": "og"}])
    assert test_client.post(f"/api/projects/{ident}/images/discover").get_json()["candidates"]
    source = tmp_path / "source.png"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "color=c=blue:s=1600x900",
                    "-frames:v", "1", str(source)], check=True)
    monkeypatch.setattr(server.apify, "download_image", lambda url, target: shutil.copyfile(source, target))
    chosen = test_client.post(f"/api/projects/{ident}/image", json={"url": "https://news.example/og.jpg"})
    assert chosen.status_code == 200, chosen.get_json()
    assert chosen.get_json()["image"]["credit"] == "news.example"
    picture = test_client.get(f"/api/projects/{ident}/image/file")
    assert picture.status_code == 200 and picture.mimetype == "image/jpeg"
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=width", "-of", "csv=p=0", "-"],
                           input=picture.data, capture_output=True, check=True)
    assert int(probe.stdout) == 1080
    assert "image" not in test_client.delete(f"/api/projects/{ident}/image").get_json()
    assert test_client.get(f"/api/projects/{ident}/image/file").status_code == 404
    assert not Path(created.get("video_path", "/nonexistent")).exists()
