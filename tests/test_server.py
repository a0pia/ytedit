"""Local API behavior, persistence, job isolation and authorization boundaries."""
from pathlib import Path
import threading
import time
from urllib.parse import parse_qs, urlparse

import pytest
import requests

from app import server, writing


ARTICLE = {
    "title": "Türkçe teknoloji haberi",
    "summary": "Yeni çip daha az enerji tüketiyor.",
    "source": "Örnek kaynak",
    "url": "https://example.org/teknoloji",
}


@pytest.fixture
def studio(tmp_path, monkeypatch):
    for name in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "ELEVENLABS_API_KEY",
                 "ELEVENLABS_VOICE_ID", "YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET"):
        monkeypatch.delenv(name, raising=False)

    def no_network(*args, **kwargs):
        raise AssertionError("Tests must not call an external API")

    monkeypatch.setattr(requests.sessions.Session, "request", no_network)
    application = server.create_app(tmp_path, testing=True)
    return application, application.test_client(), tmp_path


def create(client, **changes):
    response = client.post("/api/projects", json={**ARTICLE, **changes})
    assert response.status_code == 201, response.get_json()
    return response.get_json()


def await_status(client, ident, status):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        project = client.get(f"/api/projects/{ident}").get_json()
        if project["status"] == status:
            return project
        time.sleep(0.01)
    pytest.fail(f"Project did not reach {status}: {project}")


def fake_render(project, target, opts, progress):
    target.mkdir(parents=True, exist_ok=True)
    video, subtitle = target / "reel.mp4", target / "captions.srt"
    video.write_bytes(b"test-video")
    subtitle.write_text("1\n00:00:00,000 --> 00:00:01,000\nTürkçe haber\n", encoding="utf-8")
    progress(70)
    return {"video_path": str(video), "subtitle_path": str(subtitle), "duration": 1.0}


def test_manual_project_is_persisted_and_editorial_fields_can_be_edited(studio):
    application, client, data = studio
    project = create(client)
    assert project["status"] == "draft"
    assert project["source_url"] == ARTICLE["url"]
    assert project["generation_mode"] == "template"
    assert ARTICLE["summary"] in project["script"]
    edited = client.patch(f"/api/projects/{project['id']}", json={
        "title": "Düzenlenen başlık", "script": "Düzenlenen Türkçe seslendirme.",
        "description": "Kaynak açıklaması", "tags": ["Teknoloji"],
    })
    assert edited.status_code == 200
    restarted = server.create_app(data, testing=True).test_client()
    saved = restarted.get(f"/api/projects/{project['id']}").get_json()
    assert saved["title"] == "Düzenlenen başlık"
    assert saved["script"] == "Düzenlenen Türkçe seslendirme."
    assert saved["tags"] == ["Teknoloji"]
    assert len(restarted.get("/api/projects").get_json()["items"]) == 1
    assert (data / ".session-key").stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("fields", [
    {"title": ""}, {"title": 4}, {"title": "x" * 301},
    {"summary": []}, {"summary": "x" * 2001},
    {"source": {}}, {"source": "x" * 101},
    {"url": "javascript:alert(1)"}, {"url": "file:///etc/passwd"},
    {"url": "ftp://example.org/file"}, {"url": ["https://example.org"]},
])
def test_manual_input_validation(studio, fields):
    _, client, _ = studio
    response = client.post("/api/projects", json={**ARTICLE, **fields})
    assert response.status_code == 400
    assert client.get("/api/projects").get_json()["items"] == []


@pytest.mark.parametrize("changes", [
    {"title": " "}, {"title": "x" * 101}, {"script": None},
    {"script": "x" * 1201}, {"description": "x" * 4501},
    {"tags": "Teknoloji"}, {"tags": ["a"] * 13}, {"tags": [None]},
    {"tags": [""]}, {"tags": ["x" * 61]}, {"tags": ["x" * 60] * 8},
])
def test_edit_validation_preserves_saved_document(studio, changes):
    _, client, _ = studio
    project = create(client)
    response = client.patch(f"/api/projects/{project['id']}", json=changes)
    assert response.status_code == 400
    assert client.get(f"/api/projects/{project['id']}").get_json() == project


def test_invalid_json_and_missing_project_return_json_errors(studio):
    _, client, _ = studio
    assert client.post("/api/projects", data="plain text").status_code == 400
    assert client.post("/api/projects", json=[]).status_code == 400
    malformed = client.post("/api/projects", data="{", content_type="application/json")
    assert malformed.status_code == 400
    assert "error" in malformed.get_json()
    missing = client.get("/api/projects/does-not-exist")
    assert missing.status_code == 404
    assert "error" in missing.get_json()


def test_manual_url_is_metadata_and_never_fetched(studio):
    _, client, _ = studio
    # Even a private-host source is stored as a citation, never a fetch target.
    project = create(client, url="http://169.254.169.254/latest/meta-data/")
    assert project["source_url"] == "http://169.254.169.254/latest/meta-data/"


def test_editing_a_rendered_project_invalidates_its_media(studio, monkeypatch):
    _, client, _ = studio
    monkeypatch.setattr(server.media, "render", fake_render)
    project = create(client)
    endpoint = f"/api/projects/{project['id']}"
    assert client.post(endpoint + "/render", json={"speech": False}).status_code == 202
    ready = await_status(client, project["id"], "ready")
    assert client.get(ready["video_url"]).data == b"test-video"
    assert "Türkçe haber" in client.get(ready["subtitle_url"]).get_data(as_text=True)
    # The worker releases its active marker just after committing ready status.
    deadline = time.monotonic() + 5
    while True:
        edited = client.patch(endpoint, json={"script": "Yeni seslendirme."})
        if edited.status_code != 409 or time.monotonic() > deadline:
            break
        time.sleep(0.01)
    assert edited.status_code == 200
    updated = edited.get_json()
    assert updated["status"] == "draft"
    for name in ("video_path", "video_url", "subtitle_url", "duration"):
        assert name not in updated


def test_duplicate_render_and_edit_are_blocked_while_job_is_running(studio, monkeypatch):
    _, client, _ = studio
    started, release = threading.Event(), threading.Event()
    calls = []

    def slow_render(*args):
        calls.append(1)
        started.set()
        assert release.wait(timeout=5)
        return fake_render(*args)

    monkeypatch.setattr(server.media, "render", slow_render)
    project = create(client)
    endpoint = f"/api/projects/{project['id']}"
    try:
        assert client.post(endpoint + "/render", json={"speech": False}).status_code == 202
        assert started.wait(timeout=2)
        assert client.post(endpoint + "/render", json={}).status_code == 409
        assert client.patch(endpoint, json={"title": "Too soon"}).status_code == 409
        assert len(calls) == 1
    finally:
        release.set()
        await_status(client, project["id"], "ready")


@pytest.mark.parametrize("options", [{"speech": "false"}, {"style": "unknown"}, {"tts_provider": "paid"}])
def test_invalid_render_options_never_start_a_job(studio, monkeypatch, options):
    _, client, _ = studio
    monkeypatch.setattr(server.media, "render", lambda *args: pytest.fail("Invalid job started"))
    project = create(client)
    assert client.post(f"/api/projects/{project['id']}/render", json=options).status_code == 400
    assert client.get(f"/api/projects/{project['id']}").get_json()["status"] == "draft"


@pytest.mark.parametrize("mode, variable", [("openai", "OPENAI_API_KEY"), ("anthropic", "ANTHROPIC_API_KEY")])
def test_missing_paid_provider_credentials_do_not_call_network(studio, mode, variable):
    _, client, _ = studio
    response = client.post("/api/projects", json={**ARTICLE, "mode": mode})
    assert response.status_code == 400
    assert variable in response.get_json()["error"]
    assert client.get("/api/projects").get_json()["items"] == []


def test_provider_request_errors_do_not_disclose_credentials(studio, monkeypatch):
    _, client, _ = studio
    secret = "VERY-PRIVATE-TEST-API-KEY"
    monkeypatch.setenv("OPENAI_API_KEY", secret)

    def unavailable(*args, **kwargs):
        raise requests.ConnectionError(f"https://provider.invalid/?key={secret}")

    monkeypatch.setattr(writing.requests, "post", unavailable)
    response = client.post("/api/projects", json={**ARTICLE, "mode": "openai"})
    assert response.status_code == 502
    assert secret not in response.get_data(as_text=True)
    assert "provider.invalid" not in response.get_data(as_text=True)


def oauth_state(client, monkeypatch):
    monkeypatch.setenv("YOUTUBE_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("YOUTUBE_CLIENT_SECRET", "test-client-secret")
    response = client.get("/api/youtube/connect")
    assert response.status_code == 200
    return parse_qs(urlparse(response.get_json()["url"]).query)["state"][0]


def test_oauth_callback_rejects_wrong_state_then_accepts_valid_state_only_once(studio, monkeypatch):
    application, client, _ = studio
    calls = []
    monkeypatch.setattr(server.youtube, "exchange", lambda code, path: calls.append(code))
    state = oauth_state(client, monkeypatch)
    # An external browser does not share Electron's cookie jar.
    external_browser = application.test_client()
    assert external_browser.get("/oauth/youtube/callback", query_string={"state": "wrong", "code": "code"}).status_code == 400
    assert calls == []
    query = {"state": state, "code": "single-use-code"}
    assert external_browser.get("/oauth/youtube/callback", query_string=query).status_code == 200
    assert calls == ["single-use-code"]
    assert external_browser.get("/oauth/youtube/callback", query_string=query).status_code == 400
    assert calls == ["single-use-code"]


def test_oauth_expired_state_is_not_exchanged(studio, monkeypatch):
    _, client, _ = studio
    monkeypatch.setattr(server.youtube, "exchange", lambda *args: pytest.fail("Expired OAuth was exchanged"))
    state = oauth_state(client, monkeypatch)
    initial = time.time()
    monkeypatch.setattr(server.time, "time", lambda: initial + 601)
    response = client.get("/oauth/youtube/callback", query_string={"state": state, "code": "expired"})
    assert response.status_code == 400


@pytest.mark.parametrize("confirmation", [None, False, "true", 1])
def test_upload_requires_explicit_boolean_confirmation(studio, monkeypatch, confirmation):
    _, client, _ = studio
    monkeypatch.setattr(server.youtube, "upload", lambda *args: pytest.fail("Unconfirmed upload started"))
    project = create(client)
    payload = {} if confirmation is None else {"confirm": confirmation}
    response = client.post(f"/api/projects/{project['id']}/upload", json=payload)
    assert response.status_code == 400
    assert "onay" in response.get_json()["error"]


def test_upload_requires_connected_account(studio, monkeypatch):
    _, client, _ = studio
    monkeypatch.setattr(server.youtube, "upload", lambda *args: pytest.fail("Unauthenticated upload started"))
    project = create(client)
    response = client.post(f"/api/projects/{project['id']}/upload", json={"confirm": True})
    assert response.status_code == 400
    assert "YouTube" in response.get_json()["error"]


def test_media_paths_cannot_traverse_outside_render_directory(studio):
    _, client, data = studio
    (data / "outside.mp4").write_bytes(b"private")
    for path in ("/media/../outside.mp4", "/media/%2e%2e/outside.mp4", "/media/.session-key", "/media/../../.session-key"):
        response = client.get(path)
        assert response.status_code == 404
        assert b"private" not in response.data


def test_production_rejects_foreign_hosts_and_cross_origin_mutations(studio):
    application, client, _ = studio
    application.testing = False
    local = "http://127.0.0.1:8787"
    assert client.get("/api/projects", base_url="http://attacker.invalid:8787").status_code == 403
    assert client.post("/api/projects", base_url=local, json=ARTICLE,
                       headers={"Origin": "https://attacker.invalid"}).status_code == 403
    assert client.post("/api/projects", base_url=local, json=ARTICLE,
                       headers={"Origin": "http://127.0.0.1:9999"}).status_code == 403
    assert client.post("/api/projects", base_url=local, json=ARTICLE,
                       headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403
    assert client.post("/api/projects", base_url=local, json=ARTICLE,
                       headers={"Origin": local, "Sec-Fetch-Site": "same-origin"}).status_code == 201


def test_production_youtube_connect_rejects_cross_site_requests(studio):
    application, client, _ = studio
    application.testing = False
    response = client.get("/api/youtube/connect", base_url="http://127.0.0.1:8787",
                          headers={"Sec-Fetch-Site": "cross-site"})
    assert response.status_code == 403


def test_api_responses_have_local_application_security_headers(studio):
    _, client, _ = studio
    response = client.get("/api/projects")
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "connect-src 'self'" in response.headers["Content-Security-Policy"]
