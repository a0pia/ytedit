"""Local API behavior, persistence, job isolation and authorization boundaries."""
from datetime import datetime, timedelta, timezone
import json
import sqlite3
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
    return {"video_path": str(video), "subtitle_path": str(subtitle), "duration": 1.0,
            "provider": "Test local voice", "voice": "tr", "speech": opts.get("speech", True),
            "subtitle_timing": "sentence_audio" if opts.get("speech", True) else "estimated"}


def save_document(data, project):
    """Seed persisted legacy/adversarial data without exposing a test-only HTTP route."""
    with sqlite3.connect(data / "studio.sqlite3") as db:
        db.execute("INSERT OR REPLACE INTO documents VALUES(?,?,?)",
                   ("project", project["id"], json.dumps(project)))


def saved_document(data, ident):
    with sqlite3.connect(data / "studio.sqlite3") as db:
        row = db.execute("SELECT body FROM documents WHERE kind='project' AND id=?", (ident,)).fetchone()
    return json.loads(row[0])


def ready_project(client, data, **changes):
    project = create(client)
    target = data / "renders" / project["id"] / "first"
    output = fake_render(project, target, {"speech": False}, lambda value: None)
    project.update(status="ready", progress=100, video_path=output["video_path"], duration=1,
                   video_url=f"/media/{project['id']}/first/reel.mp4",
                   subtitle_url=f"/media/{project['id']}/first/captions.srt")
    project.update(changes)
    save_document(data, project)
    return project


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
    _, client, data = studio
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
        assert name not in saved_document(data, project["id"])


@pytest.mark.parametrize("changes", [
    {"description": "Yeni yayın açıklaması"}, {"tags": ["Gündem", "Teknoloji"]},
    {}, {"title": ARTICLE["title"]},
])
def test_metadata_and_noop_edits_preserve_existing_video(studio, changes):
    _, client, data = studio
    project = ready_project(client, data)
    response = client.patch(f"/api/projects/{project['id']}", json=changes)
    assert response.status_code == 200
    saved = response.get_json()
    assert saved["status"] == "ready"
    for field in ("video_url", "subtitle_url", "duration"):
        assert saved[field] == project[field]
    assert saved_document(data, project["id"])["video_path"] == project["video_path"]
    for field, value in changes.items():
        assert saved[field] == value


def test_changed_video_title_invalidates_render(studio):
    _, client, data = studio
    project = ready_project(client, data)
    response = client.patch(f"/api/projects/{project['id']}", json={"title": "Ekranda yeni başlık"})
    assert response.status_code == 200
    saved = response.get_json()
    assert saved["status"] == "draft"
    assert "video_url" not in saved and "video_path" not in saved
    assert "video_path" not in saved_document(data, project["id"])


def test_project_search_matches_title_script_and_source_case_insensitively(studio):
    _, client, data = studio
    title_match = create(client, title="Alpha robotics", summary="A source update", source="Journal")
    script_match = create(client, title="A different story", summary="ALPHA chip details", source="Journal")
    source_match = create(client, title="Another story", summary="Source details", source="Alpha Magazine")
    create(client, title="Unrelated", summary="No matching words", source="Other")
    response = client.get("/api/projects", query_string={"search": "aLpHa"})
    assert response.status_code == 200
    assert {project["id"] for project in response.get_json()["items"]} == {
        title_match["id"], script_match["id"], source_match["id"],
    }


def test_project_status_filters_distinguish_ready_and_uploaded(studio):
    _, client, data = studio
    draft = create(client, title="Draft search")
    ready = ready_project(client, data)
    uploaded = ready_project(client, data, youtube_id="published-video")
    draft_result = client.get("/api/projects", query_string={"status": "draft"})
    assert {item["id"] for item in draft_result.get_json()["items"]} == {draft["id"]}
    ready_result = client.get("/api/projects", query_string={"status": "ready"})
    assert {item["id"] for item in ready_result.get_json()["items"]} == {ready["id"]}
    uploaded_result = client.get("/api/projects", query_string={"status": "uploaded"})
    assert {item["id"] for item in uploaded_result.get_json()["items"]} == {uploaded["id"]}
    assert client.get("/api/projects", query_string={"status": "not-a-status"}).status_code == 400
    combined = client.get("/api/projects", query_string={"status": "draft", "search": "Draft"})
    assert [item["id"] for item in combined.get_json()["items"]] == [draft["id"]]


@pytest.mark.parametrize("status", ["queued", "rendering", "uploading"])
def test_restart_does_not_leave_unfinished_jobs_running(studio, status):
    _, client, data = studio
    project = create(client)
    project.update(status=status, progress=40)
    save_document(data, project)
    restarted = server.create_app(data, testing=True).test_client()
    recovered = restarted.get(f"/api/projects/{project['id']}").get_json()
    assert recovered["status"] == "error"
    assert recovered["error"]


def test_duplicate_creates_fresh_draft_without_render_or_youtube_state(studio):
    _, client, data = studio
    original = ready_project(client, data, youtube_id="uploaded-id", youtube_url="https://youtube.com/watch?v=uploaded-id",
                             uploaded_at="2026-10-16T12:00:00+00:00", privacy="private", error="Old failure")
    response = client.post(f"/api/projects/{original['id']}/duplicate", json={})
    assert response.status_code == 201
    duplicate = response.get_json()
    assert duplicate["id"] != original["id"]
    assert duplicate["status"] == "draft"
    assert duplicate["progress"] == 0
    assert not duplicate.get("error")
    for field in ("script", "description", "tags", "source", "source_url", "generation_mode"):
        assert duplicate[field] == original[field]
    for field in ("video_path", "video_url", "subtitle_url", "duration", "youtube_id", "youtube_url", "uploaded_at", "privacy"):
        assert field not in duplicate
    assert saved_document(data, original["id"]) == original
    assert client.get(f"/api/projects/{original['id']}").get_json()["youtube_id"] == original["youtube_id"]
    assert client.post("/api/projects/missing/duplicate", json={}).status_code == 404


def test_export_is_downloadable_editorial_json_without_machine_paths_or_credentials(studio):
    _, client, data = studio
    project = ready_project(client, data, render_options={"style": "sunset", "speech": False},
                            access_token="never-export-this-token", provider_token="never-export-provider-token")
    response = client.get(f"/api/projects/{project['id']}/export")
    assert response.status_code == 200
    assert "attachment" in response.headers["Content-Disposition"]
    assert ".json" in response.headers["Content-Disposition"]
    assert response.mimetype == "application/json"
    exported = json.loads(response.data)
    assert exported["title"] == project["title"]
    assert exported["script"] == project["script"]
    assert exported["source_url"] == project["source_url"]
    text = response.get_data(as_text=True)
    assert str(data) not in text
    assert "never-export" not in text
    assert "video_path" not in exported
    assert client.get("/api/projects/missing/export").status_code == 404


def test_delete_removes_only_project_render_directory_and_document(studio):
    _, client, data = studio
    project = ready_project(client, data)
    outside = data / "personal-video.mp4"
    outside.write_bytes(b"personal")
    other_render = data / "renders" / "another-project"
    other_render.mkdir()
    (other_render / "reel.mp4").write_bytes(b"another")
    # Never trust a video_path from the database to decide what should be deleted.
    project["video_path"] = str(outside)
    save_document(data, project)
    response = client.delete(f"/api/projects/{project['id']}")
    assert response.status_code == 200
    assert response.get_json() == {"ok": True}
    assert client.get(f"/api/projects/{project['id']}").status_code == 404
    assert client.delete(f"/api/projects/{project['id']}").status_code == 404
    assert not (data / "renders" / project["id"]).exists()
    assert outside.read_bytes() == b"personal"
    assert (other_render / "reel.mp4").read_bytes() == b"another"


def test_delete_does_not_follow_project_render_directory_symlink(studio):
    _, client, data = studio
    project = create(client)
    outside = data / "outside-render-tree"
    outside.mkdir()
    (outside / "keep.mp4").write_bytes(b"keep")
    symlink = data / "renders" / project["id"]
    symlink.symlink_to(outside, target_is_directory=True)
    response = client.delete(f"/api/projects/{project['id']}")
    assert response.status_code == 200
    assert not symlink.exists() and not symlink.is_symlink()
    assert (outside / "keep.mp4").read_bytes() == b"keep"


def test_render_result_keeps_speech_provider_voice_and_subtitle_timing(studio, monkeypatch):
    _, client, _ = studio
    monkeypatch.setattr(server.media, "render", fake_render)
    project = create(client)
    response = client.post(f"/api/projects/{project['id']}/render", json={"speech": True, "style": "sunset", "speech_rate": 180})
    assert response.status_code == 202
    saved = await_status(client, project["id"], "ready")
    assert saved["speech"] is True
    assert saved["provider"] == "Test local voice"
    assert saved["voice"] == "tr"
    assert saved["subtitle_timing"] == "sentence_audio"
    assert saved["render_options"]["style"] == "sunset"
    assert saved["render_options"]["speech_rate"] == 180


def test_queued_project_waits_for_render_slot_and_cannot_be_deleted(studio, monkeypatch):
    _, client, _ = studio
    started, release = threading.Event(), threading.Event()
    rendered = []
    first, second = create(client, title="First project"), create(client, title="Second project")

    def controlled_render(project, *args):
        rendered.append(project["id"])
        if project["id"] == first["id"]:
            started.set()
            assert release.wait(timeout=5)
        return fake_render(project, *args)

    monkeypatch.setattr(server.media, "render", controlled_render)
    try:
        assert client.post(f"/api/projects/{first['id']}/render", json={"speech": False}).status_code == 202
        assert started.wait(timeout=2)
        assert client.post(f"/api/projects/{second['id']}/render", json={"speech": False}).status_code == 202
        assert client.get(f"/api/projects/{second['id']}").get_json()["status"] == "queued"
        assert rendered == [first["id"]]
        assert client.delete(f"/api/projects/{first['id']}").status_code == 409
        assert client.delete(f"/api/projects/{second['id']}").status_code == 409
    finally:
        release.set()
        await_status(client, first["id"], "ready")
        await_status(client, second["id"], "ready")
    assert rendered == [first["id"], second["id"]]


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


@pytest.mark.parametrize("options", [
    {"speech": "false"}, {"style": "unknown"}, {"tts_provider": "paid"},
    {"speech_rate": 99}, {"speech_rate": 241}, {"speech_rate": True}, {"speech_rate": "170"},
])
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


def connect_fake_youtube(data, monkeypatch):
    monkeypatch.setenv("YOUTUBE_CLIENT_ID", "test-client")
    monkeypatch.setenv("YOUTUBE_CLIENT_SECRET", "test-secret")
    path = data / "youtube-tokens.json"
    path.write_text('{"access_token":"test-token"}')
    return path


def test_ambiguous_upload_failure_requires_separate_retry_confirmation(studio, monkeypatch):
    _, client, data = studio
    connect_fake_youtube(data, monkeypatch)
    project = ready_project(client, data)
    calls = []

    def upload(*args):
        calls.append(1)
        if len(calls) == 1:
            raise requests.ConnectionError("private-credential-must-not-leak")
        return {"youtube_id": "uploaded-video", "youtube_url": "https://youtube.com/watch?v=uploaded-video",
                "privacy": "private"}

    monkeypatch.setattr(server.youtube, "upload", upload)
    endpoint = f"/api/projects/{project['id']}/upload"
    assert client.post(endpoint, json={"confirm": True}).status_code == 202
    failed = await_status(client, project["id"], "ready")
    assert failed["upload_uncertain"] is True
    assert "private-credential" not in failed["error"]
    assert failed["video_url"] == project["video_url"]
    retry = client.post(endpoint, json={"confirm": True})
    assert retry.status_code == 409
    assert retry.get_json()["requires_retry_confirmation"] is True
    assert calls == [1]
    assert client.post(endpoint, json={"confirm": True, "retry_confirmed": "true"}).status_code == 409
    assert client.post(endpoint, json={"confirm": True, "retry_confirmed": True}).status_code == 202
    uploaded = await_status(client, project["id"], "ready")
    assert uploaded["youtube_id"] == "uploaded-video"
    assert uploaded["upload_uncertain"] is False
    assert len(calls) == 2
    assert client.post(endpoint, json={"confirm": True}).status_code == 409


def test_youtube_disconnect_is_blocked_during_upload(studio, monkeypatch):
    _, client, data = studio
    tokens = connect_fake_youtube(data, monkeypatch)
    project = ready_project(client, data)
    started, release = threading.Event(), threading.Event()

    def upload(*args):
        started.set()
        assert release.wait(timeout=5)
        return {"youtube_id": "uploaded-video", "privacy": "private"}

    monkeypatch.setattr(server.youtube, "upload", upload)
    try:
        response = client.post(f"/api/projects/{project['id']}/upload", json={"confirm": True})
        assert response.status_code == 202
        assert started.wait(timeout=2)
        assert client.post("/api/youtube/disconnect", json={}).status_code == 409
        assert tokens.exists()
    finally:
        release.set()
        await_status(client, project["id"], "ready")
    assert client.post("/api/youtube/disconnect", json={}).status_code == 200
    assert not tokens.exists()


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


def news_document(ident, source, *, days_old=0, undated=False):
    timestamp = (datetime.now(timezone.utc) - timedelta(days=days_old)).isoformat()
    return {"id": ident, "title": f"{source} teknoloji haberi", "summary": "Kaynak özeti",
            "source": source, "url": f"https://example.org/{ident}", "score": 80,
            "category": "Teknoloji", "published": None if undated else timestamp, "fetched_at": timestamp}


def seed_news(data, *articles):
    with sqlite3.connect(data / "studio.sqlite3") as db:
        db.executemany("INSERT OR REPLACE INTO documents VALUES(?,?,?)",
                       [("news", article["id"], json.dumps(article)) for article in articles])


def test_partial_news_refresh_keeps_recent_failed_sources_and_expires_stale_rows(studio, monkeypatch):
    _, client, data = studio
    old_healthy = news_document("old-healthy", "Healthy")
    failed_recent = news_document("cached-unavailable", "Unavailable", days_old=1)
    failed_stale = news_document("stale-unavailable", "Unavailable", days_old=9)
    undated_stale = news_document("stale-undated", "Unavailable", days_old=9, undated=True)
    seed_news(data, old_healthy, failed_recent, failed_stale, undated_stale)
    new_healthy = news_document("new-healthy", "Healthy")
    health = [{"source": "Healthy", "status": "ok", "count": 1, "error": None},
              {"source": "Unavailable", "status": "error", "count": 0, "error": "Kaynağa erişilemedi."}]
    monkeypatch.setattr(server.news, "fetch_news_detailed", lambda: {
        "items": [new_healthy], "sources": health, "warning": "Unavailable kaynağına erişilemedi.",
    })
    refreshed = client.post("/api/news/refresh", json={})
    assert refreshed.status_code == 200
    result = refreshed.get_json()
    articles = {item["id"]: item for item in result["items"]}
    assert new_healthy["id"] in articles
    assert failed_recent["id"] in articles
    assert failed_stale["id"] not in articles and undated_stale["id"] not in articles
    assert result["sources"] == health
    assert result["last_refreshed"]
    listed = client.get("/api/news").get_json()
    assert {item["id"] for item in listed["items"]} == set(articles)
    assert listed["sources"] == health
    assert listed["last_refreshed"] == result["last_refreshed"]
    restarted = server.create_app(data, testing=True).test_client().get("/api/news").get_json()
    assert restarted["sources"] == health
    assert restarted["last_refreshed"] == result["last_refreshed"]


def test_total_news_refresh_failure_preserves_usable_cache_and_enforces_cooldown(studio, monkeypatch):
    _, client, data = studio
    cached = news_document("recent-cache", "Unavailable", days_old=2, undated=True)
    seed_news(data, cached)
    calls = []

    def unavailable():
        calls.append(1)
        return {"items": [], "sources": [{"source": "Unavailable", "status": "error", "count": 0, "error": "Unavailable"}],
                "warning": "Unavailable kaynağına erişilemedi."}

    monkeypatch.setattr(server.news, "fetch_news_detailed", unavailable)
    refreshed = client.post("/api/news/refresh", json={})
    assert refreshed.status_code == 200
    result = refreshed.get_json()
    assert [item["id"] for item in result["items"]] == [cached["id"]]
    assert result["cached"] is True
    assert result["sources"][0]["status"] == "error"
    assert result["warning"]
    assert client.post("/api/news/refresh", json={}).status_code == 429
    assert calls == [1]
