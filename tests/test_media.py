"""Exercise actual FFmpeg outputs without calling a hosted voice API."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from app.media import MediaError, _ass_escape, _subtitle_chunks, capabilities, render


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
        self.assertEqual(progress[-1], 100)
        self.assertEqual(progress, sorted(progress))

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


class SubtitleTests(unittest.TestCase):
    def test_long_words_wrap_and_ass_control_sequences_are_neutralized(self):
        chunks = _subtitle_chunks("Teknolojide " + "uzun" * 25 + " Türkçe karakterler ığüşöç.")
        self.assertTrue(all(len(chunk.splitlines()) <= 2 for chunk in chunks))
        self.assertTrue(all(len(line) <= 27 for chunk in chunks for line in chunk.splitlines()))
        self.assertNotIn("{", _ass_escape(r"{\pos(0,0)}"))
        self.assertNotIn("\\", _ass_escape(r"{\pos(0,0)}"))


if __name__ == "__main__":
    unittest.main()
