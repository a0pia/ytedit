"""Optional real-browser smoke for manual voice-file uploads, without paid APIs.

Creates a Turkish narration fixture with the installed local voice, then disables
all speech generation while the browser uploads, times and renders that file.
Run with Playwright/Chromium installed; HYPE_BROWSER_NO_SANDBOX=1 is supported.
"""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import sys
import tempfile
import threading
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from playwright.sync_api import expect, sync_playwright
import requests
from werkzeug.serving import make_server, WSGIRequestHandler

from app import media
from app.server import create_app


TITLE = "Kendi sesinle hareketli haberler"
SCRIPT = ("Yeni teknoloji sesimizi duyuruyor.\n"
          "Haberler şimdi hareketli sahnelerle anlatılıyor.\n"
          "Kendi kaydınla videonu oluştur.")


class QuietRequest(WSGIRequestHandler):
    def log(self, *_):
        pass


@contextmanager
def running(server):
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def set_saved_render_options(data, ident, options):
    """Simulate reopening persisted local/silent renders without another encode."""
    with sqlite3.connect(data / "studio.sqlite3") as database:
        value = database.execute("SELECT body FROM documents WHERE kind='project' AND id=?", (ident,)).fetchone()[0]
        document = json.loads(value)
        document["render_options"] = options
        database.execute("UPDATE documents SET body=? WHERE kind='project' AND id=?",
                         (json.dumps(document, ensure_ascii=False), ident))


def run():
    target = Path("artifacts")
    target.mkdir(exist_ok=True)
    engine = media._local_engine()
    assert engine["binary"], "A local Turkish voice is needed only to create the uploaded fixture."
    caps = media.capabilities()
    assert caps["ffmpeg"], caps.get("ffmpeg_error")
    # Missing local TTS must not prevent using an existing narration file.
    caps.update(tts=False, tts_error="Yerel ses kapalı; bu test yüklenen ses dosyasını kullanır.",
                voice="", provider="Kurulu değil")
    with tempfile.TemporaryDirectory(prefix="hype-audio-ui-") as temporary, patch.dict(os.environ, {
        "OPENAI_API_KEY": "", "ANTHROPIC_API_KEY": "", "ELEVENLABS_API_KEY": "",
        "ELEVENLABS_VOICE_ID": "", "YOUTUBE_CLIENT_ID": "", "YOUTUBE_CLIENT_SECRET": "",
    }):
        root = Path(temporary)
        fixture = root / "fixture"
        fixture.mkdir()
        narration = media._speak(SCRIPT, fixture, 0, engine, "local", 190)
        data = root / "data"
        application = create_app(data, testing=True)
        service = make_server("127.0.0.1", 0, application, threaded=True, request_handler=QuietRequest)
        with patch.object(media, "_speak", side_effect=AssertionError("Uploaded rendering must not synthesize speech")) as speak, \
             patch.object(media, "_local_engine", side_effect=AssertionError("Uploaded rendering must not require a local voice")) as local, \
             patch.object(media, "_elevenlabs", side_effect=AssertionError("No ElevenLabs API calls allowed")) as elevenlabs, \
             patch.object(media, "capabilities", return_value=caps), \
             patch.object(requests.sessions.Session, "request", side_effect=requests.ConnectionError("External HTTP disabled in this smoke")), \
             running(service), sync_playwright() as runtime:
            browser = runtime.chromium.launch(
                executable_path=os.getenv("CHROMIUM_PATH", "/usr/bin/chromium"), headless=True,
                args=["--no-sandbox"] if os.getenv("HYPE_BROWSER_NO_SANDBOX") == "1" else [])
            context = browser.new_context(viewport={"width": 1440, "height": 900},
                                          permissions=["clipboard-read", "clipboard-write"])
            page = context.new_page()
            errors = []
            console = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on("console", lambda message: console.append(message.type + ": " + message.text)
                    if message.type in {"warning", "error"} else None)
            base = f"http://127.0.0.1:{service.server_port}"
            page.goto(base, wait_until="networkidle")
            page.locator('[data-action="new-project"]').first.click()
            page.locator("#new-title").fill(TITLE)
            page.locator("#new-summary").fill("Bu haber kendi ses dosyanla animasyonlu videoya dönüşüyor.")
            page.locator("#new-mode").select_option("template")
            try:
                assert page.locator("#new-project-form").evaluate("form => form.checkValidity()"), "New-project form is invalid before submission"
                with page.expect_response(lambda response: response.url.endswith("/api/projects") and response.request.method == "POST") as created:
                    page.locator("#create-project").click()
            except Exception:
                page.screenshot(path=str(target / "uploaded-audio-create-failure.png"), full_page=True)
                details = page.evaluate("""() => ({
                    url: location.href,
                    dialogOpen: document.querySelector('#new-project-dialog').open,
                    activeElement: document.activeElement?.id,
                    submitDisabled: document.querySelector('#create-project').disabled,
                    fields: Array.from(document.querySelector('#new-project-form').elements).map(field => ({
                        id: field.id, value: field.value, valid: field.validity?.valid,
                        validationMessage: field.validationMessage
                    })),
                    notices: Array.from(document.querySelectorAll('#new-project-error, #system-message'))
                        .map(node => ({id: node.id, hidden: node.hidden, text: node.textContent}))
                })""")
                print("Creation failure diagnostics:", json.dumps({"ui": details, "page_errors": errors,
                      "console": console}, ensure_ascii=False), flush=True)
                raise
            assert created.value.status == 201
            project = created.value.json()
            endpoint = base + "/api/projects/" + project["id"]
            expect(page.locator("#edit-title")).to_have_value(TITLE)
            expect(page.locator("#tts-provider")).to_have_value("local")

            # Download first saves a dirty script and returns only that exact text.
            page.locator("#edit-script").fill(SCRIPT)
            with page.expect_download() as downloading:
                page.locator("#download-script").click()
            download = downloading.value
            assert Path(download.path()).read_text(encoding="utf-8") == SCRIPT
            assert page.request.get(endpoint).json()["script"] == SCRIPT
            expect(page.locator("#dirty-indicator")).to_have_text("Kaydedildi")
            page.locator("#copy-script").click()
            expect(page.locator("#toast")).to_have_text("Seslendirme metni kopyalandı.")
            assert page.evaluate("navigator.clipboard.readText()") == SCRIPT

            page.locator("#voice-workflow").evaluate("element => element.open = true")
            page.locator("#voice-file").set_input_files(narration)
            with page.expect_response(lambda response: response.url.endswith("/audio") and response.request.method == "POST") as uploading:
                page.locator("#upload-voice").click()
            assert uploading.value.status == 200, uploading.value.text()
            uploaded = uploading.value.json()
            metadata = uploaded["audio"]
            assert metadata["valid"] and metadata["timing_mode"] == "estimated"
            assert "audio_path" not in uploaded
            expect(page.locator("#tts-provider")).to_have_value("uploaded")
            expect(page.locator("#audio-info")).to_contain_text(narration.name)
            expect(page.locator("#audio-preview")).to_be_visible()
            page.wait_for_function("document.querySelector('#audio-preview').duration > 0")
            assert abs(page.locator("#audio-preview").evaluate("audio => audio.duration") - metadata["duration"]) < .05
            expect(page.locator("#render-project")).to_be_enabled()

            page.locator("#audio-timings").evaluate("element => element.open = true")
            captions = metadata["captions"]
            assert len(captions) >= 2
            expect(page.locator("#audio-timings-body tr")).to_have_count(len(captions))
            assert page.locator("#audio-timings-body input:not([type=number])").count() == 0
            assert page.locator("#audio-timings-body .audio-caption-listen").all_text_contents() == [caption["text"] for caption in captions]
            start = round(captions[0]["start"] + .02, 2)
            end = round(captions[0]["end"] - .02, 2)
            assert start < end
            page.locator('[data-timing-index="0"][data-timing-field="start"]').fill(f"{start:.2f}")
            page.locator('[data-timing-index="0"][data-timing-field="end"]').fill(f"{end:.2f}")
            expect(page.locator("#save-audio-timings")).to_be_enabled()
            expect(page.locator("#render-project")).to_be_disabled()
            with page.expect_response(lambda response: response.url.endswith("/audio/timings") and response.request.method == "PATCH") as timing:
                page.locator("#save-audio-timings").click()
            assert timing.value.status == 200, timing.value.text()
            timed = timing.value.json()
            assert timed["audio"]["timing_mode"] == "manual"
            assert timed["audio"]["captions"][0] == {"text": captions[0]["text"], "start": start, "end": end}
            expect(page.locator("#audio-timing-mode")).to_have_text("Elle düzenlenmiş zamanlama")
            page.locator("#edit-description").fill("Yalnızca açıklama güncellendi; yüklenen ses aynı kalır.")
            page.locator("#save-project").click()
            expect(page.locator("#dirty-indicator")).to_have_text("Kaydedildi")
            assert page.request.get(endpoint).json()["audio"]["valid"] is True

            page.locator("#video-design").select_option("kinetic")
            with page.expect_request(lambda request: request.url.endswith("/render") and request.method == "POST") as rendering:
                page.locator("#render-project").click()
            assert rendering.value.post_data_json["tts_provider"] == "uploaded"
            assert rendering.value.post_data_json["speech"] is True
            expect(page.locator("#preview-video")).to_have_attribute("src", re.compile(r"/media/.+\.mp4$"), timeout=90000)
            expect(page.locator("#preview-video")).to_have_js_property("videoWidth", 720, timeout=15000)
            expect(page.locator("#preview-video")).to_have_js_property("videoHeight", 1280)
            result = page.request.get(endpoint).json()
            assert result["status"] == "ready", result
            assert result["design"] == "kinetic" and result["scene_count"] >= 2
            assert result["speech"] and result["subtitle_timing"] == "manual"
            assert abs(result["duration"] - metadata["duration"]) < .05
            assert abs(page.locator("#preview-video").evaluate("video => video.duration") - metadata["duration"]) < .15
            subtitles = page.request.get(base + result["subtitle_url"]).text()
            assert "-->" in subtitles and "teknoloji" in subtitles and "Kendi" in subtitles
            assert not speak.called and not local.called and not elevenlabs.called
            source_video = data / "renders" / result["video_url"].removeprefix("/media/")
            shutil.copy2(source_video, target / "uploaded-audio-animated-fixture.mp4")
            page.locator("#audio-preview").scroll_into_view_if_needed()
            page.screenshot(path=str(target / "uploaded-audio-studio.png"), full_page=True)

            # Keeping an audio file must not override a previously saved voice choice.
            for options, provider in [
                ({"tts_provider": "local", "speech": True}, "local"),
                ({"tts_provider": "local", "speech": False}, "none"),
                (result["render_options"], "uploaded"),
            ]:
                set_saved_render_options(data, project["id"], options)
                page.reload(wait_until="networkidle")
                expect(page.locator("#tts-provider")).to_have_value(provider)
                expect(page.locator("#audio-preview")).to_be_visible()

            # A script edit blocks this recording immediately; saving persists that state.
            page.locator("#edit-script").fill(SCRIPT + " Yeni cümle eklendi.")
            expect(page.locator("#audio-warning")).to_have_text("Metin değişti. Aynı metinden üretilen sesi yeniden yükle.")
            expect(page.locator("#render-project")).to_be_disabled()
            page.locator("#save-project").click()
            expect(page.locator("#dirty-indicator")).to_have_text("Kaydedildi")
            assert page.request.get(endpoint).json()["audio"]["valid"] is False
            expect(page.locator("#render-project")).to_be_disabled()
            page.set_viewport_size({"width": 390, "height": 844})
            page.locator("#voice-workflow").scroll_into_view_if_needed()
            overflow = page.evaluate("({width:innerWidth,document:document.documentElement.scrollWidth,body:document.body.scrollWidth})")
            assert overflow["document"] == overflow["body"] == overflow["width"] == 390, overflow
            page.screenshot(path=str(target / "uploaded-audio-mobile.png"), full_page=True)
            page.locator("#remove-audio").click()
            expect(page.locator("#confirm-dialog")).to_be_visible()
            page.locator("#confirm-cancel").click()
            assert "audio" in page.request.get(endpoint).json()
            page.locator("#remove-audio").click()
            with page.expect_response(lambda response: response.url.endswith("/audio") and response.request.method == "DELETE") as removal:
                page.locator("#confirm-accept").click()
            assert removal.value.status == 200
            expect(page.locator("#audio-file-panel")).to_be_hidden()
            expect(page.locator("#tts-provider")).to_have_value("local")
            assert "audio" not in page.request.get(endpoint).json()
            assert not errors, errors
            browser.close()
    print("PASS: exact saved script download/copy, actual WAV upload and browser playback, manual caption timing, metadata edit preserves audio, uploaded-voice kinetic 720x1280 MP4/SRT with real audio duration, stale-script render lock, 390px layout, and confirmed audio removal. Local TTS and ElevenLabs were forbidden during upload/render.")


if __name__ == "__main__":
    run()
