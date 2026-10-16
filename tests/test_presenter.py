"""The code-drawn presenter rig and the hosted ("host") video design."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import wave

from app import presenter
from app.media import MediaError, _host_plan, _kinetic_events, _kinetic_plan, render


SPANS = [(0, 3, "Merhaba teknoloji dünyası!"), (3, 7, "Bu hafta ne oldu?"),
         (7, 11, "Yeni modeller daha hızlı çalışıyor."), (11, 15, "Kaynağı kontrol edin.")]
LONG = [(i * 3.0, i * 3.0 + 3, f"Cümle numarası {i} teknoloji haberini anlatıyor.") for i in range(12)]


class RigTests(unittest.TestCase):
    def test_host_plan_varies_every_cut_and_returns_to_the_host(self):
        scenes = _host_plan(_kinetic_plan(36, LONG, 2.8))
        self.assertEqual((scenes[0]["host"], scenes[0].get("wave")), ("big", True))
        self.assertEqual({scene["host"] for scene in scenes}, {"big", "pip", "off"})
        self.assertGreaterEqual(len({scene["layout"] for scene in scenes}), 6)
        self.assertTrue(all(a["layout"] != b["layout"] for a, b in zip(scenes, scenes[1:])))
        self.assertEqual(scenes[-1]["layout"], "host")
        self.assertTrue(all(scene["host"] == {"hook": "big", "host": "big", "keyword": "off"}.get(scene["layout"], "pip")
                            for scene in scenes))

    def test_questions_cut_back_to_the_host(self):
        scenes = _host_plan(_kinetic_plan(15, SPANS, 2.8))
        question = next(scene for scene in scenes if "?" in scene["phrase"])
        self.assertEqual(question["layout"], "host")

    def test_mouth_follows_loudness_and_text_while_eyes_blink(self):
        scenes = _host_plan(_kinetic_plan(15, SPANS))
        levels = [0.0] * 12 + [1.0] * 168
        rig = presenter.Rig("seed", SPANS, scenes, 15, levels)
        self.assertEqual(rig.pose(.5)["mouth"][0], "X")
        open_shapes = {rig.pose(1 + i / 12)["mouth"][0] for i in range(24)}
        self.assertTrue(open_shapes - {"X"}, open_shapes)
        self.assertTrue(any(rig.pose(blink + .02)["open"] == 0 for blink in rig.blinks))
        # Identical inputs always animate identically.
        again = presenter.Rig("seed", SPANS, scenes, 15, levels)
        self.assertEqual(rig.pose(4.2), again.pose(4.2))

    def test_names_are_bounded_and_uppercased_with_turkish_rules(self):
        self.assertEqual(presenter.clean_name("  ", "kaan"), "Kaan")
        self.assertEqual(len(presenter.clean_name("x" * 40, "nova")), presenter.MAX_NAME)
        self.assertEqual(presenter.display_name("Işık İnci"), "IŞIK İNCİ")

    def test_speech_levels_detect_loud_frames_and_silence(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "voice.wav"
            with wave.open(str(path), "wb") as audio:
                audio.setnchannels(1)
                audio.setsampwidth(2)
                audio.setframerate(24000)
                audio.writeframes(b"\0\0" * 24000 + (b"\x00\x40\x00\xc0" * 12000))
            levels = presenter.speech_levels(path, 2)
            self.assertLess(max(levels[:10]), .05)
            self.assertGreater(min(levels[14:22]), .9)
            silent = Path(temporary) / "silent.wav"
            with wave.open(str(silent), "wb") as audio:
                audio.setnchannels(1)
                audio.setsampwidth(2)
                audio.setframerate(24000)
                audio.writeframes(b"\0\0" * 48000)
            self.assertIsNone(presenter.speech_levels(silent, 2))

    def test_user_text_cannot_inject_ass_into_host_name_or_bubbles(self):
        scenes = _host_plan(_kinetic_plan(36, LONG, 2.8))
        host = {"look": "nova", "name": r"{\pos(1,1)}Nova", "spans": LONG, "levels": None}
        content = "\n".join(_kinetic_events("Başlık", [(0, 36, "Metin")], scenes, 36, "aurora", host))
        self.assertNotIn(r"{\pos(1,1)}", content)
        self.assertIn(r"\clip(", content)  # The PiP badge masks the puppet.


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg is required")
class HostRenderTests(unittest.TestCase):
    def test_real_hosted_video_animates_the_presenter(self):
        script = ("Yerel yapay zekâ modelleri bilgisayarda farklı kullanım seçenekleri sunuyor. "
                  "Peki bu sizin için ne anlama geliyor? "
                  "Donanım gereksinimlerini ve lisansları kontrol etmek gerekiyor.")
        with tempfile.TemporaryDirectory() as temporary, \
                patch("urllib.request.urlopen", side_effect=AssertionError("Presenter must be offline")):
            result = render({"title": "Yerel yapay zekâ", "script": script}, Path(temporary),
                            {"speech": False, "video_design": "host", "host_look": "kaan", "host_name": "Deniz"})
            self.assertEqual((result["design"], result["host_look"], result["host_name"]), ("host", "kaan", "Deniz"))
            self.assertIn("DENİZ ANLATIYOR", Path(temporary, "captions.ass").read_text())

            def frame(timestamp):
                return subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-ss", str(timestamp),
                                       "-i", result["video_path"], "-frames:v", "1", "-vf",
                                       "crop=300:300:210:520,scale=60:60", "-f", "rawvideo", "-pix_fmt", "rgb24",
                                       "pipe:1"], capture_output=True, check=True, timeout=20).stdout

            first, second = frame(.9), frame(1.6)
            changed = sum(abs(a - b) > 30 for a, b in zip(first, second)) / len(first)
            self.assertGreater(changed, .01)  # The face moves within one scene.
            probe = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-of", "json",
                                               result["video_path"]], capture_output=True, check=True).stdout)
            video = next(s for s in probe["streams"] if s["codec_type"] == "video")
            self.assertEqual((video["width"], video["height"]), (720, 1280))

    def test_unknown_look_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary, self.assertRaises(MediaError):
            render({"title": "x", "script": "Merhaba."}, Path(temporary),
                   {"speech": False, "video_design": "host", "host_look": "yok"})


if __name__ == "__main__":
    unittest.main()


class CapsuleThemeTests(unittest.TestCase):
    def test_capsule_theme_draws_the_dashboard_chassis_and_escapes_text(self):
        from app import capsule
        scenes = _host_plan(_kinetic_plan(36, LONG, 2.8))
        host = {"look": "kuzgun", "name": r"K{\b1}uzgun", "spans": LONG, "levels": None}
        world, hud = capsule.events(r"Başlık {\fnX}", [(0, 36, "Metin bir iki")], scenes, 36, host)
        content = "\n".join(world + hud)
        self.assertIn(r"\clip(", "\n".join(world))
        self.assertIn("Anahtar kelime", content)
        # The active caption word is highlighted in lime, one event per word.
        self.assertEqual(sum("Metin bir iki" in line.replace(r"{\1c&H3AF2D9&}", "").replace(r"{\1c&HFFFFFF&}", "")
                             for line in hud), 3)
        self.assertIn("Teknoloji gündemi", content)
        self.assertIn(r"\1c&H3AF2D9&", content)  # Lime accent in ASS BGR order.
        self.assertNotIn(r"{\fnX}", content)
        self.assertNotIn(r"{\b1}", content)
        self.assertIn("Son söz", content)

    def test_volt_mascot_has_led_eyes_antenna_and_blinks(self):
        look = presenter.LOOKS["volt"]
        pose = {"gaze": (0, 0), "open": 1.0, "mouth": ("X", 0, 0), "brow": (.2, 4), "level": .8}
        names = [name for name, _color, _path in presenter.head_parts(look, "D9F23A", pose)]
        self.assertTrue({"leds", "bulb", "glow", "visor", "cups", "mic"} <= set(names))
        closed = presenter.head_parts(look, "D9F23A", {**pose, "open": 0.0})
        self.assertNotIn("led-shine", [name for name, _c, _p in closed])

    @unittest.skipUnless(shutil.which("ffmpeg"), "FFmpeg is required")
    def test_real_capsule_render(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = render({"title": "Kapsül", "script": "Merhaba teknoloji. Bu bir deneme mi? Evet."},
                            Path(temporary), {"speech": False, "video_design": "host", "style": "capsule"})
            self.assertEqual(result["host_look"], "kuzgun")
            frame = subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-ss", "0.5", "-i", result["video_path"],
                                    "-frames:v", "1", "-vf", "crop=10:10:660:400", "-f", "rawvideo", "-pix_fmt", "rgb24",
                                    "pipe:1"], capture_output=True, check=True).stdout
            self.assertGreater(sum(frame) / len(frame), 120)  # Light panel, not a dark scene.


class AttentionTests(unittest.TestCase):
    def test_camera_moves_differ_per_scene_and_stay_inside_the_canvas(self):
        from app import capsule
        scenes = _host_plan(_kinetic_plan(36, LONG, 2.8))
        zoom, x, y = capsule.camera(scenes, 36)
        self.assertEqual(zoom.count("if(lt(it,"), len(scenes) - 1)
        self.assertIn("exp(", zoom)  # Punch-ins on cuts.
        self.assertTrue(x.startswith("max(0,min(iw-iw/zoom,") and y.startswith("max(0,min(ih-ih/zoom,"))

    def test_keyword_is_a_verbatim_word(self):
        from app import capsule
        self.assertEqual(capsule.keyword("Pil ömrü “iyileşiyor”, deniyor."), "iyileşiyor")

    def test_effects_mix_leaves_narration_untouched(self):
        from app import sfx
        with tempfile.TemporaryDirectory() as temporary:
            narration, mixed = Path(temporary) / "n.wav", Path(temporary) / "m.wav"
            with wave.open(str(narration), "wb") as audio:
                audio.setnchannels(1)
                audio.setsampwidth(2)
                audio.setframerate(24000)
                audio.writeframes(b"\0\0" * 48000)
            sfx.mix(narration, mixed, [1.0], [1.5])
            with wave.open(str(narration), "rb") as audio:
                self.assertEqual(set(audio.readframes(48000)), {0})
            with wave.open(str(mixed), "rb") as audio:
                self.assertEqual(audio.getnframes(), 48000)
                frames = audio.readframes(48000)
            self.assertGreater(max(frames[2 * 23000:2 * 25000]), 0)


class RoamingTests(unittest.TestCase):
    def test_raven_flies_between_perches_and_lands_on_interface_elements(self):
        from app import capsule
        scenes = capsule.perches(_host_plan(_kinetic_plan(36, LONG, 2.8)))
        rig = presenter.Rig("seed", LONG, scenes, 36, None, roam=True)
        second = scenes[1]["perch"][0]
        flying = rig.pose(second[0] + .2)
        self.assertGreater(flying["wings"][0], 0)
        landed = rig.pose(second[0] + 1.6)
        self.assertEqual(landed["roam"][:2], (second[1], second[2]))
        self.assertTrue(any(len(scene["perch"]) == 2 for scene in scenes))  # Split scenes hop twice.

    def test_raven_head_moves_in_bird_like_snaps(self):
        from app import capsule
        scenes = capsule.perches(_host_plan(_kinetic_plan(36, LONG, 2.8)))
        rig = presenter.Rig("seed", LONG, scenes, 36, None, roam=True)
        angles = {round(rig.pose(10 + i / 12)["angle"]) for i in range(36)}
        self.assertGreater(len(angles), 1)
