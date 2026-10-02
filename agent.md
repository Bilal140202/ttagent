# ttagent — Operating Manual for AI Agents

**Read this file and nothing else.** Everything a machine needs to run
ttagent end-to-end is here: preconditions, invocations, the full output
contract, a decision tree for exit codes, and known limitations.

---

## 1. What ttagent is

ttagent harvests **one public TikTok post** (video or photo-mode
slideshow) per invocation and returns:

* the video (clean, HD-preferred), the **soundtrack**, and the covers —
  downloaded to disk and **verified by magic bytes**;
* for slideshows: every still frame the public surface exposes;
* `video_manifest.json` — a schema-versioned JSON envelope describing
  the post, its author, the music identity, stats, every media URL,
  every local file, every error, and the provenance of the decode slot
  that produced the result.

There is **no LLM at runtime**. ttagent is a deterministic state machine
designed to be *called by* AI agents, not to be one.

## 2. Preconditions

* Python 3.9+ (stdlib only — no pip installs, no ffmpeg, no browser).
* Outbound HTTPS. That is all.
* No login, no cookies, no API keys, no env vars (the only one, optional:
  `TTAGENT_MCP_EXTRACT_TIMEOUT`, used by the MCP wrapper).

## 3. Invocation (three modes)

```bash
# 1. Full harvest — decode + verified downloads (default out: ./tiktok_media)
python ttagent.py "https://www.tiktok.com/@user/video/<ID>"

# 2. Metadata only — no media files on disk
python ttagent.py "<ID>" --no-download

# 3. Machine contract — exactly one JSON object on stdout
python ttagent.py "<input>" --json --quiet
```

Accepted inputs: `tiktok.com/@user/video/<id>` and `/photo/<id>`,
`m.tiktok.com` variant, short links (`vm.tiktok.com/…`, `vt.tiktok.com/…`,
`tiktok.com/t/…` — expanded exactly one hop), and bare video ids
(15–20 digits). Flags: `--out DIR` · `--no-download` · `--no-music` ·
`--json` · `--quiet` · `--version`.

A TikTok post is a **video plus its soundtrack**. The soundtrack is
harvested by default; pass `--no-music` to skip it.

## 4. The output contract

`--json` stdout (summary) and `video_manifest.json` (full envelope) share
one schema: `schema/video-result.schema.json` (draft-07, `schema_version
"1.0"`). The envelope always carries every top-level key:

| key | meaning |
|---|---|
| `schema_version` | const `"1.0"` — bump = breaking contract change |
| `source` | `{tool, version, generated_at}` |
| `request` | `{input, video_id, canonical_url, options{download_media, download_music}}` |
| `status` | `ok` \| `partial` \| `empty` |
| `video` | the video object, or `null` when empty |
| `errors` | structured `{stage, code, message, subject}` list |
| `metadata` | `duration_sec`, `decode_slots_tried` (provenance), `counts` |

`video.media.video` carries `url / hd_url / watermarked_url` and the
download state of each; `video.media.music` carries the soundtrack
identity (`title`, `author`, `original`, `duration`, `music_id`) plus its
`file`; `video.media.images[]` carries slideshow frames;
`video.stats` carries plays/likes/comments/shares/collects/downloads —
**explicitly nullable** when a slot does not expose them, never a guess.

`video.extraction_source` ∈ `tikwm` / `embed_v2` / `tiklydown` /
`oembed` — always recorded. A decode via `oembed` means metadata-only:
the video entry reads `downloadable: false, reason: "metadata_only"`.

## 5. Decision tree

```
exit 0
  ├─ status "ok"      → everything materialized; errors[] empty
  └─ status "partial" → decoded but something missing: read the media
                        entry's reason ("metadata_only",
                        "no_video_url_exposed", "download_failed")
exit 1
  ├─ status "empty"   → honest negative: video unavailable or
  │                     undecodable (or a dead short link). errors[]
  │                     says which. Do NOT retry blindly.
  └─ other            → infra-level failure; read errors[].code
exit 2
  └─ invalid_input    → your input, not the network. Fix the URL/id.
        codes: E_INVALID_INPUT, E_SHORTLINK_DEAD
```

Decoder codes: `E_VIDEO_UNAVAILABLE` (all slots agree the video is
gone/private), `E_DECODE_FAILED` (all slots failed without a verdict).
Fetcher: `E_DOWNLOAD_FAILED`. Orchestrator: `E_MANIFEST_WRITE_FAILED`.

## 6. Copy-paste tasks

```bash
# The soundtrack only
python ttagent.py "<url>" --json --quiet && ls tiktok_media/*_music.mp3

# Save HD video + skip music
python ttagent.py "<url>" --out ./clips --no-music

# Pipe-safe batch (one at a time — politeness is a hard constraint)
while read -r u; do python ttagent.py "$u" --json --quiet >> results.ndjson; done < urls.txt

# Re-read a previous run's manifest
python -c "import json; print(json.load(open('tiktok_media/video_manifest.json'))['video']['stats'])"
```

## 7. Known limitations (honest, not fixable by retry)

* **Region-locked videos** may be invisible to a mirror worker from
  another region — the envelope says `empty` with the slot trace, which
  is the honest report of what the doors showed.
* **Mirror workers are borrowed ground.** `tikwm` is a third-party
  mirror; if it rate-limits or dies, the trace records it and the next
  slot takes over (the embed page, a second mirror, then oembed).
* **oembed is metadata-only by design** — the official endpoint never
  carries video bytes, so a run that lands there is `partial`.
* **One post per invocation.** Batch = loop with the tool's own
  politeness sleeps doing their work.

## 8. Hard constraints (do not ask the tool to break these)

1. No login/cookies/OAuth/browser — public content only, fails closed.
2. No GUI, no prompts.
3. No LLM at runtime.
4. stdlib only, single file, Python 3.9+.
5. Logs → stderr; data → stdout. Under `--json`, stdout is exactly one
   JSON object.
6. Files stay under `--out`. Media URLs must be https + a host suffix on
   the delivery allowlist (tiktok CDN families, tikwm mirror, byteoversea,
   akamaized ttwvideo, muscdn/musical.ly music) or they are refused. IDs
   are validated before they touch the filesystem. Downloads are atomic
   (`.part` → `os.replace`) and magic-byte verified (MP4/MP3/JPEG/PNG/
   WEBP/GIF).
