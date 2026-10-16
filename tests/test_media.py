"""Exercise actual FFmpeg outputs without calling a hosted voice API."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from app.media import (MediaError, _ass_escape, _ffmpeg_probe, _fit_display, _glyph_width,
                       _kinetic_events, _kinetic_plan, _local_engine, _sentences,
                       _source_phrase, _subtitle_chunks, _title_layout, capabilities, render)


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg is required")
class RenderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name)

    def probe(self, path):
        result = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
                                capture_output=True, check=True, timeout=15)
        return json.loads(result.stdout)

    def test_real_silent_video_has_vertical_video_audio_and_turkish_subtitles(self):
        progress = []
        with patch("urllib.request.urlopen", side_effect=AssertionError("Free rendering must be offline")):
            result = render({"title": "Yapay zekâ gündemi", "script": "Teknolojide yeni bir gün!"},
                            self.output, {"speech": False}, progress.append)
        media = self.probe(result["video_path"])
        video = next(stream for stream in media["streams"] if stream["codec_type"] == "video")
        self.assertEqual((video["width"], video["height"]), (720, 1280))
        self.assertEqual(video["codec_name"], "h264")
        self.assertTrue(any(stream["codec_type"] == "audio" for stream in media["streams"]))
        self.assertGreater(float(media["format"]["duration"]), 1.9)
        self.assertIn("Teknolojide yeni bir gün!", " ".join(Path(result["subtitle_path"]).read_text().split()))
        self.assertEqual(result["subtitle_timing"], "estimated")
        self.assertEqual(result["design"], "kinetic")
        self.assertGreaterEqual(result["scene_count"], 2)
        self.assertEqual(progress[-1], 100)
        self.assertEqual(progress, sorted(progress))
        self.assertTrue(any(65 < value < 98 for value in progress))
        self.assertEqual({path.name for path in self.output.iterdir()},
                         {"reel.mp4", "captions.srt", "captions.ass", "narration.wav"})

    def test_real_local_turkish_narration(self):
        if not capabilities()["tts"]:
            self.skipTest("No local Turkish voice installed")
        with patch("urllib.request.urlopen", side_effect=AssertionError("Local voice must not call an API")):
            result = render({"title": "Türkiye teknoloji", "script": "Türkçe yapay zekâ haberleri."},
                            self.output, {"speech": True})
        self.assertTrue(result["speech"])
        self.assertEqual(result["subtitle_timing"], "sentence_audio")
        self.assertGreater(result["duration"], 1)
        self.assertTrue(Path(result["video_path"]).is_file())
        # Audibly nonempty PCM, rather than merely an empty AAC stream.
        import wave
        with wave.open(str(self.output / "narration.wav"), "rb") as wav:
            self.assertEqual(wav.getframerate(), 24000)
            self.assertTrue(any(wav.readframes(wav.getnframes())))

    def test_missing_api_credentials_fail_without_network(self):
        with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "", "ELEVENLABS_VOICE_ID": ""}), \
                patch("urllib.request.urlopen", side_effect=AssertionError("Missing credentials must not call API")):
            with self.assertRaisesRegex(MediaError, "ELEVENLABS_API_KEY"):
                render({"script": "Merhaba dünya."}, self.output, {"tts_provider": "elevenlabs"})

    def test_script_limit_and_explicit_speech_option(self):
        with self.assertRaisesRegex(MediaError, "1200"):
            render({"script": "x" * 1201}, self.output)
        with self.assertRaisesRegex(MediaError, "true veya false"):
            render({"script": "Merhaba."}, self.output, {"speech": "false"})

    def test_long_silent_video_rejected_before_encoding(self):
        with self.assertRaisesRegex(MediaError, "90 saniye"):
            render({"script": "a " * 300}, self.output, {"speech": False})
        self.assertFalse((self.output / "reel.mp4").exists())

    def test_missing_subtitle_support_fails_before_voice_generation(self):
        state = {"ready": False, "error": "libass destekli FFmpeg kurun.", "features": {"subtitles": False}}
        with patch("app.media._ffmpeg_state", return_value=state), patch("app.media._speak") as speak:
            with self.assertRaisesRegex(MediaError, "libass"):
                render({"script": "Teknoloji."}, self.output)
        speak.assert_not_called()
        self.assertEqual(list(self.output.iterdir()), [])

    def test_failed_encoding_removes_partial_media_and_keeps_user_files(self):
        sentinel = self.output / "user-notes.txt"
        sentinel.write_text("Preserve this file.")

        def fail_encoding(_command, folder, *_args):
            (folder / "reel.mp4").write_bytes(b"incomplete")
            raise MediaError("Kodlama başarısız.")

        with patch("app.media._encode", side_effect=fail_encoding):
            with self.assertRaisesRegex(MediaError, "Kodlama başarısız"):
                render({"script": "Merhaba dünya."}, self.output, {"speech": False})
        self.assertEqual(list(self.output.iterdir()), [sentinel])
        self.assertEqual(sentinel.read_text(), "Preserve this file.")

    def test_existing_video_is_never_overwritten(self):
        original = self.output / "reel.mp4"
        original.write_bytes(b"existing video")
        with self.assertRaisesRegex(MediaError, "daha önce"):
            render({"script": "Merhaba dünya."}, self.output, {"speech": False})
        self.assertEqual(original.read_bytes(), b"existing video")

    def test_invalid_configured_voice_is_reported_before_render(self):
        if not capabilities()["tts"]:
            self.skipTest("No local voice installed")
        with patch.dict(os.environ, {"LOCAL_TTS_VOICE": "this-voice-does-not-exist"}):
            self.assertFalse(capabilities()["tts"])
            with self.assertRaisesRegex(MediaError, "LOCAL_TTS_VOICE"):
                render({"script": "Türkçe konuşuyoruz."}, self.output)
        self.assertEqual(list(self.output.iterdir()), [])

    def test_classic_design_remains_an_explicit_real_export_option(self):
        result = render({"title": "Klasik tasarım", "script": "Merhaba teknoloji."}, self.output,
                        {"speech": False, "video_design": "classic"})
        self.assertEqual(result["design"], "classic")
        self.assertEqual(result["scene_count"], 1)
        self.assertNotIn("/ TEKNOLOJİ", (self.output / "captions.ass").read_text())
        self.assertTrue(Path(result["video_path"]).is_file())

    def test_kinetic_export_changes_layouts_and_has_motion_between_cuts(self):
        script = ("Yerel yapay zekâ modelleri bilgisayarda farklı kullanım seçenekleri sunuyor. "
                  "İnternet gereksinimleri kullanılan modele göre değişebiliyor. "
                  "Donanım gereksinimlerini ve model lisanslarını kullanmadan önce kontrol etmek gerekiyor. "
                  "Bu örnekte teknoloji konusunu birlikte inceliyoruz.")
        with patch("urllib.request.urlopen", side_effect=AssertionError("Motion design must be entirely offline")):
            result = render({"title": "Yerel yapay zekâ neden konuşuluyor?", "script": script}, self.output,
                            {"speech": False})
        self.assertGreater(result["duration"], 10)
        self.assertGreaterEqual(result["scene_count"], 4)

        def frame(timestamp):
            response = subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
                                       "-ss", str(timestamp), "-i", result["video_path"], "-frames:v", "1",
                                       "-vf", "crop=720:820:0:0,scale=72:82", "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"],
                                      capture_output=True, check=True, timeout=20)
            self.assertEqual(len(response.stdout), 72 * 82 * 3)
            return response.stdout

        frames = [frame(timestamp) for timestamp in (.4, 3.4, 6.4, 9.4)]
        differences = [sum(abs(a - b) for a, b in zip(first, second)) / len(first)
                       for first, second in zip(frames, frames[1:])]
        self.assertTrue(all(difference > 12 for difference in differences), differences)
        # Compare within one scene as well: transitions alone would be a slideshow.
        first, second = frame(3.4), frame(4.1)
        changed = sum(sum(abs(first[i + c] - second[i + c]) for c in range(3)) > 30
                      for i in range(0, len(first), 3)) / (72 * 82)
        self.assertGreater(changed, .025)
        self.assertIn(r"\move(", (self.output / "captions.ass").read_text())


class SubtitleTests(unittest.TestCase):
    def test_long_words_wrap_and_ass_control_sequences_are_neutralized(self):
        chunks = _subtitle_chunks("Teknolojide " + "uzun" * 25 + " Türkçe karakterler ığüşöç.")
        self.assertTrue(all(len(chunk.splitlines()) <= 2 for chunk in chunks))
        self.assertTrue(all(len(line) <= 27 for chunk in chunks for line in chunk.splitlines()))
        self.assertNotIn("{", _ass_escape(r"{\pos(0,0)}"))
        self.assertNotIn("\\", _ass_escape(r"{\pos(0,0)}"))

    def test_news_abbreviations_decimals_initials_and_quotes_keep_sentence_boundaries(self):
        script = 'Prof. Dr. A. Yılmaz, GPT-4.1 modelini inceledi. "3. nesil çip hazır!" Yeni bir dönem.'
        self.assertEqual(_sentences(script), [
            "Prof. Dr. A. Yılmaz, GPT-4.1 modelini inceledi.",
            '"3. nesil çip hazır!"', "Yeni bir dönem."])

    def test_wide_glyphs_fit_and_long_headlines_have_visible_truncation(self):
        for text in ("W" * 100, "人工智能" * 20):
            for chunk in _subtitle_chunks(text):
                self.assertTrue(all(sum(map(_glyph_width, line)) <= 600 / 44 for line in chunk.splitlines()))
        title = "Yapay zekâ artık cebimizde"
        _, layout = _title_layout(title)
        self.assertEqual(" ".join(layout.split()), title)
        size, layout = _title_layout("Çok uzun bir teknoloji haberi " * 20)
        self.assertLessEqual(len(layout.splitlines()), 4)
        self.assertTrue(layout.endswith("…"))
        self.assertTrue(all(sum(map(_glyph_width, line)) <= 570 / size for line in layout.splitlines()))

    def test_motion_cards_use_verbatim_phrases_and_preserve_statistic_context(self):
        source = "Model %30 daha hızlı değil; bu yalnızca test için verilen bir örnektir."
        phrase = _source_phrase(source)
        self.assertEqual(phrase, source)
        _, fitted = _fit_display(phrase, sizes=(64, 58, 52, 46, 40, 34), width=500, lines=6, height=280)
        self.assertEqual(" ".join(fitted.split()), source)
        scenes = _kinetic_plan(12, [(0, 6, source), (6, 12, "İkinci cümlede gerçek bir sayı bulunmuyor.")])
        self.assertTrue(all(scene["phrase"] in source + " İkinci cümlede gerçek bir sayı bulunmuyor."
                            for scene in scenes[1:]))
        self.assertEqual(scenes[0]["layout"], "hook")
        self.assertEqual(scenes[-1]["end"], 12)

    def test_motion_user_text_cannot_inject_ass_font_or_position_instructions(self):
        title = r"Teknoloji {\fnUntrustedFont} başlığı"
        caption = r"Gerçek metin {\pos(99,99)} devam ediyor."
        scenes = _kinetic_plan(4, [(0, 4, caption)])
        content = "\n".join(_kinetic_events(title, [(0, 4, caption)], scenes, 4, "aurora"))
        self.assertNotIn(r"{\fnUntrustedFont}", content)
        self.assertNotIn(r"{\pos(99,99)}", content)
        visible_fragments = "".join(line.rsplit("}", 1)[-1].replace(r"\N", "") for line in content.splitlines())
        self.assertIn("UntrustedFont", visible_fragments)
        self.assertIn("｛", content)


class CapabilityTests(unittest.TestCase):
    def test_mac_without_turkish_system_voice_uses_installed_espeak(self):
        def which(name):
            return {"say": "/usr/bin/say", "espeak-ng": "/opt/homebrew/bin/espeak-ng"}.get(name)

        with patch("app.media.sys.platform", "darwin"), patch("app.media.shutil.which", side_effect=which), \
                patch("app.media._say_voices", return_value=()), patch("app.media._espeak_voice_error", return_value=""), \
                patch.dict(os.environ, {"LOCAL_TTS_VOICE": ""}):
            engine = _local_engine()
        self.assertEqual(engine["binary"], "/opt/homebrew/bin/espeak-ng")
        self.assertEqual(engine["voice"], "tr")
        self.assertFalse(engine["error"])

    def test_requested_mac_voice_must_be_installed(self):
        with patch("app.media.sys.platform", "darwin"), patch("app.media.shutil.which", return_value="/usr/bin/say"), \
                patch("app.media._say_voices", return_value=("Yelda",)), \
                patch.dict(os.environ, {"LOCAL_TTS_VOICE": "Olmayan"}):
            engine = _local_engine()
        self.assertIsNone(engine["binary"])
        self.assertIn("LOCAL_TTS_VOICE", engine["error"])

    def test_extracted_arm_libraries_are_detected_without_an_x86_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "usr/bin").mkdir(parents=True)
            (root / "usr/bin/espeak-ng").touch()
            data = root / "usr/lib/aarch64-linux-gnu/espeak-ng-data"
            data.mkdir(parents=True)
            with patch("app.media.sys.platform", "linux"), patch("app.media.shutil.which", return_value=None), \
                    patch("app.media._espeak_voice_error", return_value=""), \
                    patch.dict(os.environ, {"LOCAL_TTS_ROOT": str(root), "LOCAL_TTS_VOICE": ""}):
                engine = _local_engine()
            self.assertEqual(engine["env"]["ESPEAK_DATA_PATH"], str(data))
            self.assertIn("aarch64-linux-gnu", engine["env"]["LD_LIBRARY_PATH"])

    def test_ffmpeg_missing_libass_is_actionable_and_probe_is_cached(self):
        _ffmpeg_probe.cache_clear()
        self.addCleanup(_ffmpeg_probe.cache_clear)
        outputs = [b" V....D libx264 H.264\n A....D aac AAC\n", b" ... zoompan V->V Zoom\n", b"ffprobe version"]
        with patch("app.media._run", side_effect=[subprocess.CompletedProcess([], 0, stdout=value) for value in outputs]) as run:
            first = _ffmpeg_probe("/fake/ffmpeg", (), "/fake/ffprobe", ())
            second = _ffmpeg_probe("/fake/ffmpeg", (), "/fake/ffprobe", ())
        self.assertFalse(first["ready"])
        self.assertIn("libass", first["error"])
        self.assertEqual(first, second)
        self.assertEqual(run.call_count, 3)


if __name__ == "__main__":
    unittest.main()
