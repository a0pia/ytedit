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
        world, hud, overlays = capsule.events(r"Başlık {\fnX}", [(0, 36, "Metin bir iki")], scenes, 36, host)
        self.assertEqual(overlays, [])
        self.assertIn("Aopia", "\n".join(hud))
        content = "\n".join(world + hud)
        self.assertIn(r"\clip(", "\n".join(world))
        self.assertIn("Anahtar kelime", content)
        # Burned-in captions: one event per spoken word, the active word lit in lime
        # and the words still to come laid out but invisible.
        captions = [line for line in hud if r"\bord6" in line]
        self.assertEqual(len(captions), 3)
        self.assertTrue(all("METİN" in line and "İKİ" in line for line in captions))
        self.assertIn(r"{\alpha&HFF&}İKİ", captions[0])
        self.assertIn(r"\1c&H3AF2D9&", captions[2])  # Kapsül pack highlight.
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
            self.assertEqual(result["host_look"], "vega")
            frame = subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-ss", "0.5", "-i", result["video_path"],
                                    "-frames:v", "1", "-vf", "crop=10:10:660:400", "-f", "rawvideo", "-pix_fmt", "rgb24",
                                    "pipe:1"], capture_output=True, check=True).stdout
            self.assertLess(sum(frame) / len(frame), 80)  # Dark cyber panel by default.


class AttentionTests(unittest.TestCase):
    def test_camera_stays_still_except_at_emphasis_moments(self):
        from app import capsule
        scenes = _host_plan(_kinetic_plan(36, LONG, 2.8))
        self.assertEqual(capsule.camera(scenes, 36, [])[0], "1.0")
        moments = [{"word": "40", "start": 7.3, "end": 7.7, "score": 3.0, "reason": "sayı"}]
        zoom, x, y = capsule.camera(scenes, 36, moments)
        self.assertEqual(zoom.count("(3-2*"), 1)  # One smooth punch-in, no per-scene zoom.
        self.assertIn("it-7.020", zoom)  # Starts easing just before the word is spoken.
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


class PaletteTests(unittest.TestCase):
    def test_scene_colours_return_to_the_main_palette_every_third_scene(self):
        from app import capsule
        names = [capsule.palette(index)["name"] for index in range(9)]
        self.assertEqual(names[0::3], ["main"] * 3)
        self.assertTrue(all(name != "main" for i, name in enumerate(names) if i % 3))
        self.assertEqual(len(set(names)), 5)

    def test_captions_are_cut_into_short_bursts(self):
        from app import capsule
        bursts = capsule.caption_chunks([(0, 4, "Yeni nesil telefon çipleri yapay zekâyı\ncihazda çalıştırıyor.")])
        self.assertTrue(all(1 <= len(words) <= 4 for _start, _end, words, _times in bursts))
        self.assertEqual(" ".join(w for *_x, words, _t in bursts for w in words),
                         "Yeni nesil telefon çipleri yapay zekâyı cihazda çalıştırıyor.")
        self.assertEqual(bursts[-1][1], 4)


class BrandTests(unittest.TestCase):
    def test_story_brand_picks_its_pack_and_turkish_suffixes_match(self):
        from app import palettes
        self.assertEqual(palettes.primary_brand("Claude'un yeni sürümü", "Anthropic duyurdu."), "claude")
        self.assertEqual(palettes.choose_pack("auto", "Claude'un yeni sürümü", ""), "cyber-anthropic")
        self.assertEqual(palettes.PACKS["cyber-anthropic"]["pop"], "D97757")
        self.assertEqual(palettes.choose_pack("ocean", "Claude", ""), "ocean")
        self.assertIn(palettes.choose_pack("auto", "Yerel haber", "Belediye duyurdu."), palettes.GENERAL_PACKS)
        self.assertIsNone(palettes.primary_brand("Metaverse değil", "metal fiyatları"))

    def test_every_pack_keeps_text_readable(self):
        from app import palettes
        for name, pack in palettes.PACKS.items():
            for scene in pack["scenes"]:
                self.assertGreaterEqual(palettes.contrast(scene["card_ink"], scene["card"]), 4.5, (name, scene["name"]))
                self.assertGreaterEqual(palettes.contrast(scene["ink"], scene["panel"]), 3.0, (name, scene["name"]))
                self.assertGreaterEqual(palettes.contrast(scene["bird"], scene["panel"]), 2.0, (name, scene["name"]))

    def test_brand_logo_or_wordmark_appears_where_the_brand_is_mentioned(self):
        from app import capsule
        spans = [(0, 4, "Claude yeni sürümünü duyurdu."), (4, 8, "Diğer haberler sürüyor."),
                 (8, 12, "Claude kod yazıyor.")]
        scenes = capsule.perches(_host_plan(_kinetic_plan(12, spans, 2.8)))
        host = {"look": "kuzgun", "name": "Kuzgun", "spans": spans, "levels": None}
        brand = {"slug": "claude", "name": "Claude", "stems": ("claude",), "logo": None}
        world, _hud, overlays = capsule.events("Claude", [(0, 12, "Metin")], scenes, 12, host, "anthropic", brand)
        self.assertEqual(overlays, [])
        self.assertTrue(any(line.endswith("}Claude") for line in world))
        brand["logo"] = "/tmp/claude.png"
        _world, _hud, overlays = capsule.events("Claude", [(0, 12, "Metin")], scenes, 12, host, "anthropic", brand)
        self.assertGreaterEqual(len(overlays), 1)
        self.assertEqual(overlays[0]["size"], 150 - 2 * round(150 * .12))


class AndroidTests(unittest.TestCase):
    def test_vega_android_has_ski_goggles_eyes_and_an_equalizer_mouth(self):
        look = presenter.LOOKS["vega"]
        pose = {"gaze": (0, 0), "open": 1.0, "mouth": ("C", 22, 18), "brow": (.2, 4), "level": .9}
        names = [name for name, _c, _p in presenter.head_parts(look, "2EE6FF", pose)]
        self.assertTrue({"head", "goggle-strap", "goggle-frame", "goggle-lens", "eyes", "brows", "mouth-eq"} <= set(names))
        talking = next(path for name, _c, path in presenter.head_parts(look, "2EE6FF", pose) if name == "mouth-eq")
        self.assertEqual(talking.count("m "), 7)  # Seven equalizer bars while speaking.
        quiet = next(path for name, _c, path in presenter.head_parts(look, "2EE6FF", {**pose, "mouth": ("X", 0, 0)})
                     if name == "mouth-eq")
        self.assertEqual(quiet.count("m "), 1)
        body = [name for name, _c, _p in presenter.body_parts(look, "2EE6FF", pose)]
        self.assertTrue({"torso", "circuits", "core"} <= set(body))

    def test_neon_parts_glow(self):
        scenes = _host_plan(_kinetic_plan(6, SPANS[:2], 2.8))
        events = presenter.puppet_events(look_id="vega", accent_for=lambda _i: "2EE6FF", spans=SPANS, scenes=scenes,
                                         duration=6, levels=None, seed="s")
        self.assertTrue(any(r"\blur" in line for line in events))

    def test_cyber_packs_are_dark_and_readable(self):
        from app import palettes
        for name in ("cyber", "cyber-amber", "cyber-green", "cyber-anthropic"):
            pack = palettes.PACKS[name]
            self.assertTrue(pack["cyber"])
            self.assertTrue(all(palettes.luminance(scene["panel"]) < .05 for scene in pack["scenes"]))


class TypographyMapTests(unittest.TestCase):
    def test_map_scores_numbers_brands_turns_and_questions(self):
        from app import capsule, emphasis
        segments = [(0, 3, "Anthropic, Claude modelinin"), (3, 6, "yeni sürümünü duyurdu."),
                    (6, 9, "Model yüzde 40 daha hızlı."), (9, 12, "Ancak testler bağımsız değil."),
                    (12, 15, "Peki bu sizin için ne demek?")]
        words = {w["word"]: w for w in emphasis.typography_map(capsule.caption_chunks(segments))}
        self.assertEqual(words["40"]["reason"], "sayı")
        self.assertEqual(words["Claude"]["reason"], "marka")
        self.assertEqual(words["testler"]["reason"], "dönüş sonrası")
        self.assertEqual(words["demek?"]["reason"], "soru")
        self.assertEqual(words["bu"]["score"], 0)  # Short function words are never stressed.
        self.assertEqual(words["daha"]["score"], 0)

    def test_moments_are_few_and_spaced(self):
        from app import capsule
        segments = [(i * 3.0, i * 3.0 + 3, f"Model yüzde {i}0 daha hızlı.") for i in range(10)]
        moments = capsule.emphasis_moments(segments, 30)
        self.assertLessEqual(len(moments), round(30 / 6.5))
        self.assertTrue(all(b["start"] - a["start"] >= 3.5 for a, b in zip(moments, moments[1:])))
        self.assertEqual(capsule.emphasis_moments([(0, 4, "Sakin bir cümle burada")], 4), [])

    def test_stressed_caption_word_is_enlarged(self):
        from app import capsule
        segments = [(0, 2, "Giriş cümlesi burada."), (2, 5, "Model yüzde 40 daha hızlı.")]
        scenes = _host_plan(_kinetic_plan(5, segments, 2.8))
        _world, hud, _overlays = capsule.events("Başlık", segments, scenes, 5, None)
        self.assertTrue(any(r"\fscx175" in line and "40" in line for line in hud))
