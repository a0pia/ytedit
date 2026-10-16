"""Uploaded voice workflow, persistence and local-file boundaries; no live APIs."""
from copy import deepcopy
from datetime import datetime, timezone
from io import BytesIO
import json
import math
from pathlib import Path
import shutil
import sqlite3
import struct
import subprocess
import threading
import time
import unicodedata
import wave

import pytest
import requests

from app import server, writing


SCRIPT = "Merhaba dünya. Yeni haber burada."
CAPTIONS = [
    {"start": 0.0, "end": 0.4, "text": "Merhaba dünya."},
    {"start": 0.45, "end": 1.1, "text": "Yeni haber burada."},
]


def wav_bytes(seconds=1.2, rate=16000):
    """A small audible sine wave, encoded without audio packages or a network."""
    stream = BytesIO()
    with wave.open(stream, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(rate)
        frames = bytearray()
        for index in range(round(seconds * rate)):
            frames.extend(struct.pack("<h", round(4000 * math.sin(2 * math.pi * 440 * index / rate))))
        audio.writeframes(frames)
    return stream.getvalue()


@pytest.fixture
def studio(tmp_path, monkeypatch):
    for name in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "ELEVENLABS_API_KEY",
                 "ELEVENLABS_VOICE_ID", "YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET"):
        monkeypatch.delenv(name, raising=False)

    def no_network(*args, **kwargs):
        raise AssertionError("Audio workflow tests must not call an external API")

    monkeypatch.setattr(requests.sessions.Session, "request", no_network)
    application = server.create_app(tmp_path, testing=True)
    return application, application.test_client(), tmp_path


def create(client, script=SCRIPT):
    response = client.post("/api/projects", json={"title": "Seslendirme haberi", "summary": "Kaynak özeti"})
    assert response.status_code == 201, response.get_json()
    project = response.get_json()
    response = client.patch(f"/api/projects/{project['id']}", json={"script": script})
    assert response.status_code == 200, response.get_json()
    return response.get_json()


def saved(data, ident):
    with sqlite3.connect(data / "studio.sqlite3") as db:
        row = db.execute("SELECT body FROM documents WHERE kind='project' AND id=?", (ident,)).fetchone()
    return json.loads(row[0])


def save(data, project):
    with sqlite3.connect(data / "studio.sqlite3") as db:
        db.execute("INSERT OR REPLACE INTO documents VALUES(?,?,?)",
                   ("project", project["id"], json.dumps(project, ensure_ascii=False)))


def upload(client, ident, content=None, filename="narration.wav"):
    return client.post(f"/api/projects/{ident}/audio", data={
        "file": (BytesIO(wav_bytes() if content is None else content), filename),
    }, content_type="multipart/form-data")


def with_audio(client):
    project = create(client)
    response = upload(client, project["id"])
    assert response.status_code in {200, 201}, response.get_json()
    return response.get_json()


def seed_video(data, project, provider="uploaded"):
    document = saved(data, project["id"])
    target = data / "renders" / project["id"] / "first"
    target.mkdir(parents=True, exist_ok=True)
    video = target / "reel.mp4"
    video.write_bytes(b"existing-video")
    document.update(status="ready", progress=100, video_path=str(video), duration=1.2,
                    video_url=f"/media/{project['id']}/first/reel.mp4",
                    subtitle_url=f"/media/{project['id']}/first/captions.srt",
                    speech=True, render_options={"tts_provider": provider, "speech": True})
    save(data, document)
    return document


def wait_ready(client, ident):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        project = client.get(f"/api/projects/{ident}").get_json()
        if project["status"] == "ready":
            return project
        if project["status"] == "error":
            pytest.fail(f"Render failed: {project.get('error')}")
        time.sleep(0.01)
    pytest.fail(f"Render did not finish: {project}")


def test_script_download_is_the_current_script_as_utf8_without_added_title(studio):
    _, client, _ = studio
    project = create(client)
    endpoint = f"/api/projects/{project['id']}"
    changed = "Türkçe güncel metin.\nİkinci satır."
    assert client.patch(endpoint, json={"script": changed}).status_code == 200
    response = client.get(endpoint + "/script")
    assert response.status_code == 200
    assert response.mimetype == "text/plain"
    assert "charset=utf-8" in response.content_type.lower()
    assert "attachment" in response.headers["Content-Disposition"]
    assert response.data.decode("utf-8") == changed
    assert project["title"] not in response.data.decode("utf-8")
    assert client.get("/api/projects/missing/script").status_code == 404


def test_real_wav_upload_is_normalized_persisted_and_streamed_without_private_path(studio):
    _, client, data = studio
    project = create(client)
    response = upload(client, project["id"], filename="../../narration.wav")
    assert response.status_code in {200, 201}, response.get_json()
    uploaded = response.get_json()
    metadata = uploaded["audio"]
    assert metadata["filename"] == "narration.wav"
    assert metadata["duration"] == pytest.approx(1.2, abs=0.05)
    assert metadata["valid"] is True
    assert metadata["timing_mode"] == "estimated"
    assert metadata["url"] == f"/api/projects/{project['id']}/audio/file"
    assert len(metadata["script_hash"]) == 64
    stamp = datetime.fromisoformat(metadata["uploaded_at"])
    assert stamp.tzinfo is not None
    assert abs((datetime.now(timezone.utc) - stamp).total_seconds()) < 30
    assert " ".join(caption["text"] for caption in metadata["captions"]).split() == SCRIPT.split()
    assert all(0 <= caption["start"] < caption["end"] <= metadata["duration"]
               for caption in metadata["captions"])
    document = saved(data, project["id"])
    canonical = Path(document["audio_path"])
    relative = canonical.relative_to(data / "audio" / project["id"])
    assert len(relative.parts) == 2 and relative.name == "audio.wav"
    assert canonical.is_file()
    with wave.open(str(canonical), "rb") as normalized:
        assert normalized.getnchannels() == 1
        assert normalized.getframerate() == 24000
        assert normalized.getsampwidth() == 2
        assert normalized.getnframes() / normalized.getframerate() == pytest.approx(1.2, abs=0.05)
    assert "audio_path" not in uploaded
    assert str(data) not in response.get_data(as_text=True)
    for public in (client.get(f"/api/projects/{project['id']}").get_json(),
                   client.get("/api/projects").get_json()["items"][0]):
        assert "audio_path" not in public
        assert public["audio"] == metadata
    streamed = client.get(metadata["url"])
    assert streamed.status_code == 200
    assert "wav" in streamed.mimetype
    assert streamed.data == canonical.read_bytes()
    assert client.get(metadata["url"], headers={"Range": "bytes=0-15"}).status_code == 206
    restarted = server.create_app(data, testing=True).test_client()
    assert restarted.get(f"/api/projects/{project['id']}").get_json()["audio"] == metadata
    assert restarted.get(metadata["url"]).data == canonical.read_bytes()


@pytest.mark.parametrize("filename,content", [
    ("narration.wav", b"not audio"), ("narration.mp3", b"<html>not audio</html>"),
    ("narration.txt", wav_bytes()), ("narration.wav", b""),
], ids=["invalid-wav", "invalid-mp3", "unsupported-extension", "empty-file"])
def test_invalid_upload_preserves_document_and_has_no_audio_artifacts(studio, filename, content):
    _, client, data = studio
    project = create(client)
    before = saved(data, project["id"])
    response = upload(client, project["id"], content, filename)
    assert response.status_code == 400, response.get_json()
    assert saved(data, project["id"]) == before
    assert not list((data / "audio" / project["id"]).glob("**/audio.wav"))


@pytest.mark.parametrize("seconds", [0.2, 90.2])
def test_upload_validates_actual_duration(studio, seconds):
    _, client, data = studio
    project = create(client)
    before = saved(data, project["id"])
    response = upload(client, project["id"], wav_bytes(seconds))
    assert response.status_code == 400, response.get_json()
    assert saved(data, project["id"]) == before


def test_missing_field_oversized_upload_and_missing_projects_are_rejected(studio):
    _, client, data = studio
    project = create(client)
    before = saved(data, project["id"])
    endpoint = f"/api/projects/{project['id']}/audio"
    assert client.post(endpoint, data={}).status_code == 400
    assert client.post(endpoint, data={"audio": (BytesIO(wav_bytes()), "voice.wav")}).status_code == 400
    oversized = upload(client, project["id"], b"x" * (25 * 1024 * 1024 + 1))
    assert oversized.status_code in {400, 413}
    assert saved(data, project["id"]) == before
    assert upload(client, "missing").status_code == 404
    assert client.get(endpoint + "/file").status_code == 404
    assert client.get("/api/projects/missing/audio/file").status_code == 404


def test_mp3_upload_accepts_real_audio_instead_of_trusting_the_extension(studio, tmp_path):
    if not shutil.which("ffmpeg"):
        pytest.skip("MP3 fixture requires FFmpeg")
    _, client, _ = studio
    source, encoded = tmp_path / "source.wav", tmp_path / "voice.mp3"
    source.write_bytes(wav_bytes())
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(source), "-y", str(encoded)], check=True,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    project = create(client)
    response = upload(client, project["id"], encoded.read_bytes(), "voice.mp3")
    assert response.status_code in {200, 201}, response.get_json()
    assert response.get_json()["audio"]["filename"] == "voice.mp3"
    assert response.get_json()["audio"]["duration"] == pytest.approx(1.2, abs=0.1)


def test_replacement_is_transactional_and_uses_a_new_canonical_file(studio):
    _, client, data = studio
    project = with_audio(client)
    before = saved(data, project["id"])
    old_file = Path(before["audio_path"])
    original = old_file.read_bytes()
    failure = upload(client, project["id"], b"broken wav", "replacement.wav")
    assert failure.status_code == 400
    assert saved(data, project["id"]) == before
    assert old_file.read_bytes() == original
    assert client.get(project["audio"]["url"]).data == original
    replaced = upload(client, project["id"], wav_bytes(1.5, 24000), "replacement.wav")
    assert replaced.status_code in {200, 201}, replaced.get_json()
    after = saved(data, project["id"])
    assert after["audio"]["filename"] == "replacement.wav"
    assert after["audio"]["duration"] == pytest.approx(1.5, abs=0.05)
    assert Path(after["audio_path"]) != old_file
    assert not old_file.exists()
    assert Path(after["audio_path"]).is_file()


def test_caption_planning_failure_restores_the_exact_previous_audio_and_releases_the_job(studio, monkeypatch):
    _, client, data = studio
    project = with_audio(client)
    before = saved(data, project["id"])
    original = Path(before["audio_path"]).read_bytes()

    def fail(*args):
        raise server.audio.AudioError("Altyazı planı oluşturulamadı.")

    monkeypatch.setattr(server.audio, "plan_captions", fail)
    response = upload(client, project["id"], wav_bytes(1.4), "replacement.wav")
    assert response.status_code == 400
    assert saved(data, project["id"]) == before
    assert Path(before["audio_path"]).read_bytes() == original
    assert list((data / "audio" / project["id"]).glob("**/audio.wav")) == [Path(before["audio_path"])]
    assert client.patch(f"/api/projects/{project['id']}", json={"description": "Still editable"}).status_code == 200


def test_normalizing_upload_blocks_conflicts_and_preserves_previous_file_until_commit(studio, monkeypatch):
    application, client, data = studio
    project = with_audio(client)
    before = saved(data, project["id"])
    original = Path(before["audio_path"]).read_bytes()
    entered, release = threading.Event(), threading.Event()
    responses = []
    normalize = server.audio.normalize_audio

    def controlled(source, target):
        entered.set()
        assert release.wait(10), "Test did not release audio normalization"
        return normalize(source, target)

    monkeypatch.setattr(server.audio, "normalize_audio", controlled)
    endpoint = f"/api/projects/{project['id']}"

    def background_upload():
        with application.test_client() as background:
            responses.append(upload(background, project["id"], wav_bytes(1.4), "replacement.wav"))

    worker = threading.Thread(target=background_upload)
    worker.start()
    try:
        assert entered.wait(5)
        assert client.get(endpoint).get_json()["status"] == "processing_audio"
        assert client.get(project["audio"]["url"]).data == original
        assert upload(client, project["id"]).status_code == 409
        assert client.delete(endpoint + "/audio").status_code == 409
        assert client.patch(endpoint + "/audio/timings", json={"captions": CAPTIONS}).status_code == 409
        assert client.patch(endpoint, json={"script": "Racing edit"}).status_code == 409
        assert client.post(endpoint + "/render", json={"tts_provider": "uploaded", "speech": True}).status_code == 409
        assert client.post(endpoint + "/translate", json={}).status_code == 409
        assert client.delete(endpoint).status_code == 409
        assert Path(before["audio_path"]).read_bytes() == original
    finally:
        release.set()
        worker.join(timeout=10)
    assert not worker.is_alive()
    assert len(responses) == 1 and responses[0].status_code == 200
    assert responses[0].get_json()["audio"]["filename"] == "replacement.wav"
    assert not Path(before["audio_path"]).exists()


def test_manual_timings_preserve_audio_and_use_the_exact_script_words(studio):
    _, client, data = studio
    project = with_audio(client)
    before = saved(data, project["id"])
    response = client.patch(f"/api/projects/{project['id']}/audio/timings", json={"captions": CAPTIONS})
    assert response.status_code == 200, response.get_json()
    result = response.get_json()
    assert result["audio"]["timing_mode"] == "manual"
    assert result["audio"]["captions"] == CAPTIONS
    assert result["audio"]["valid"] is True
    after = saved(data, project["id"])
    assert after["audio_path"] == before["audio_path"]
    assert after["audio"]["script_hash"] == before["audio"]["script_hash"]
    assert client.get(result["audio"]["url"]).status_code == 200


@pytest.mark.parametrize("captions", [
    [], None, "captions", [{"start": 0, "end": 1, "text": "Only some words."}],
    [{"start": 0, "end": 1, "text": "Yeni haber burada. Merhaba dünya."}],
    [{"start": 0, "end": 1, "text": SCRIPT + " Fazladan."}],
    [{"start": -0.1, "end": 1, "text": SCRIPT}],
    [{"start": 0.8, "end": 0.2, "text": SCRIPT}],
    [{"start": 0, "end": 1.3, "text": SCRIPT}],
    [{"start": True, "end": 1, "text": SCRIPT}],
    [{"start": "0", "end": 1, "text": SCRIPT}],
    [{"start": 0, "end": float("nan"), "text": SCRIPT}],
    [{"start": 0, "end": float("inf"), "text": SCRIPT}],
    [{"start": 0, "end": 0.6, "text": "Merhaba dünya."},
     {"start": 0.5, "end": 1.1, "text": "Yeni haber burada."}],
])
def test_invalid_manual_timings_leave_database_and_file_unchanged(studio, captions):
    _, client, data = studio
    project = with_audio(client)
    before = saved(data, project["id"])
    original = Path(before["audio_path"]).read_bytes()
    response = client.patch(f"/api/projects/{project['id']}/audio/timings", json={"captions": captions})
    assert response.status_code == 400, response.get_json()
    assert saved(data, project["id"]) == before
    assert Path(before["audio_path"]).read_bytes() == original


def test_manual_timings_are_bounded_by_the_file_duration_not_mutable_metadata(studio):
    _, client, data = studio
    project = with_audio(client)
    before = saved(data, project["id"])
    before["audio"]["duration"] = 80.0
    save(data, before)
    response = client.patch(f"/api/projects/{project['id']}/audio/timings", json={
        "captions": [{"start": 0, "end": 2.0, "text": SCRIPT}],
    })
    assert response.status_code == 400, response.get_json()
    assert saved(data, project["id"]) == before


@pytest.mark.parametrize("operation", ["replace", "delete", "timings"])
@pytest.mark.parametrize("provider", ["uploaded", "local"])
def test_audio_mutations_invalidate_the_renders_that_depend_on_them(studio, operation, provider):
    _, client, data = studio
    project = with_audio(client)
    before = seed_video(data, project, provider)
    endpoint = f"/api/projects/{project['id']}/audio"
    if operation == "replace":
        response = upload(client, project["id"], wav_bytes(1.4), "replacement.wav")
    elif operation == "delete":
        response = client.delete(endpoint)
    else:
        response = client.patch(endpoint + "/timings", json={"captions": CAPTIONS})
    assert response.status_code in {200, 201}, response.get_json()
    after = saved(data, project["id"])
    if provider == "uploaded" or operation == "replace":
        assert after["status"] == "draft"
        for field in ("video_path", "video_url", "subtitle_url", "duration", "render_options"):
            assert field not in after
    else:
        assert after["status"] == "ready"
        for field in ("video_path", "video_url", "subtitle_url", "duration", "render_options"):
            assert after[field] == before[field]
    if operation == "delete":
        assert "audio" not in response.get_json()
        assert "audio" not in after and "audio_path" not in after
        assert not Path(before["audio_path"]).exists()
        assert client.get(endpoint + "/file").status_code == 404


@pytest.mark.parametrize("status", ["queued", "rendering", "uploading", "translating", "processing_audio"])
def test_busy_projects_reject_audio_upload_delete_and_timing_edits(studio, status):
    _, client, data = studio
    project = with_audio(client)
    before = saved(data, project["id"])
    before["status"] = status
    save(data, before)
    endpoint = f"/api/projects/{project['id']}/audio"
    assert upload(client, project["id"]).status_code == 409
    assert client.delete(endpoint).status_code == 409
    assert client.patch(endpoint + "/timings", json={"captions": CAPTIONS}).status_code == 409
    assert saved(data, project["id"]) == before
    assert Path(before["audio_path"]).is_file()


def test_script_change_marks_audio_stale_but_keeps_it_playable_and_blocks_render(studio, monkeypatch):
    _, client, data = studio
    monkeypatch.setattr(server.media, "render", lambda *args: pytest.fail("Stale voice reached renderer"))
    project = with_audio(client)
    endpoint = f"/api/projects/{project['id']}"
    original = Path(saved(data, project["id"])["audio_path"]).read_bytes()
    changed = client.patch(endpoint, json={"script": "Tamamen değişmiş seslendirme."})
    assert changed.status_code == 200
    assert changed.get_json()["audio"]["valid"] is False
    assert client.get(project["audio"]["url"]).data == original
    rejected = client.post(endpoint + "/render", json={"tts_provider": "uploaded", "speech": True})
    assert rejected.status_code == 400
    assert rejected.get_json()["error"]
    assert client.get(endpoint).get_json()["status"] == "draft"


def test_title_and_description_edits_and_normalized_script_keep_audio_valid(studio):
    _, client, data = studio
    project = with_audio(client)
    endpoint = f"/api/projects/{project['id']}"
    digest = project["audio"]["script_hash"]
    changed = client.patch(endpoint, json={"title": "Yeni başlık", "description": "Yeni açıklama"})
    assert changed.status_code == 200
    assert changed.get_json()["audio"]["valid"] is True
    equivalent = unicodedata.normalize("NFD", SCRIPT).replace(" ", "  \n")
    normalized = client.patch(endpoint, json={"script": equivalent})
    assert normalized.status_code == 200
    assert normalized.get_json()["audio"]["valid"] is True
    assert saved(data, project["id"])["audio"]["script_hash"] == digest


def test_translation_marks_original_audio_stale(studio, monkeypatch):
    _, client, _ = studio
    project = with_audio(client)
    monkeypatch.setattr(writing, "request_json", lambda *args: {
        "title": "Türkçe yeni başlık", "script": "Çeviriden gelen yeni seslendirme.",
        "description": "Kaynak açıklaması", "tags": ["Haber"],
    })
    endpoint = f"/api/projects/{project['id']}"
    translated = client.post(endpoint + "/translate", json={})
    assert translated.status_code == 200, translated.get_json()
    assert translated.get_json()["audio"]["valid"] is False
    assert client.get(project["audio"]["url"]).status_code == 200
    assert client.post(endpoint + "/render", json={"tts_provider": "uploaded", "speech": True}).status_code == 400


def test_uploaded_render_requires_audio_and_valid_persisted_captions(studio, monkeypatch):
    _, client, data = studio
    monkeypatch.setattr(server.media, "render", lambda *args: pytest.fail("Invalid uploaded voice reached renderer"))
    project = create(client)
    endpoint = f"/api/projects/{project['id']}"
    options = {"tts_provider": "uploaded", "speech": True, "uploaded_audio_path": "/tmp/forged.wav"}
    assert client.post(endpoint + "/render", json=options).status_code == 400
    assert upload(client, project["id"]).status_code in {200, 201}
    document = saved(data, project["id"])
    document["audio"]["captions"] = [{"start": 0, "end": 1, "text": "Forged transcript"}]
    save(data, document)
    assert client.post(endpoint + "/render", json=options).status_code == 400
    assert client.get(endpoint).get_json()["status"] == "draft"


def test_missing_canonical_file_is_not_playable_or_renderable(studio, monkeypatch):
    _, client, data = studio
    project = with_audio(client)
    Path(saved(data, project["id"])["audio_path"]).unlink()
    monkeypatch.setattr(server.media, "render", lambda *args: pytest.fail("Missing audio reached renderer"))
    assert client.get(f"/api/projects/{project['id']}").get_json()["audio"]["valid"] is False
    assert client.get(project["audio"]["url"]).status_code == 404
    assert client.post(f"/api/projects/{project['id']}/render",
                       json={"tts_provider": "uploaded", "speech": True}).status_code == 400


@pytest.mark.parametrize("manual", [False, True])
def test_uploaded_render_uses_only_the_private_canonical_audio_and_timings(studio, monkeypatch, manual):
    _, client, data = studio
    project = with_audio(client)
    endpoint = f"/api/projects/{project['id']}"
    if manual:
        response = client.patch(endpoint + "/audio/timings", json={"captions": CAPTIONS})
        assert response.status_code == 200, response.get_json()
        project = response.get_json()
    else:
        equivalent = unicodedata.normalize("NFD", SCRIPT).replace(" ", "  \n")
        response = client.patch(endpoint, json={"script": equivalent})
        assert response.status_code == 200
        assert response.get_json()["audio"]["valid"] is True
    canonical = saved(data, project["id"])["audio_path"]
    calls = []

    def render(project, target, opts, progress):
        calls.append((deepcopy(project), deepcopy(opts)))
        target.mkdir(parents=True)
        video, subtitles = target / "reel.mp4", target / "captions.srt"
        video.write_bytes(b"test-uploaded-voice-video")
        subtitles.write_text("", encoding="utf-8")
        return {"video_path": str(video), "subtitle_path": str(subtitles), "duration": 1.2,
                "provider": "Uploaded audio", "speech": True,
                "subtitle_timing": "manual" if manual else "estimated"}

    monkeypatch.setattr(server.media, "render", render)
    response = client.post(endpoint + "/render", json={
        "tts_provider": "uploaded", "speech": True, "audio_path": "/tmp/forged.wav",
        "uploaded_audio_path": "/tmp/forged.wav", "audio_captions": [{"text": "forged"}],
        "audio_timing_mode": "forged",
    })
    assert response.status_code == 202, response.get_json()
    ready = wait_ready(client, project["id"])
    assert len(calls) == 1
    private, options = calls[0]
    assert private["audio_path"] == canonical
    assert private["audio_captions"] == project["audio"]["captions"]
    assert private["audio_timing_mode"] == ("manual" if manual else "estimated")
    assert options["tts_provider"] == "uploaded" and options["speech"] is True
    assert all("forged" not in str(value) for value in options.values())
    assert "audio_path" not in ready
    assert "audio_captions" not in ready and "audio_timing_mode" not in ready
    assert client.get(ready["video_url"]).data == b"test-uploaded-voice-video"


def test_forged_audio_path_cannot_be_streamed_or_rendered(studio, monkeypatch):
    _, client, data = studio
    project = with_audio(client)
    outside = data / "personal.wav"
    outside.write_bytes(wav_bytes())
    document = saved(data, project["id"])
    document["audio_path"] = str(outside)
    save(data, document)
    monkeypatch.setattr(server.media, "render", lambda *args: pytest.fail("Forged path reached renderer"))
    assert client.get(project["audio"]["url"]).status_code == 404
    assert client.post(f"/api/projects/{project['id']}/render",
                       json={"tts_provider": "uploaded", "speech": True}).status_code == 400
    assert outside.is_file()


def test_canonical_audio_symlink_cannot_expose_an_external_file(studio, monkeypatch):
    _, client, data = studio
    project = with_audio(client)
    canonical = Path(saved(data, project["id"])["audio_path"])
    outside = data / "personal.wav"
    outside.write_bytes(wav_bytes())
    canonical.unlink()
    canonical.symlink_to(outside)
    monkeypatch.setattr(server.media, "render", lambda *args: pytest.fail("Symlink audio reached renderer"))
    assert client.get(project["audio"]["url"]).status_code == 404
    assert client.post(f"/api/projects/{project['id']}/render",
                       json={"tts_provider": "uploaded", "speech": True}).status_code == 400
    assert client.delete(f"/api/projects/{project['id']}/audio").status_code == 200
    assert outside.is_file()


def test_duplicate_and_export_omit_audio_association_paths_tokens_and_blobs(studio):
    _, client, data = studio
    project = with_audio(client)
    document = saved(data, project["id"])
    document.update(access_token="never-export-token", audio_blob="never-export-audio" * 1000)
    save(data, document)
    endpoint = f"/api/projects/{project['id']}"
    duplicated = client.post(endpoint + "/duplicate", json={})
    assert duplicated.status_code == 201
    duplicate = duplicated.get_json()
    assert duplicate["script"] == project["script"]
    assert "audio" not in duplicate and "audio_path" not in saved(data, duplicate["id"])
    assert client.get(f"/api/projects/{duplicate['id']}/audio/file").status_code == 404
    exported = client.get(endpoint + "/export")
    assert exported.status_code == 200
    assert json.loads(exported.data)["script"] == project["script"]
    text = exported.get_data(as_text=True)
    assert str(data) not in text
    assert "audio_path" not in text and "never-export" not in text
    assert len(exported.data) < 10000
    assert Path(document["audio_path"]).is_file()


@pytest.mark.parametrize("operation", ["delete_audio", "delete_project", "replace_audio"])
def test_audio_cleanup_ignores_a_malicious_stored_path(studio, operation):
    _, client, data = studio
    project = with_audio(client)
    other = with_audio(client)
    outside = data / "personal.wav"
    outside.write_bytes(b"personal audio must survive")
    document = saved(data, project["id"])
    original_directory = data / "audio" / project["id"]
    document["audio_path"] = str(outside)
    save(data, document)
    endpoint = f"/api/projects/{project['id']}"
    if operation == "delete_audio":
        response = client.delete(endpoint + "/audio")
    elif operation == "delete_project":
        response = client.delete(endpoint)
    else:
        response = upload(client, project["id"], filename="replacement.wav")
    assert response.status_code in {200, 201}, response.get_json()
    assert outside.read_bytes() == b"personal audio must survive"
    assert client.get(other["audio"]["url"]).status_code == 200
    if operation == "delete_project":
        assert not original_directory.exists()
        assert client.get(endpoint).status_code == 404


@pytest.mark.parametrize("operation", ["delete_audio", "delete_project"])
def test_audio_cleanup_does_not_follow_a_project_directory_symlink(studio, operation):
    _, client, data = studio
    project = create(client)
    outside = data / "outside-audio-tree"
    outside.mkdir()
    keep = outside / "audio.wav"
    keep.write_bytes(b"keep this audio")
    (data / "audio").mkdir(exist_ok=True)
    link = data / "audio" / project["id"]
    link.symlink_to(outside, target_is_directory=True)
    document = saved(data, project["id"])
    document.update(audio_path=str(keep), audio={"filename": "voice.wav", "duration": 1.2,
                    "script_hash": "legacy", "captions": CAPTIONS, "timing_mode": "manual"})
    save(data, document)
    endpoint = f"/api/projects/{project['id']}"
    response = client.delete(endpoint + ("/audio" if operation == "delete_audio" else ""))
    assert response.status_code == 200, response.get_json()
    assert keep.read_bytes() == b"keep this audio"
    assert not link.exists() and not link.is_symlink()
