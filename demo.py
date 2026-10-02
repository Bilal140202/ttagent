#!/usr/bin/env python3
"""
demo.py — consume ttagent exactly the way an external AI agent would
=====================================================================
Runs the CLI as a subprocess (`--json --quiet`, the machine contract),
then pretty-prints the manifest it points to.  No imports from the tool
itself — this file is proof that the subprocess+JSON contract is enough.

Usage:
    python demo.py <tiktok_url_or_id> [--out demo_output]
                   [--skip-download] [--raw]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TOOL = ROOT / "ttagent.py"


def main() -> int:
    ap = argparse.ArgumentParser(description="ttagent end-user demo")
    ap.add_argument("url", help="TikTok video/photo URL or video id")
    ap.add_argument("--out", default="demo_output")
    ap.add_argument("--skip-download", action="store_true")
    ap.add_argument("--raw", action="store_true",
                    help="dump the raw envelope JSON and exit")
    args = ap.parse_args()

    cmd = [sys.executable, str(TOOL), args.url, "--out", args.out,
           "--json", "--quiet"]
    if args.skip_download:
        cmd.append("--no-download")

    print(f"$ {' '.join(cmd)}", file=sys.stderr)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    try:
        summary = json.loads(proc.stdout)
    except ValueError:
        print("demo failed: CLI produced no parsable stdout. "
              f"stderr tail:\n{(proc.stderr or '')[-800:]}", file=sys.stderr)
        return 1

    if not summary.get("ok"):
        print(json.dumps(summary, indent=2))
        return proc.returncode or 1

    manifest = Path(summary["manifest_path"])
    envelope = json.loads(manifest.read_text(encoding="utf-8"))
    if args.raw:
        print(json.dumps(envelope, indent=2, ensure_ascii=False))
        return 0

    video = envelope.get("video") or {}
    meta = envelope.get("metadata") or {}
    author = video.get("author") or {}
    media = video.get("media") or {}
    vm = media.get("video") or {}
    music = media.get("music") or {}
    stats = video.get("stats") or {}

    print()
    bar = "─" * 62
    print(bar)
    status = envelope.get("status")
    icon = {"ok": "✓", "partial": "~", "empty": "✗"}.get(status, "?")
    print(f" {icon} ttagent run: {status.upper()}"
          f"   (decoded via: {video.get('extraction_source')})")
    print(bar)
    print(f"  video     : {video.get('url')}")
    print(f"  video_id  : {video.get('video_id')}")
    print(f"  author    : @{author.get('unique_id') or '?'}"
          f"  ({author.get('nickname')})")
    title = video.get("title")
    if title:
        title = title if len(title) <= 80 else title[:77] + "..."
        print(f"  title     : {title}")
    print(f"  created   : {video.get('created_at') or 'not exposed'}"
          f"   region: {video.get('region') or '?'}"
          f"   duration: {video.get('duration') or '?'}s")
    stats_line = ", ".join(
        f"{k}={v:,}" if isinstance(v, int) else f"{k}={v}"
        for k, v in stats.items() if v is not None)
    if stats_line:
        print(f"  stats     : {stats_line}")
    print(bar)
    state = ("saved" if vm.get("downloaded")
             else (f"not saved: {vm.get('reason')}" if vm.get("reason")
                   else "url only"))
    print(f"  [vid ] {vm.get('file') or '(no file)'}"
          f"{'  + ' + vm.get('hd_file') if vm.get('hd_file') else ''} — {state}")
    mstate = ("saved" if music.get("downloaded")
              else (f"not saved: {music.get('reason')}"
                    if music.get("reason") else "url only"))
    print(f"  [audio] {music.get('file') or '(no file)'}"
          f"  — {music.get('title') or '?'} — {mstate}")
    for img in media.get("images", []):
        ist = "saved" if img.get("downloaded") else \
              (f"not saved: {img.get('reason')}" if img.get("reason")
               else "url only")
        print(f"  [slide] {img.get('file') or '(no file)'} — {ist}")
    counts = (meta.get("counts") or {})
    print(bar)
    print(f"  totals    : {counts.get('videos', 0)} video, "
          f"{counts.get('audio_tracks', 0)} soundtrack, "
          f"{counts.get('images', 0)} slide(s), "
          f"{counts.get('downloaded_media', 0)} downloaded, "
          f"{counts.get('failed_downloads', 0)} failed "
          f"in {meta.get('duration_sec', 0):.1f}s")
    slots = ", ".join(f"{s.get('slot')}={s.get('outcome')}"
                      for s in meta.get("decode_slots_tried", []))
    print(f"  slots     : {slots}")
    print(f"  manifest  : {manifest}")
    print(bar)
    return 0


if __name__ == "__main__":
    sys.exit(main())
