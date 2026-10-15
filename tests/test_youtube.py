"""YouTube OAuth and resumable-upload protocol with fake HTTP responses only."""
from datetime import datetime
import json
import time

import pytest
import requests

from app import youtube


@pytest.fixture(autouse=True)
def isolated_credentials(monkeypatch):
    monkeypatch.setenv("YOUTUBE_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("YOUTUBE_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("YOUTUBE_REDIRECT_URI", "http://127.0.0.1:8787/oauth/youtube/callback")

    def no_network(*args, **kwargs):
        raise AssertionError("Protocol tests must not contact Google")

    monkeypatch.setattr(requests.sessions.Session, "request", no_network)


def response(body=None, *, status=200, headers=None):
    result = requests.Response()
    result.status_code = status
    result.url = "https://www.googleapis.com/test"
    result._content = json.dumps(body if body is not None else {}).encode()
    result.headers.update(headers or {})
    return result


def token_file(tmp_path, **changes):
    path = tmp_path / "youtube-tokens.json"
    youtube.save_tokens(path, {"access_token": "test-access-token", "refresh_token": "test-refresh-token",
                               "expires_in": 3600, **changes})
    return path


def test_exchange_sends_oauth_code_and_saves_private_tokens(tmp_path, monkeypatch):
    calls = []

    def post(url, **kwargs):
        calls.append((url, kwargs))
        return response({"access_token": "new-access", "refresh_token": "new-refresh", "expires_in": 3600})

    monkeypatch.setattr(youtube.requests, "post", post)
    path = tmp_path / "youtube-tokens.json"
    started = time.time()
    youtube.exchange("single-use-code", path)
    assert calls[0][0] == "https://oauth2.googleapis.com/token"
    assert calls[0][1]["data"] == {
        "code": "single-use-code", "client_id": "test-client-id", "client_secret": "test-client-secret",
        "redirect_uri": "http://127.0.0.1:8787/oauth/youtube/callback", "grant_type": "authorization_code",
    }
    tokens = json.loads(path.read_text())
    assert tokens["access_token"] == "new-access"
    assert tokens["refresh_token"] == "new-refresh"
    assert started + 3540 <= tokens["expires_at"] <= time.time() + 3540
    assert path.stat().st_mode & 0o777 == 0o600
    assert not path.with_suffix(".tmp").exists()


def test_exchange_rejects_missing_access_token_without_saving(tmp_path, monkeypatch):
    monkeypatch.setattr(youtube.requests, "post", lambda *args, **kwargs: response({"refresh_token": "refresh"}))
    path = tmp_path / "youtube-tokens.json"
    with pytest.raises(ValueError, match="belirteci"):
        youtube.exchange("code", path)
    assert not path.exists()


def test_current_access_token_does_not_call_google(tmp_path):
    path = token_file(tmp_path)
    assert youtube.access_token(path) == "test-access-token"


@pytest.mark.parametrize("new_refresh", [None, "rotated-refresh"])
def test_refresh_preserves_or_rotates_refresh_token_and_restores_private_permissions(tmp_path, monkeypatch, new_refresh):
    path = token_file(tmp_path, expires_in=-10)
    path.chmod(0o644)
    calls = []
    returned = {"access_token": "refreshed-access", "expires_in": 1800}
    if new_refresh:
        returned["refresh_token"] = new_refresh

    def post(url, **kwargs):
        calls.append((url, kwargs))
        return response(returned)

    monkeypatch.setattr(youtube.requests, "post", post)
    assert youtube.access_token(path) == "refreshed-access"
    assert calls[0][0] == "https://oauth2.googleapis.com/token"
    assert calls[0][1]["data"] == {
        "client_id": "test-client-id", "client_secret": "test-client-secret",
        "refresh_token": "test-refresh-token", "grant_type": "refresh_token",
    }
    saved = json.loads(path.read_text())
    assert saved["refresh_token"] == (new_refresh or "test-refresh-token")
    assert saved["expires_at"] > time.time()
    assert path.stat().st_mode & 0o777 == 0o600


def test_missing_or_unrefreshable_tokens_fail_without_network(tmp_path):
    with pytest.raises(ValueError, match="bağlayın"):
        youtube.access_token(tmp_path / "missing.json")
    path = token_file(tmp_path, expires_in=-1, refresh_token=None)
    with pytest.raises(ValueError, match="süresi dolmuş"):
        youtube.access_token(path)


@pytest.mark.parametrize("operation", ["exchange", "refresh"])
def test_token_http_errors_propagate_and_preserve_existing_tokens(tmp_path, monkeypatch, operation):
    path = token_file(tmp_path, expires_in=-10)
    original = path.read_bytes()
    monkeypatch.setattr(youtube.requests, "post", lambda *args, **kwargs: response(status=401))
    with pytest.raises(requests.HTTPError):
        if operation == "exchange":
            youtube.exchange("invalid-code", path)
        else:
            youtube.access_token(path)
    assert path.read_bytes() == original


class UploadSession:
    def __init__(self, *, location="https://www.googleapis.com/upload/youtube/v3/videos?upload_id=test", start_status=200, upload_status=200, video_id="video123"):
        self.location = location
        self.start_status = start_status
        self.upload_status = upload_status
        self.video_id = video_id
        self.posts = []
        self.puts = []
        self.stream = None
        self.transferred = None
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True

    def post(self, url, **kwargs):
        self.posts.append((url, kwargs))
        return response(status=self.start_status, headers={"Location": self.location})

    def put(self, url, **kwargs):
        self.puts.append((url, kwargs))
        self.stream = kwargs["data"]
        assert hasattr(self.stream, "read"), "Upload must stream the file rather than read it all into RAM"
        assert not self.stream.closed
        self.transferred = self.stream.read()
        return response({"id": self.video_id} if self.video_id else {}, status=self.upload_status)


def upload_inputs(tmp_path, monkeypatch, session):
    monkeypatch.setattr(youtube.requests, "Session", lambda: session)
    video = tmp_path / "reel.mp4"
    video.write_bytes(b"fake-mp4-video-content")
    project = {"title": "Türkçe başlık " * 12, "description": "Açıklama " * 650,
               "tags": [f"etiket-{index}" for index in range(15)]}
    return project, video, token_file(tmp_path)


def test_resumable_upload_streams_file_with_private_default_and_returns_video_id(tmp_path, monkeypatch):
    session = UploadSession()
    project, video, tokens = upload_inputs(tmp_path, monkeypatch, session)
    result = youtube.upload(project, video, tokens)
    url, request = session.posts[0]
    assert url == "https://www.googleapis.com/upload/youtube/v3/videos"
    assert request["params"] == {"uploadType": "resumable", "part": "snippet,status"}
    assert request["headers"]["Authorization"] == "Bearer test-access-token"
    assert request["headers"]["X-Upload-Content-Length"] == str(video.stat().st_size)
    assert request["headers"]["X-Upload-Content-Type"] == "video/mp4"
    assert request["json"]["snippet"] == {
        "title": project["title"][:100], "description": project["description"][:5000],
        "tags": project["tags"][:12], "categoryId": "28",
    }
    assert request["json"]["status"] == {"privacyStatus": "private", "selfDeclaredMadeForKids": False}
    assert session.puts[0][0] == session.location
    assert session.puts[0][1]["headers"]["Authorization"] == "Bearer test-access-token"
    assert session.puts[0][1]["headers"]["Content-Length"] == str(video.stat().st_size)
    assert session.transferred == video.read_bytes()
    assert session.stream.closed and session.closed
    assert result["youtube_id"] == "video123"
    assert result["youtube_url"] == "https://www.youtube.com/watch?v=video123"
    assert result["privacy"] == "private"
    assert datetime.fromisoformat(result["uploaded_at"]).tzinfo is not None


@pytest.mark.parametrize("privacy", ["public", "unlisted"])
def test_resumable_upload_uses_explicit_privacy(tmp_path, monkeypatch, privacy):
    session = UploadSession()
    args = upload_inputs(tmp_path, monkeypatch, session)
    result = youtube.upload(*args, privacy=privacy)
    assert session.posts[0][1]["json"]["status"]["privacyStatus"] == privacy
    assert result["privacy"] == privacy


@pytest.mark.parametrize("location", [
    "https://attacker.invalid/upload", "http://www.googleapis.com/upload",
    "https://www.googleapis.com.attacker.invalid/upload", "https://www.googleapis.com@attacker.invalid/upload",
    "//www.googleapis.com/upload", "",
])
def test_untrusted_upload_location_is_rejected_before_transmitting_file_or_token(tmp_path, monkeypatch, location):
    session = UploadSession(location=location)
    args = upload_inputs(tmp_path, monkeypatch, session)
    with pytest.raises(ValueError, match="güvenli"):
        youtube.upload(*args)
    assert session.posts[0][0] == "https://www.googleapis.com/upload/youtube/v3/videos"
    assert session.puts == []
    assert session.transferred is None
    assert session.closed


@pytest.mark.parametrize("stage", ["initiate", "transfer"])
def test_upload_http_errors_propagate_without_returning_success(tmp_path, monkeypatch, stage):
    session = UploadSession(start_status=403 if stage == "initiate" else 200,
                            upload_status=503 if stage == "transfer" else 200)
    args = upload_inputs(tmp_path, monkeypatch, session)
    with pytest.raises(requests.HTTPError):
        youtube.upload(*args)
    if stage == "initiate":
        assert session.puts == []
    else:
        assert session.stream.closed
    assert session.closed


def test_success_response_without_video_id_is_not_reported_as_uploaded(tmp_path, monkeypatch):
    session = UploadSession(video_id=None)
    args = upload_inputs(tmp_path, monkeypatch, session)
    with pytest.raises(ValueError, match="kimliği"):
        youtube.upload(*args)


def test_invalid_privacy_is_rejected_before_network_or_token_access(tmp_path):
    with pytest.raises(ValueError, match="gizlilik"):
        youtube.upload({}, tmp_path / "missing.mp4", tmp_path / "missing-token.json", privacy="invalid")
