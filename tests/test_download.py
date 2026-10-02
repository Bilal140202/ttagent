"""Delivery tier: allowlist, magic-byte verification, atomic writes."""
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

from _loader import tool
from fixtures import (CDN_JPEG, CDN_MP4, HTML_HEAD, HTTP_URL, JPEG_HEAD,
                      MP3_HEAD, MP4_HEAD, OUTSIDE_URL)


class MagicKindTests(unittest.TestCase):
    def test_known_magics(self):
        self.assertEqual(tool._magic_kind(JPEG_HEAD), "jpeg")
        self.assertEqual(tool._magic_kind(MP4_HEAD), "mp4")
        self.assertEqual(tool._magic_kind(MP3_HEAD), "mp3")
        self.assertEqual(tool._magic_kind(b"\xff\xfb\x90\x00"), "mp3")
        self.assertEqual(tool._magic_kind(b"GIF89a"), "gif")
        self.assertEqual(tool._magic_kind(b"RIFF\x00\x00\x00\x00WEBP"), "webp")
        self.assertEqual(tool._magic_kind(b"\x89PNG\r\n\x1a\n" + b"\x00" * 8),
                         "png")

    def test_unknown_is_none(self):
        self.assertIsNone(tool._magic_kind(HTML_HEAD))
        self.assertIsNone(tool._magic_kind(b""))


class AllowlistTests(unittest.TestCase):
    def test_cdn_hosts_allowed(self):
        self.assertTrue(tool._media_url_allowed(CDN_MP4))
        self.assertTrue(tool._media_url_allowed(CDN_JPEG))
        self.assertTrue(tool._media_url_allowed(
            "https://www.tikwm.com/video/media/play/x.mp4"))
        self.assertTrue(tool._media_url_allowed(
            "https://v16-webapp.tiktok.com/a.mp4"))
        self.assertTrue(tool._media_url_allowed(
            "https://ttwvideo.akamaized.net/a.mp4"))
        self.assertTrue(tool._media_url_allowed(
            "https://sf16-ies-music.tiktokcdn-us.com/a.mp3"))

    def test_non_cdn_rejected(self):
        self.assertFalse(tool._media_url_allowed(OUTSIDE_URL))
        self.assertFalse(tool._media_url_allowed(HTTP_URL))  # plain http
        self.assertFalse(tool._media_url_allowed(
            "https://tiktokcdn.com.evil.io/a.mp4"))
        self.assertFalse(tool._media_url_allowed("not a url"))


class DownloadTests(unittest.TestCase):
    def _run(self, payload, dest, headers=None, tries=1):
        state = {"consumed": False}
        resp = mock.MagicMock()

        def _read(n):
            if state["consumed"]:
                return b""
            state["consumed"] = True
            return payload

        resp.read = _read
        resp.headers = headers or {}
        cm = mock.MagicMock()
        cm.__enter__ = mock.Mock(return_value=resp)
        cm.__exit__ = mock.Mock(return_value=False)
        with mock.patch.object(tool.urllib.request, "urlopen",
                               return_value=cm):
            return tool.download(CDN_MP4, dest, tries=tries)

    def test_honest_failure_on_html_payload(self):
        tool.ERRORS.clear()
        with tempfile.TemporaryDirectory() as td:
            dest = Path(td) / "x.mp4"
            ok = self._run(HTML_HEAD + b"x" * 64, dest)
            self.assertFalse(ok)
            self.assertFalse(dest.exists())
            self.assertFalse(dest.with_suffix(".mp4.part").exists())
            self.assertEqual(tool.ERRORS[-1]["code"], tool.E_DOWNLOAD_FAILED)

    def test_success_writes_and_renames(self):
        with tempfile.TemporaryDirectory() as td:
            dest = Path(td) / "ok.mp4"
            ok = self._run(MP4_HEAD + b"y" * 100, dest)
            self.assertTrue(ok)
            self.assertTrue(dest.exists())
            self.assertEqual(dest.read_bytes()[4:8], b"ftyp")

    def test_content_length_mismatch_retries_then_fails(self):
        with tempfile.TemporaryDirectory() as td:
            dest = Path(td) / "bad.mp4"
            ok = self._run(MP4_HEAD, dest, headers={"Content-Length": "999"})
            self.assertFalse(ok)
            self.assertFalse(dest.exists())

    def test_zero_bytes_fails(self):
        with tempfile.TemporaryDirectory() as td:
            dest = Path(td) / "empty.mp4"
            ok = self._run(b"", dest)
            self.assertFalse(ok)

    def test_allowlist_rejection_short_circuits(self):
        tool.ERRORS.clear()
        with tempfile.TemporaryDirectory() as td:
            dest = Path(td) / "x.mp4"
            ok = tool.download(OUTSIDE_URL, dest, tries=3)
            self.assertFalse(ok)
            self.assertFalse(dest.exists())

    def test_http_404_no_retry(self):
        tool.ERRORS.clear()
        err = urllib.error.HTTPError(CDN_MP4, 404, "nf", {}, None)
        with mock.patch.object(tool.urllib.request, "urlopen",
                               side_effect=err) as urlopen:
            with tempfile.TemporaryDirectory() as td:
                dest = Path(td) / "x.mp4"
                ok = tool.download(CDN_MP4, dest, tries=3)
                self.assertFalse(ok)
                self.assertEqual(urlopen.call_count, 1)


if __name__ == "__main__":
    unittest.main()
