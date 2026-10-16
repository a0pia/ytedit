"""Turkish translation contracts with deterministic models and no live APIs."""
from copy import deepcopy
from datetime import datetime, timezone
import json
import sqlite3
import threading
import time

import pytest
import requests

from app import server, translation, writing


ARTICLE = {
    "title": "New chip uses 20 percent less energy",
    "summary": "Acme says its new chip uses 20 percent less energy.",
    "source": "Example News",
    "url": "https://example.org/chips?story=20",
}
TURKISH_ARTICLE = {
    "title": "Yeni çip yüzde 20 daha az enerji tüketiyor",
    "summary": "Acme, yeni çipinin yüzde 20 daha az enerji tükettiğini söylüyor.",
}
TURKISH_PROJECT = {
    "title": "Yeni çip yüzde 20 daha az enerji tüketiyor",
    "script": "Acme yeni çipini tanıttı. Şirket yüzde 20 daha az enerji tükettiğini söylüyor.",
    "description": "Acme'nin yeni çipine ilişkin kaynak haberi.",
    "tags": ["Teknoloji", "Çip"],
}


@pytest.fixture
def studio(tmp_path, monkeypatch):
    for name in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET"):
        monkeypatch.delenv(name, raising=False)

    def no_network(*args, **kwargs):
        raise AssertionError("Translation tests must not call a live API")

    monkeypatch.setattr(requests.sessions.Session, "request", no_network)
    application = server.create_app(tmp_path, testing=True)
    return application, application.test_client(), tmp_path


def create(client, **fields):
    response = client.post("/api/projects", json={**ARTICLE, **fields})
    assert response.status_code == 201, response.get_json()
    return response.get_json()


def save(data, project, kind="project"):
    with sqlite3.connect(data / "studio.sqlite3") as db:
        db.execute("INSERT OR REPLACE INTO documents VALUES(?,?,?)",
                   (kind, project["id"], json.dumps(project)))


def saved(data, ident):
    with sqlite3.connect(data / "studio.sqlite3") as db:
        row = db.execute("SELECT body FROM documents WHERE kind='project' AND id=?", (ident,)).fetchone()
    return json.loads(row[0])


def ready(client, data):
    project = create(client)
    target = data / "renders" / project["id"] / "first"
    target.mkdir(parents=True)
    video = target / "reel.mp4"
    video.write_bytes(b"existing-video")
    project.update(status="ready", progress=100, video_path=str(video), duration=3.5,
                   video_url=f"/media/{project['id']}/first/reel.mp4",
                   subtitle_url=f"/media/{project['id']}/first/captions.srt",
                   render_options={"video_design": "classic", "speech": False}, provider="local",
                   voice="tr", speech=False, subtitle_timing="estimated", scene_count=2, design="classic")
    save(data, project)
    return project


def assert_timestamp(value):
    parsed = datetime.fromisoformat(value)
    assert parsed.tzinfo is not None
    assert abs((datetime.now(timezone.utc) - parsed).total_seconds()) < 30


@pytest.mark.parametrize("provider", [None, "openai", "anthropic"])
def test_article_translation_uses_only_selected_provider_and_preserves_provenance(monkeypatch, provider):
    calls = []

    def model(system, payload, mode):
        calls.append((system, payload, mode))
        return {**TURKISH_ARTICLE, "source": "Forged", "source_url": "https://evil.test",
                "id": "forged", "video_path": "/tmp/model.mp4"}

    monkeypatch.setattr(writing, "request_json", model)
    original = deepcopy(ARTICLE)
    result = translation.translate_article(ARTICLE) if provider is None else translation.translate_article(ARTICLE, provider)
    assert ARTICLE == original
    assert calls[0][1] == {"title": ARTICLE["title"], "summary": ARTICLE["summary"]}
    assert calls[0][2] == (provider or "ollama")
    assert "Türkçe" in calls[0][0]
    assert {key: result[key] for key in TURKISH_ARTICLE} == TURKISH_ARTICLE
    assert result["original_title"] == ARTICLE["title"]
    assert result["original_summary"] == ARTICLE["summary"]
    assert result["source"] == ARTICLE["source"]
    assert result["source_url"] == ARTICLE["url"]
    assert result["source_language"] == "auto" and result["target_language"] == "tr"
    assert result["provider"] == (provider or "ollama")
    assert "id" not in result and "video_path" not in result
    assert_timestamp(result["translated_at"])


@pytest.mark.parametrize("provider", ["template", "unknown", None])
def test_invalid_translation_providers_never_call_a_model(monkeypatch, provider):
    monkeypatch.setattr(writing, "request_json", lambda *args: pytest.fail("Invalid provider reached model"))
    with pytest.raises(ValueError):
        translation.translate_article(ARTICLE, provider)


@pytest.mark.parametrize("output", [
    [], {"title": "", "summary": "Özet"}, {"title": "x" * 301, "summary": "Özet"},
    {"title": "Başlık", "summary": "x" * 2001}, {"title": "Başlık", "summary": None},
])
def test_article_translation_rejects_invalid_model_output(monkeypatch, output):
    monkeypatch.setattr(writing, "request_json", lambda *args: output)
    with pytest.raises(ValueError):
        translation.translate_article(ARTICLE)


def test_empty_article_summary_stays_empty_without_invented_details(monkeypatch):
    monkeypatch.setattr(writing, "request_json", lambda *args: {"title": "Türkçe başlık", "summary": ""})
    result = translation.translate_article({**ARTICLE, "summary": ""})
    assert result["summary"] == result["original_summary"] == ""


def test_project_translation_retains_first_originals_and_adds_bounded_source_citation(monkeypatch):
    project = {"title": "English title", "script": "English script", "description": "Original details",
               "tags": ["Technology"], "source_url": ARTICLE["url"], "source": ARTICLE["source"]}
    original = deepcopy(project)
    monkeypatch.setattr(writing, "request_json", lambda *args: {
        **TURKISH_PROJECT, "description": "Ç" * 4500, "id": "forged",
        "source_url": "https://evil.test", "status": "ready", "video_path": "/tmp/forged.mp4"})
    first = translation.translate_project(project)
    assert project == original
    assert first["language"] == "tr"
    assert len(first["description"]) == 4500
    assert first["description"].endswith("Kaynak: " + ARTICLE["url"])
    assert set(first) == {"title", "script", "description", "tags", "language", "translation", "editorial_note"}
    second = translation.translate_project({**project, **first}, "anthropic")
    for key in ("title", "script", "description", "tags"):
        assert second["translation"]["original_" + key] == original[key]
    assert second["translation"]["provider"] == "anthropic"
    assert_timestamp(second["translation"]["translated_at"])


@pytest.mark.parametrize("changes", [
    {"title": "x" * 101}, {"script": "x" * 1201}, {"description": "x" * 4501},
    {"tags": ["a"] * 13}, {"tags": ["x" * 60] * 8},
])
def test_project_translation_rejects_invalid_editorial_fields(monkeypatch, changes):
    monkeypatch.setattr(writing, "request_json", lambda *args: {**TURKISH_PROJECT, **changes})
    with pytest.raises(ValueError):
        translation.translate_project({"title": "Original", "script": "Original script"})


def test_default_translation_transport_uses_local_ollama_and_turkish_prompt(monkeypatch):
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    calls = []

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"message": {"content": json.dumps(TURKISH_ARTICLE, ensure_ascii=False)}}

    def post(url, **kwargs):
        calls.append((url, kwargs))
        return Response()

    monkeypatch.setattr(requests, "post", post)
    assert translation.translate_article(ARTICLE)["title"] == TURKISH_ARTICLE["title"]
    assert len(calls) == 1
    url, options = calls[0]
    assert url == "http://127.0.0.1:11434/api/chat"
    assert "headers" not in options
    assert options["json"]["model"] == "llama3.2:3b"
    assert options["json"]["format"] == "json" and options["json"]["stream"] is False
    assert "Türkçe" in options["json"]["messages"][0]["content"]
    assert json.loads(options["json"]["messages"][1]["content"]) == {
        "title": ARTICLE["title"], "summary": ARTICLE["summary"]}


def test_ollama_failure_never_falls_back_to_configured_paid_api(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "paid-key-must-not-be-used")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "another-unused-key")
    calls = []

    def fail(url, **kwargs):
        calls.append(url)
        raise requests.ConnectionError("Ollama unavailable")

    monkeypatch.setattr(requests, "post", fail)
    with pytest.raises(requests.ConnectionError):
        translation.translate_article(ARTICLE)
    assert len(calls) == 1 and calls[0].endswith("/api/chat")


def test_article_translation_api_is_a_preview_and_can_use_cached_news(studio, monkeypatch):
    _, client, data = studio
    existing = create(client)
    article = {**ARTICLE, "id": "cached-story", "score": 40}
    save(data, article, "news")
    calls = []

    def model(system, payload, provider):
        calls.append((payload, provider))
        return TURKISH_ARTICLE

    monkeypatch.setattr(writing, "request_json", model)
    for payload in (ARTICLE, {"news_id": "cached-story"}):
        response = client.post("/api/translate", json=payload)
        assert response.status_code == 200, response.get_json()
        assert response.get_json()["source_url"] == ARTICLE["url"]
        assert response.get_json()["provider"] == "ollama"
    assert all(provider == "ollama" for _, provider in calls)
    assert all(payload["title"] == ARTICLE["title"] for payload, _ in calls)
    assert client.get("/api/projects").get_json()["items"] == [existing]


def test_translated_article_creates_turkish_template_with_only_known_provenance(studio, monkeypatch):
    _, client, _ = studio
    monkeypatch.setattr(writing, "request_json", lambda *args: TURKISH_ARTICLE)
    translated = client.post("/api/translate", json=ARTICLE).get_json()
    translated.update(id="model-id", video_path="/tmp/forged.mp4", status="ready",
                      source_url="https://forged.test", access_token="never-store-this")
    project = create(client, **TURKISH_ARTICLE, language="tr", mode="template", translation=translated)
    assert project["language"] == "tr" and project["generation_mode"] == "template"
    assert TURKISH_ARTICLE["summary"] in project["script"]
    assert project["source_url"] == ARTICLE["url"] and project["source"] == ARTICLE["source"]
    assert project["id"] != "model-id" and project["status"] == "draft"
    assert set(project["translation"]) == {
        "original_title", "original_summary", "provider", "source_language", "target_language", "translated_at"}
    assert project["translation"]["original_title"] == ARTICLE["title"]
    assert "never-store-this" not in json.dumps(project)


def test_cached_news_cannot_silently_replace_translated_article_on_create(studio, monkeypatch):
    _, client, data = studio
    save(data, {**ARTICLE, "id": "cached-story"}, "news")
    monkeypatch.setattr(writing, "request_json", lambda *args: TURKISH_ARTICLE)
    translated = client.post("/api/translate", json=ARTICLE).get_json()
    response = client.post("/api/projects", json={"news_id": "cached-story", "language": "tr", "translation": translated})
    assert response.status_code == 400
    assert client.get("/api/projects").get_json()["items"] == []


def test_existing_project_translation_is_synchronous_and_invalidates_render(studio, monkeypatch):
    _, client, data = studio
    project = ready(client, data)
    monkeypatch.setattr(writing, "request_json", lambda *args: {**TURKISH_PROJECT, "source_url": "https://forged.test"})
    response = client.post(f"/api/projects/{project['id']}/translate", json={})
    assert response.status_code == 200, response.get_json()
    result = response.get_json()
    assert result["script"] == TURKISH_PROJECT["script"]
    assert result["status"] == "draft" and result["progress"] == 0
    assert result["language"] == "tr"
    for key in ("id", "source", "source_url", "created"):
        assert result[key] == project[key]
    assert result["translation"]["original_script"] == project["script"]
    for key in ("video_path", "video_url", "subtitle_url", "duration", "render_options", "provider", "voice", "speech", "subtitle_timing", "scene_count", "design"):
        assert key not in saved(data, project["id"])


@pytest.mark.parametrize("failure,status", [(ValueError("Invalid translation"), 400), (requests.ConnectionError("private-token"), 502)])
def test_translation_failure_restores_exact_project_including_existing_video(studio, monkeypatch, failure, status):
    _, client, data = studio
    project = ready(client, data)

    def fail(*args):
        raise failure

    monkeypatch.setattr(writing, "request_json", fail)
    endpoint = f"/api/projects/{project['id']}"
    response = client.post(endpoint + "/translate", json={})
    assert response.status_code == status
    assert "private-token" not in response.get_data(as_text=True)
    assert saved(data, project["id"]) == project
    assert client.get(project["video_url"]).data == b"existing-video"
    assert client.patch(endpoint, json={"description": "Still editable"}).status_code == 200


def test_translating_project_is_visible_and_blocks_conflicting_operations(studio, monkeypatch):
    application, client, data = studio
    project = ready(client, data)
    entered, release = threading.Event(), threading.Event()
    responses = []

    def model(*args):
        entered.set()
        assert release.wait(5), "Test did not release translation"
        return TURKISH_PROJECT

    monkeypatch.setattr(writing, "request_json", model)
    monkeypatch.setattr(server.youtube, "configured", lambda: True)
    (data / "youtube-tokens.json").write_text("{}")
    endpoint = f"/api/projects/{project['id']}"

    def translate_in_thread():
        with application.test_client() as background:
            responses.append(background.post(endpoint + "/translate", json={}))

    worker = threading.Thread(target=translate_in_thread)
    worker.start()
    try:
        assert entered.wait(5)
        assert client.get(endpoint).get_json()["status"] == "translating"
        assert client.patch(endpoint, json={"script": "Racing edit"}).status_code == 409
        assert client.delete(endpoint).status_code == 409
        assert client.post(endpoint + "/render", json={"speech": False}).status_code == 409
        assert client.post(endpoint + "/upload", json={"confirm": True}).status_code == 409
        assert client.post(endpoint + "/translate", json={}).status_code == 409
    finally:
        release.set()
        worker.join(timeout=5)
    assert not worker.is_alive()
    assert responses[0].status_code == 200
    assert client.get(endpoint).get_json()["status"] == "draft"


def test_restart_recovers_interrupted_translation(studio):
    _, client, data = studio
    project = create(client)
    save(data, {**project, "status": "translating"})
    restarted = server.create_app(data, testing=True).test_client()
    recovered = restarted.get(f"/api/projects/{project['id']}").get_json()
    assert recovered["status"] == "error" and recovered["error"]
    assert recovered["script"] == project["script"]


def test_duplicate_and_export_preserve_turkish_language_and_translation_provenance(studio, monkeypatch):
    _, client, _ = studio
    original = create(client)
    monkeypatch.setattr(writing, "request_json", lambda *args: TURKISH_PROJECT)
    endpoint = f"/api/projects/{original['id']}"
    translated = client.post(endpoint + "/translate", json={}).get_json()
    duplicate = client.post(endpoint + "/duplicate", json={}).get_json()
    exported = json.loads(client.get(endpoint + "/export").data)
    for document in (duplicate, exported):
        assert document["language"] == "tr"
        assert document["translation"] == translated["translation"]
        assert document["source_url"] == ARTICLE["url"]
        assert document["script"] == TURKISH_PROJECT["script"]
    assert duplicate["id"] != original["id"]


def test_status_reports_translation_setup_and_flags_without_secrets(studio, monkeypatch):
    _, client, _ = studio
    monkeypatch.setenv("OPENAI_API_KEY", "secret-openai-value")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "secret-anthropic-value")

    class Models:
        def raise_for_status(self):
            pass

        def json(self):
            return {"models": [{"name": "llama3.2:3b"}]}

    monkeypatch.setenv("OLLAMA_MODEL", "llama3.2:3b")
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: Models())
    monkeypatch.setattr(server.media, "capabilities", lambda: {"ffmpeg": True, "tts": True})
    response = client.get("/api/status")
    assert response.status_code == 200
    info = response.get_json()["translation"]
    assert info["default_provider"] == "ollama" and info["target_language"] == "tr"
    assert info["providers"] == {"ollama": True, "openai": True, "anthropic": True}
    assert "ollama pull llama3.2:3b" in info["setup_commands"]
    assert "secret-openai-value" not in response.get_data(as_text=True)
    assert "secret-anthropic-value" not in response.get_data(as_text=True)


@pytest.mark.parametrize("design", [None, "kinetic", "classic"])
def test_render_preserves_video_design_and_scene_count(studio, monkeypatch, design):
    _, client, _ = studio
    project = create(client)
    seen = []

    def render(project, target, opts, progress):
        seen.append(opts.copy())
        target.mkdir(parents=True)
        video, subtitle = target / "reel.mp4", target / "captions.srt"
        video.write_bytes(b"rendered-video")
        subtitle.write_text("", encoding="utf-8")
        return {"video_path": str(video), "subtitle_path": str(subtitle), "duration": 3.0,
                "design": opts.get("video_design", "kinetic"), "scene_count": 4}

    monkeypatch.setattr(server.media, "render", render)
    opts = {"speech": False, **({"video_design": design} if design else {})}
    endpoint = f"/api/projects/{project['id']}"
    assert client.post(endpoint + "/render", json=opts).status_code == 202
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        result = client.get(endpoint).get_json()
        if result["status"] == "ready":
            break
        time.sleep(0.01)
    assert result["status"] == "ready", result
    assert result["design"] == (design or "kinetic") and result["scene_count"] == 4
    assert seen[0].get("video_design", "kinetic") == (design or "kinetic")


def test_unknown_video_design_is_rejected_before_rendering(studio, monkeypatch):
    _, client, _ = studio
    project = create(client)
    monkeypatch.setattr(server.media, "render", lambda *args: pytest.fail("Invalid design rendered"))
    response = client.post(f"/api/projects/{project['id']}/render", json={"video_design": "unknown"})
    assert response.status_code == 400
    assert client.get(f"/api/projects/{project['id']}").get_json() == project


def test_published_project_requires_duplicate_before_translation(studio, monkeypatch):
    _, client, data = studio
    project = ready(client, data)
    project.update(youtube_id='existing-video', youtube_url='https://www.youtube.com/watch?v=existing-video')
    save(data, project)
    monkeypatch.setattr(writing, 'request_json', lambda *args: pytest.fail('Published project must not invoke a model'))
    response = client.post(f"/api/projects/{project['id']}/translate", json={'provider': 'ollama'})
    assert response.status_code == 409
    assert 'çoğalt' in response.get_json()['error']
    assert saved(data, project['id']) == project
    copy = client.post(f"/api/projects/{project['id']}/duplicate", json={}).get_json()
    assert 'youtube_id' not in copy
    assert copy['status'] == 'draft'
