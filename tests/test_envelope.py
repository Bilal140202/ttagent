"""harvest() end-to-end with patched slots and downloads (fully offline)."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _loader import tool
from fixtures import (CDN_HD, CDN_JPEG, CDN_MP4, CDN_MUSIC, FAKE_HANDLE,
                      FAKE_ID, JPEG_HEAD, MP3_HEAD, MP4_HEAD)


def _fake_file_response(head):
    """A file-like urlopen result: returns `head` once, then EOF."""
    state = {"consumed": False}
    resp = mock.MagicMock()

    def _read(n):
        if state["consumed"]:
            return b""
        state["consumed"] = True
        return head

    resp.read = _read
    resp.headers = {}
    cm = mock.MagicMock()
    cm.__enter__ = mock.Mock(return_value=resp)
    cm.__exit__ = mock.Mock(return_value=False)
    return cm


def _synthetic_post():
    return {
        "video_id": FAKE_ID, "handle": FAKE_HANDLE,
        "canonical_url": f"https://www.tiktok.com/@{FAKE_HANDLE}/video/{FAKE_ID}",
        "title": "synthetic title", "region": "US",
        "created_at": 1700000000, "duration": 12,
        "cover_url": CDN_JPEG, "origin_cover_url": None,
        "author": {"unique_id": FAKE_HANDLE,
                   "nickname": "Synthetic Creator",
                   "avatar_url": None, "author_id": None},
        "music": {"url": CDN_MUSIC, "title": "original sound",
                  "author": FAKE_HANDLE, "original": True,
                  "duration": 12, "music_id": "7111111111111111111"},
        "stats": {"plays": 1000, "likes": 100, "comments": 10,
                  "shares": 5, "collects": 7, "downloads": 2},
        "media_items": [{
            "type": "video", "url": CDN_MP4, "hd_url": CDN_HD,
            "play_url": CDN_MP4, "watermarked_url": None,
            "poster_url": CDN_JPEG, "width": 1080, "height": 1920,
            "duration": 12,
        }],
        "extraction_source": "tikwm",
    }


class HarvestTests(unittest.TestCase):
    def setUp(self):
        tool.ERRORS.clear()

    def _run(self, post=None, do_download=True, do_music=True,
             n_downloads=None, heads=None):
        post = post or _synthetic_post()
        norm = {"input": FAKE_ID, "video_id": FAKE_ID, "handle": None,
                "short_url": None, "kind": "bare",
                "canonical_url": f"https://www.tiktok.com/@i/video/{FAKE_ID}"}
        with mock.patch.object(tool, "DECODE_SLOT_FNS", [
                ("synthetic", lambda u: ("ok", post))]), \
             mock.patch.object(tool.time, "sleep"):
            with tempfile.TemporaryDirectory() as td:
                out = Path(td) / "out"
                if do_download and n_downloads:
                    with mock.patch.object(
                            tool.urllib.request, "urlopen",
                            side_effect=[_fake_file_response(h)
                                         for h in heads]):
                        env = tool.harvest(norm, out, do_download=True,
                                           do_music=do_music)
                else:
                    env = tool.harvest(norm, out, do_download=do_download,
                                       do_music=do_music)
                files = sorted(p.name for p in out.iterdir())
        return env, files

    def test_full_harvest_video_music_cover(self):
        # downloads: video, hd variant, cover, music = 4 files
        heads = [MP4_HEAD, MP4_HEAD, JPEG_HEAD, MP3_HEAD]
        env, files = self._run(n_downloads=4, heads=heads)
        self.assertEqual(env["status"], "ok")
        self.assertEqual(env["schema_version"], "1.0")
        self.assertEqual(env["video"]["video_id"], FAKE_ID)
        self.assertEqual(env["video"]["author"]["unique_id"], FAKE_HANDLE)
        media = env["video"]["media"]
        self.assertEqual(media["video"]["file"], f"{FAKE_ID}_video.mp4")
        self.assertEqual(media["video"]["hd_file"], f"{FAKE_ID}_hd.mp4")
        self.assertEqual(media["music"]["file"], f"{FAKE_ID}_music.mp3")
        self.assertTrue(media["covers"]["cover_downloaded"])
        self.assertEqual(env["metadata"]["counts"]["downloaded_media"], 4)
        self.assertEqual(env["errors"], [])
        self.assertIn(f"{FAKE_ID}_video.mp4", files)
        self.assertIn(f"{FAKE_ID}_music.mp3", files)
        self.assertIn("video_manifest.json", files)

    def test_metadata_only(self):
        env, files = self._run(do_download=False)
        self.assertEqual(env["status"], "ok")
        self.assertEqual(env["metadata"]["counts"]["downloaded_media"], 0)
        self.assertEqual(files, ["video_manifest.json"])
        self.assertFalse(env["video"]["media"]["video"]["downloaded"])
        self.assertTrue(env["video"]["media"]["video"]["downloadable"])

    def test_oembed_metadata_only_status(self):
        post = _synthetic_post()
        post["media_items"][0]["url"] = None
        post["media_items"][0]["hd_url"] = None
        post["music"]["url"] = None
        post["extraction_source"] = "oembed"
        env, files = self._run(post=post, do_download=False)
        self.assertEqual(env["status"], "partial")
        self.assertEqual(env["video"]["media"]["video"]["reason"],
                         "no_video_url_exposed")
        self.assertFalse(env["video"]["media"]["video"]["downloadable"])

    def test_no_music_flag(self):
        env, files = self._run(do_music=False, do_download=False)
        self.assertFalse(env["video"]["media"]["music"]["downloaded"])
        self.assertEqual(env["request"]["options"]["download_music"], False)

    def test_outside_allowlist_not_attempted(self):
        post = _synthetic_post()
        post["media_items"][0]["url"] = "https://evil.example.com/v.mp4"
        post["media_items"][0]["hd_url"] = None
        post["music"]["url"] = None
        env, files = self._run(post=post, do_download=True, do_music=False)
        vid = env["video"]["media"]["video"]
        self.assertFalse(vid["downloadable"])
        self.assertEqual(vid["reason"], "url_outside_delivery_allowlist")

    def test_slideshow_harvest(self):
        post = _synthetic_post()
        post["media_items"] = [
            {"type": "image", "url": CDN_JPEG, "slide_index": 1},
            {"type": "image", "url": CDN_JPEG, "slide_index": 2},
        ]
        heads = [JPEG_HEAD, JPEG_HEAD, MP3_HEAD]
        env, files = self._run(post=post, n_downloads=3, heads=heads)
        self.assertEqual(env["metadata"]["counts"]["images"], 2)
        self.assertEqual(env["metadata"]["counts"]["videos"], 0)
        self.assertIn(f"{FAKE_ID}_img1.jpg", files)
        self.assertIn(f"{FAKE_ID}_img2.jpg", files)

    def test_envelope_required_keys(self):
        env, files = self._run(do_download=True, do_music=False)
        for key in ("schema_version", "source", "request", "status",
                    "video", "errors", "metadata"):
            self.assertIn(key, env)
        self.assertEqual(env["source"]["tool"], "ttagent")
        self.assertEqual(env["request"]["options"],
                         {"download_media": True, "download_music": False})


class EmptyPathTests(unittest.TestCase):
    def test_all_slots_fail_envelope(self):
        tool.ERRORS.clear()
        with mock.patch.object(tool, "DECODE_SLOT_FNS", [
                ("a", lambda u: ("failed", None))]), \
             mock.patch.object(tool.time, "sleep"):
            with tempfile.TemporaryDirectory() as td:
                env = tool.harvest(
                    {"input": "x", "video_id": FAKE_ID, "handle": None,
                     "short_url": None, "kind": "bare",
                     "canonical_url": f"https://www.tiktok.com/@i/video/{FAKE_ID}"},
                    Path(td), do_download=False)
                self.assertEqual(env["status"], "empty")
                self.assertIsNone(env["video"])
                self.assertEqual(env["errors"][-1]["code"],
                                 tool.E_DECODE_FAILED)


if __name__ == "__main__":
    unittest.main()
