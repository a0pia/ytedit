"""Real local audio decoding, pause estimates, and uploaded-narration exports."""
from array import array
import json
import math
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import wave

from app.audio import (AudioError, inspect_audio, normalize_audio, plan_captions,
                       validate_captions)
from app.media import MediaError, _uploaded_kinetic_plan, render


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg is required")
class UploadedAudioTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def wav(self, name="voice.wav", duration=2.4, channels=1, sample_rate=24000,
            active=None, amplitude=7000, dc=False):
        path = self.root / name
        samples = array("h")
        active = active if active is not None else [(0, duration)]
        for index in range(round(duration * sample_rate)):
            timestamp = index / sample_rate
            audible = any(start <= timestamp < end for start, end in active)
            value = amplitude if dc else int(amplitude * math.sin(2 * math.pi * 210 * timestamp))
            for _channel in range(channels):
                samples.append(value if audible else 0)
        with wave.open(str(path), "wb") as output:
            output.setnchannels(channels)
            output.setsampwidth(2)
            output.setframerate(sample_rate)
            output.writeframes(samples.tobytes())
        return path

    def ffmpeg(self, *args):
        return subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y", *map(str, args)],
                              capture_output=True, check=True, timeout=30)

    def probe(self, path):
        result = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
                                capture_output=True, check=True, timeout=15)
        return json.loads(result.stdout)

    def test_wav_metadata_uses_decoded_duration_and_stereo_normalizes_locally(self):
        source = self.wav(channels=2, sample_rate=44100)
        metadata = inspect_audio(source)
        self.assertEqual(metadata["channels"], 2)
        self.assertEqual(metadata["codec"], "pcm_s16le")
        self.assertEqual(metadata["sample_rate"], 44100)
        self.assertAlmostEqual(metadata["duration"], 2.4, places=3)
        target = self.root / "normalized.wav"
        with patch("urllib.request.urlopen", side_effect=AssertionError("No hosted voice calls")):
            duration = normalize_audio(source, target)
        self.assertAlmostEqual(duration, 2.4, places=3)
        with wave.open(str(target), "rb") as audio:
            self.assertEqual((audio.getnchannels(), audio.getframerate(), audio.getsampwidth()), (1, 24000, 2))
            self.assertEqual(audio.getnframes(), round(duration * 24000))
            self.assertTrue(any(audio.readframes(audio.getnframes())))

    def test_actual_mp3_is_accepted_by_content_and_decoded_to_wav(self):
        source = self.wav()
        mp3 = self.root / "untrusted-name.bin"
        self.ffmpeg("-i", source, "-c:a", "libmp3lame", "-f", "mp3", mp3)
        metadata = inspect_audio(mp3)
        self.assertEqual(metadata["format"], "mp3")
        self.assertEqual(metadata["codec"], "mp3")
        self.assertAlmostEqual(metadata["duration"], 2.4, places=3)
        output = self.root / "decoded.wav"
        self.assertAlmostEqual(normalize_audio(mp3, output), 2.4, places=3)
        self.assertAlmostEqual(inspect_audio(output)["duration"], 2.4, places=3)

    def test_invalid_silent_dc_short_and_oversize_audio_are_rejected(self):
        invalid = self.root / "fake.mp3"
        invalid.write_bytes(b"not an audio file")
        playlist = self.root / "voice.wav"
        playlist.write_text("#EXTM3U\nhttps://example.invalid/private.mp3\n")
        cases = [(invalid, "MP3 veya WAV"), (playlist, "MP3 veya WAV"),
                 (self.wav("silent.wav", amplitude=0), "sessiz"),
                 (self.wav("dc.wav", dc=True), "sessiz"),
                 (self.wav("tiny.wav", duration=.39), "0,4"),
                 (self.wav("long.wav", duration=90.02), "90 saniye")]
        for path, message in cases:
            with self.subTest(path=path.name), self.assertRaisesRegex(AudioError, message):
                inspect_audio(path)
        large = self.root / "large.wav"
        with large.open("wb") as file:
            file.truncate(32 * 1024 * 1024 + 1)
        with self.assertRaisesRegex(AudioError, "32 MB"):
            inspect_audio(large)

    def test_stereo_cancellation_is_rejected_after_downmix(self):
        path = self.root / "cancel.wav"
        samples = array("h")
        for i in range(24000):
            value = round(math.sin(i * .04) * 10000)
            samples.extend((value, -value))
        with wave.open(str(path), "wb") as output:
            output.setnchannels(2)
            output.setsampwidth(2)
            output.setframerate(24000)
            output.writeframes(samples.tobytes())
        with self.assertRaisesRegex(AudioError, "sessiz"):
            normalize_audio(path, self.root / "cancel-normalized.wav")

    def test_estimates_follow_actual_leading_trailing_silence_and_keep_full_text(self):
        script = "Birinci bölümün bütün kelimeleri burada. İkinci bölümde teknoloji gündemini inceliyoruz."
        source = self.wav(duration=5, active=[(.8, 1.9), (3, 4.1)])
        captions = plan_captions(script, source)
        self.assertEqual(" ".join(item["text"] for item in captions), script)
        self.assertGreaterEqual(captions[0]["start"], .7)
        self.assertLessEqual(captions[-1]["end"], 4.2)
        self.assertEqual(validate_captions(captions, script, 5), captions)
        self.assertLessEqual(len(captions), 100)
        # Allocation uses the measured pause: weighted first sentence reaches the
        # second voiced interval instead of dividing the entire file uniformly.
        self.assertGreater(captions[0]["end"], 1.5)
        self.assertTrue(all(a["end"] <= b["start"] for a, b in zip(captions, captions[1:])))

    def test_short_audio_and_long_script_still_have_valid_finite_intervals(self):
        source = self.wav(duration=.4)
        script = "Teknoloji gündemi " * 60
        captions = plan_captions(script, source)
        self.assertEqual(validate_captions(captions, script, .4), captions)
        self.assertEqual(" ".join(item["text"] for item in captions), script.strip())
        with self.assertRaisesRegex(AudioError, "1200"):
            plan_captions("x" * 1201, source)

    def test_manual_timings_require_complete_verbatim_order_and_finite_bounds(self):
        valid = [{"start": .2, "end": .8, "text": "Yapay zekâ"},
                 {"start": 1, "end": 1.8, "text": "gündemi."}]
        script = "Yapay zekâ gündemi."
        self.assertEqual(validate_captions(valid, script, 2), valid)
        self.assertEqual(validate_captions([{**valid[0], "text": "Yapay  zeka\u0302"}, valid[1]], script, 2), valid)
        variants = [[], [{**valid[0], "start": float("nan")}, valid[1]],
                    [{**valid[0], "end": float("inf")}, valid[1]],
                    [{**valid[0], "start": -.1}, valid[1]],
                    [{**valid[0], "end": .21}, valid[1]],
                    [valid[0], {**valid[1], "start": .7}],
                    [valid[0], {**valid[1], "end": 2.1}],
                    [{**valid[0], "start": True}, valid[1]],
                    [{**valid[0], "start": "0.2"}, valid[1]],
                    [{**valid[0], "text": "Yeni bilgi"}, valid[1]],
                    [valid[1], valid[0]], [valid[0]],
                    [{"start": 0, "end": 2, "text": ""}], valid * 51]
        for rows in variants:
            with self.subTest(rows=rows), self.assertRaises(AudioError):
                validate_captions(rows, script, 2)

    def test_uploaded_export_keeps_original_normalized_wave_and_never_calls_tts(self):
        source = self.wav(active=[(.3, 1.1), (1.3, 2.1)])
        script = "Bugünün teknoloji haberlerini inceliyoruz."
        output = self.root / "export"
        with patch("app.media._speak", side_effect=AssertionError("Uploaded voice must never synthesize")), \
                patch("app.media._local_engine", side_effect=AssertionError("No TTS probing")), \
                patch("urllib.request.urlopen", side_effect=AssertionError("No network")):
            result = render({"title": "Teknoloji", "script": script, "audio_path": str(source)}, output,
                            {"tts_provider": "uploaded", "speech": True})
        self.assertEqual((output / "narration.wav").read_bytes(), source.read_bytes())
        expected_pcm = self.ffmpeg("-i", source, "-f", "s16le", "pipe:1").stdout
        actual_pcm = self.ffmpeg("-i", output / "narration.wav", "-f", "s16le", "pipe:1").stdout
        self.assertEqual(actual_pcm, expected_pcm)
        self.assertEqual(result["provider"], "Yüklenen ses")
        self.assertEqual(result["voice"], "Harici kayıt")
        self.assertEqual(result["subtitle_timing"], "audio_estimated")
        self.assertEqual(result["duration"], inspect_audio(source)["duration"])
        self.assertTrue(result["speech"])
        self.assertEqual(result["design"], "kinetic")
        self.assertGreaterEqual(result["scene_count"], 2)
        metadata = self.probe(result["video_path"])
        audio = next(stream for stream in metadata["streams"] if stream["codec_type"] == "audio")
        self.assertEqual(audio["codec_name"], "aac")
        self.assertAlmostEqual(float(audio["duration"]), 2.4, delta=.025)
        self.assertAlmostEqual(float(metadata["format"]["duration"]), 2.4, delta=1 / 24 + .005)
        self.assertEqual(" ".join(line for line in (output / "captions.srt").read_text().splitlines()
                                  if line and "-->" not in line and not line.isdigit()), script)

    def test_manual_export_honors_edited_timings_and_classic_design(self):
        source = self.wav()
        captions = [{"start": .4, "end": 1.2, "text": "Yapay zekâ"},
                    {"start": 1.5, "end": 2.1, "text": "gündemi."}]
        result = render({"title": "Teknoloji", "script": "Yapay zekâ gündemi.", "audio_path": str(source),
                         "audio_captions": captions, "audio_timing_mode": "manual"}, self.root / "manual",
                        {"tts_provider": "uploaded", "speech": True, "video_design": "classic"})
        self.assertEqual(result["subtitle_timing"], "manual")
        self.assertEqual(result["design"], "kinetic")  # Legacy "classic" now renders with Remotion.
        self.assertIn("00:00:00,400 --> 00:00:01,200", Path(result["subtitle_path"]).read_text())
        self.assertIn("00:00:01,500 --> 00:00:02,100", Path(result["subtitle_path"]).read_text())

    def test_invalid_uploaded_requests_fail_without_fallback_and_clean_staging(self):
        source = self.wav()
        projects = [{"script": "Merhaba."},
                    {"script": "Merhaba.", "audio_path": str(source), "audio_timing_mode": "manual"},
                    {"script": "Merhaba.", "audio_path": str(source), "audio_captions":
                     [{"start": 0, "end": 2, "text": "Yanlış metin."}]}]
        with patch("app.media._speak", side_effect=AssertionError("No fallback")), \
                patch("app.media._local_engine", side_effect=AssertionError("No fallback")):
            for index, project in enumerate(projects):
                output = self.root / f"failed-{index}"
                with self.subTest(project=project), self.assertRaises(MediaError):
                    render(project, output, {"tts_provider": "uploaded", "speech": True})
                self.assertEqual(list(output.iterdir()), [])
            with self.assertRaisesRegex(MediaError, "açık"):
                render(projects[0], self.root / "muted", {"tts_provider": "uploaded", "speech": False})

    def test_long_manual_captions_export_in_two_lines_with_complete_text_and_original_gaps(self):
        source = self.wav()
        script = "Teknoloji " * 119 + "gelişiyor."
        self.assertEqual(len(script), 1200)
        words = script.split()
        cases = [
            [{"start": .2, "end": 2.2, "text": script}],
            [{"start": .2, "end": 1.2, "text": " ".join(words[:65])},
             {"start": 1.6, "end": 2.2, "text": " ".join(words[65:])}],
        ]

        def seconds(timestamp):
            hours, minutes, tail = timestamp.split(":")
            whole, milliseconds = tail.split(",")
            return int(hours) * 3600 + int(minutes) * 60 + int(whole) + int(milliseconds) / 1000

        for case, captions in enumerate(cases):
            with self.subTest(captions=len(captions)):
                result = render({"title": "Teknoloji", "script": script, "audio_path": str(source),
                                 "audio_captions": captions, "audio_timing_mode": "manual"},
                                self.root / f"long-manual-{case}", {"tts_provider": "uploaded", "speech": True})
                entries = []
                for block in Path(result["subtitle_path"]).read_text().strip().split("\n\n"):
                    lines = block.splitlines()
                    self.assertLessEqual(len(lines[2:]), 2)
                    self.assertTrue(all(len(line) <= 27 for line in lines[2:]))
                    self.assertNotIn("…", block)
                    start, end = map(seconds, lines[1].split(" --> "))
                    entries.append({"start": start, "end": end, "text": " ".join(lines[2:])})
                self.assertGreater(len(entries), len(captions))
                self.assertEqual(" ".join(entry["text"] for entry in entries), script)
                self.assertTrue(all(a["end"] <= b["start"] for a, b in zip(entries, entries[1:])))
                for caption in captions:
                    group = [entry for entry in entries if caption["start"] <= entry["start"] and entry["end"] <= caption["end"]]
                    self.assertEqual(group[0]["start"], caption["start"])
                    self.assertEqual(group[-1]["end"], caption["end"])
                    self.assertEqual(" ".join(entry["text"] for entry in group), caption["text"])
                if len(captions) == 2:
                    self.assertFalse(any(entry["start"] < 1.6 and entry["end"] > 1.2 for entry in entries))
                self.assertEqual(result["subtitle_timing"], "manual")
                self.assertTrue(Path(result["video_path"]).is_file())

    def test_uploaded_scene_changes_follow_caption_ends(self):
        spans = [(0, 1.5, "Birinci cümle."), (2, 3.3, "İkinci cümle."),
                 (4, 6.1, "Üçüncü cümle."), (6.5, 8.9, "Son cümle.")]
        scenes = _uploaded_kinetic_plan(10, spans)
        self.assertEqual(scenes[0]["end"], 3.3)
        self.assertEqual(scenes[-1]["end"], 10)
        self.assertTrue(all(scene["end"] in [end for _, end, _ in spans] + [10] for scene in scenes))


if __name__ == "__main__":
    unittest.main()
