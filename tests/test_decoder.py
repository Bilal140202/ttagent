"""Decode-slot parsers against synthetic payloads (no network)."""
import unittest
from unittest import mock

from _loader import tool
from fixtures import (CDN_HD, CDN_JPEG, CDN_MP4, CDN_MUSIC, CDN_WM,
                      FAKE_HANDLE, FAKE_ID, embed_html_shell,
                      embed_html_universal, oembed_payload,
                      tikwm_error_payload, tikwm_payload)

NORM = {"input": FAKE_ID, "video_id": FAKE_ID, "handle": None,
        "short_url": None, "kind": "bare",
        "canonical_url": f"https://www.tiktok.com/@i/video/{FAKE_ID}"}


class TikwmSlotTests(unittest.TestCase):
    def _patch(self, payload):
        return mock.patch.object(
            tool, "http_get",
            return_value=__import__("json").dumps(payload).encode())

    def test_success_with_relative_paths(self):
        with self._patch(tikwm_payload()):
            outcome, post = tool._fetch_tikwm(NORM["canonical_url"])
        self.assertEqual(outcome, "ok")
        self.assertEqual(post["video_id"], FAKE_ID)
        # relative play path gets absolutized onto the mirror host
        self.assertTrue(post["media_items"][0]["url"].startswith("https://"))
        # hd is preferred as primary
        self.assertEqual(post["media_items"][0]["url"], CDN_HD)
        self.assertEqual(post["media_items"][0]["watermarked_url"], CDN_WM)
        self.assertEqual(post["music"]["url"], CDN_MUSIC)
        self.assertTrue(post["music"]["original"])
        self.assertEqual(post["author"]["unique_id"], FAKE_HANDLE)
        self.assertEqual(post["stats"]["plays"], 1000)
        self.assertEqual(post["extraction_source"], "tikwm")

    def test_error_payload_is_unavailable(self):
        with self._patch(tikwm_error_payload()):
            outcome, _ = tool._fetch_tikwm(NORM["canonical_url"])
        self.assertEqual(outcome, "unavailable")

    def test_unknown_error_is_failed(self):
        with self._patch(tikwm_error_payload(msg="server busy")):
            outcome, _ = tool._fetch_tikwm(NORM["canonical_url"])
        self.assertEqual(outcome, "failed")

    def test_slideshow_images(self):
        data = tikwm_payload()["data"]
        data["images"] = [{"url": CDN_JPEG}, {"url": CDN_JPEG}]
        data.pop("play"), data.pop("hdplay"), data.pop("wmplay")
        with self._patch(tikwm_payload(data=data)):
            outcome, post = tool._fetch_tikwm(NORM["canonical_url"])
        self.assertEqual(outcome, "ok")
        self.assertEqual(len(post["media_items"]), 2)
        self.assertEqual(post["media_items"][0]["type"], "image")
        self.assertEqual(post["media_items"][0]["slide_index"], 1)

    def test_bad_id_shape_fails(self):
        data = tikwm_payload()["data"]
        data["id"] = "not-numeric"
        with self._patch(tikwm_payload(data=data)):
            outcome, _ = tool._fetch_tikwm(NORM["canonical_url"])
        self.assertEqual(outcome, "failed")


class EmbedSlotTests(unittest.TestCase):
    def test_universal_blob(self):
        with mock.patch.object(tool, "http_get",
                               return_value=embed_html_universal().encode()):
            outcome, post = tool._fetch_embed(FAKE_ID)
        self.assertEqual(outcome, "ok")
        self.assertEqual(post["video_id"], FAKE_ID)
        self.assertEqual(post["media_items"][0]["url"], CDN_MP4)
        self.assertEqual(post["media_items"][0]["watermarked_url"], CDN_WM)
        self.assertEqual(post["author"]["unique_id"], FAKE_HANDLE)
        self.assertEqual(post["stats"]["likes"], 90)
        self.assertEqual(post["extraction_source"], "embed_v2")

    def test_shell_is_failed(self):
        with mock.patch.object(tool, "http_get",
                               return_value=embed_html_shell().encode()):
            outcome, _ = tool._fetch_embed(FAKE_ID)
        self.assertEqual(outcome, "failed")


class TiklydownSlotTests(unittest.TestCase):
    def test_success_shape(self):
        import json
        payload = {"code": 0, "data": {
            "id": FAKE_ID, "title": "synthetic",
            "video": {"noWatermark": CDN_MP4, "watermark": CDN_WM,
                      "hd": CDN_HD, "cover": CDN_JPEG},
            "music": {"play_url": CDN_MUSIC, "title": "s"},
            "author": {"unique_id": FAKE_HANDLE},
            "stats": {"playCount": "500"}}}
        with mock.patch.object(
                tool, "http_get", return_value=json.dumps(payload).encode()):
            outcome, post = tool._fetch_tiklydown("https://x/" + FAKE_ID)
        self.assertEqual(outcome, "ok")
        self.assertEqual(post["media_items"][0]["url"], CDN_MP4)
        self.assertEqual(post["extraction_source"], "tiklydown")


class OembedSlotTests(unittest.TestCase):
    def test_metadata_only(self):
        import json
        with mock.patch.object(
                tool, "http_get",
                return_value=json.dumps(oembed_payload()).encode()):
            outcome, post = tool._fetch_oembed(NORM["canonical_url"])
        self.assertEqual(outcome, "ok")
        self.assertIsNone(post["media_items"][0]["url"])  # no bytes, ever
        self.assertEqual(post["title"], "synthetic oembed title")
        self.assertEqual(post["video_id"], FAKE_ID)  # recovered from html
        self.assertEqual(post["extraction_source"], "oembed")


class DecodeOrchestratorTests(unittest.TestCase):
    def test_slots_recorded_in_trace(self):
        calls = []

        def fake_tikwm(url):
            calls.append("tikwm")
            return "failed", None

        def fake_embed(vid):
            calls.append("embed_v2")
            return "ok", {"video_id": vid, "canonical_url": None,
                          "media_items": [], "author": {}, "music": {},
                          "stats": {}, "extraction_source": "embed_v2"}

        with mock.patch.object(tool, "DECODE_SLOT_FNS", [
                ("tikwm", fake_tikwm), ("embed_v2", fake_embed)]), \
             mock.patch.object(tool.time, "sleep"):
            post, trace = tool.decode_video(NORM)
        self.assertEqual(calls, ["tikwm", "embed_v2"])
        self.assertEqual([t["outcome"] for t in trace], ["failed", "ok"])
        self.assertEqual(post["extraction_source"], "embed_v2")

    def test_all_slots_fail_sets_error(self):
        with mock.patch.object(tool, "DECODE_SLOT_FNS", [
                ("a", lambda u: ("failed", None))]), \
             mock.patch.object(tool.time, "sleep"):
            tool.ERRORS.clear()
            post, trace = tool.decode_video(NORM)
            self.assertIsNone(post)
            self.assertEqual(tool.ERRORS[-1]["code"], tool.E_DECODE_FAILED)

    def test_slot_crash_does_not_kill_run(self):
        def boom(url):
            raise RuntimeError("synthetic crash")

        def ok_slot(url):
            return "ok", {"video_id": FAKE_ID, "canonical_url": None,
                          "media_items": [], "author": {}, "music": {},
                          "stats": {}, "extraction_source": "x"}

        with mock.patch.object(tool, "DECODE_SLOT_FNS", [
                ("boom", boom), ("ok_slot", ok_slot)]), \
             mock.patch.object(tool.time, "sleep"):
            post, trace = tool.decode_video(NORM)
        self.assertIsNotNone(post)
        self.assertIn("crashed", trace[0]["outcome"])


if __name__ == "__main__":
    unittest.main()
