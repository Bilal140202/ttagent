# ttagent

**An agentic TikTok video & soundtrack harvester for AI agents — no login, no API keys, no browser. MCP wrapper included.**

![Python](https://img.shields.io/badge/python-3.9%2B-blue) ![Tests](https://img.shields.io/badge/tests-66%20offline-brightgreen) ![License](https://img.shields.io/badge/license-MIT-green) ![LLM](https://img.shields.io/badge/LLM%20at%20runtime-none-critical)

`ttagent` is the TikTok sibling of [`xthread-agent`](https://github.com/Bilal140202/xthread-agent) (X/Twitter threads), [`ytagent`](https://github.com/Bilal140202/ytagent) (YouTube), and [`igagent`](https://github.com/Bilal140202/igagent) (Instagram). Same doctrine: a deterministic, slot-based, stdlib-only state machine that a cloud agent can call with one URL and read back one JSON contract.

```bash
python ttagent.py "https://www.tiktok.com/@user/video/<ID>"
# → verified video + soundtrack + covers on disk + video_manifest.json
```

---

## Why this exists

TikTok is the friendliest of the big platforms to sessionless machines — a whole ecosystem of public mirror workers and open CDN paths grew around it — but it is also the most volatile: mirror domains rotate, regions differ, and the official surface offers metadata only. ttagent is built for exactly that landscape: **compose many legitimate access paths, verify every byte, and tell the truth about what worked.**

What it gives you:

1. **One input, one artifact.** A video URL (or short link, or bare id) in; the video, its soundtrack, its covers, and `video_manifest.json` out.
2. **The soundtrack is media.** A TikTok post is a video *plus its music* — the track is harvested alongside the video (opt-out with `--no-music`), with its identity (title, author, original?, duration, id) in the envelope.
3. **Honest negatives.** A deleted video is not an exception — it is `status: "empty"` with structured errors and a slot-by-slot provenance trace.
4. **Slots, not brands.** The four decode surfaces are interchangeable implementations of one contract. When a mirror dies, you replace the slot — the pipeline never restructures.
5. **Verified delivery.** Files exist only after passing the CDN allowlist, a `Content-Length` check, and a magic-byte identity check (MP4 `ftyp`, MP3 `ID3`/frame-sync, JPEG, PNG). A tool that reports a file is vouching for its bytes.
6. **Politeness as a hard constraint.** Bounded retries, 0.6 s decode sleeps, response caps, one post per invocation. The public surfaces this tool depends on are free; restraint is the rent.

## Architecture

```
            ┌──────────────────────────────────────────────────────┐
            │                    DISCOVERY                        │
            │  normalize @user/video|photo URLs · vm./vt./t/      │
            │  short links (one hop, dead-link verdict) · bare    │
            │  15–20 digit video ids                              │
            └───────────────────────────┬──────────────────────────┘
                                        ▼
            ┌──────────────────────────────────────────────────────┐
            │                     DECODE  (slots)                 │
            │  1. tikwm      — mirror worker API (richest: HD,    │
            │     watermark variants, music, stats, slideshows)   │
            │  2. embed_v2   — TikTok's own embed hydration blob  │
            │  3. tiklydown  — second mirror (documented slot)    │
            │  4. oembed     — official, metadata-only last resort│
            │  provenance trace [{"slot","outcome"}] on every run │
            └───────────────────────────┬──────────────────────────┘
                                        ▼
            ┌──────────────────────────────────────────────────────┐
            │                     DELIVER                        │
            │  https + tiktok CDN families / tikwm mirror /       │
            │  byteoversea / akamaized / muscdn only              │
            │  stream → .part → Content-Length ✓ → magic bytes ✓  │
            │  → os.replace (atomic) → files + video_manifest.json│
            └──────────────────────────────────────────────────────┘
```

Each tier fails closed: a slot that finds nothing hands control to the next slot and the attempt is recorded; only "everything failed" becomes a run-level error.

## Quickstart

```bash
# full harvest (decode + verified downloads of video, music, covers)
python ttagent.py "https://www.tiktok.com/@user/video/<ID>" --out ./tiktok_media

# metadata only
python ttagent.py "<ID>" --no-download

# video only, skip the soundtrack
python ttagent.py "<url>" --no-music

# the machine contract: exactly one JSON object on stdout
python ttagent.py "<input>" --json --quiet
```

### For AI agents

The three-command contract:

| command | returns | exit |
|---|---|---|
| `ttagent.py "<input>" --json --quiet` | summary JSON on stdout, full envelope at `manifest_path` | 0 ok/partial · 1 empty · 2 invalid |
| `ttagent.py "<input>" --no-download --json --quiet` | same, no files on disk | same |
| `ttagent.py --version` | `ttagent 1.0.0` | 0 |

## CLI reference

```
ttagent.py <input> [--out DIR] [--no-download] [--no-music] [--json] [--quiet] [--version]

<input>         tiktok.com/@user/video/<id> · /photo/<id> · vm./vt. short
                links · tiktok.com/t/<code> · bare 15–20 digit id
--out DIR       output directory (default: tiktok_media)
--no-download   decode only; manifest still written
--no-music      skip the soundtrack download
--json          one JSON summary object on stdout (stderr silenced)
--quiet         silence human logs on stderr
```

### JSON output (for AI agents)

```json
{
  "ok": true,
  "status": "ok",
  "video_id": "6718335390845095173",
  "canonical_url": "https://www.tiktok.com/@scout2015/video/6718335390845095173",
  "extraction_source": "tikwm",
  "author": "scout2015",
  "video_file": "6718335390845095173_video.mp4",
  "music_file": "6718335390845095173_music.mp3",
  "images": 0,
  "downloaded": 3,
  "failed_downloads": 0,
  "out_dir": "tiktok_media",
  "manifest_path": "tiktok_media/video_manifest.json",
  "errors": [],
  "duration_sec": 3.3
}
```

The full envelope (`video_manifest.json`) adds the video object: title,
region, `created_at`, author, the soundtrack identity, `stats`
(plays/likes/comments/shares/collects/downloads), `media.video` with
`url / hd_url / watermarked_url` and per-variant download state,
`media.images[]` for slideshows, `errors[]` with stable codes, and
`metadata.decode_slots_tried` — the provenance trace. The draft-07 schema
is bundled at `schema/video-result.schema.json`.

## For MCP hosts

`python mcp_server.py` speaks newline-delimited JSON-RPC 2.0 on stdio —
stdlib only, no `mcp` package. Register it in Claude Desktop / Zed:

| tool | what it does |
|---|---|
| `extract_video` | full harvest → verified video/music/covers + envelope |
| `lookup_video` | metadata-only decode (no downloads) |
| `read_manifest` | return an existing `video_manifest.json` (refuses anything else) |
| `get_schema` | the draft-07 envelope schema |

Error policy: an honest empty result is **not** an MCP error; a bad tool
argument, timeout, or crash is.

## Documentation

| file | role |
|---|---|
| [`agent.md`](agent.md) | the operating manual for AI agents — read this file and nothing else |
| [`agents.md`](agents.md) | perfection-based role prompts for the five pipeline roles |
| [`PROJECT_CONTEXT.md`](PROJECT_CONTEXT.md) | maintainer manifesto: why, load-bearing walls, fragile parts, debts |
| [`docs/endpoint-matrix.md`](docs/endpoint-matrix.md) | living endpoint status table + maintenance protocol |
| [`schema/video-result.schema.json`](schema/video-result.schema.json) | the output contract, machine-checkable |
| [`RELEASE_NOTES.md`](RELEASE_NOTES.md) | version history |

## Constraints (non-negotiable)

1. **No login, no cookies, no OAuth, no browser.** Public content only; everything fails closed.
2. **No GUI, no interactive prompts.** 100% non-interactive CLI.
3. **No LLM at runtime.** Deterministic state machine — the "agent" is designed *for* AI agents, not made of one.
4. **stdlib only.** Single file, zero pip dependencies, Python 3.9+.
5. **Logs on stderr, data on stdout.** Always pipe-safe.
6. **Files stay under the output directory.** CDN allowlist, ID validation, atomic writes, magic-byte verification.

## Requirements

Python 3.9+ and outbound HTTPS. Nothing else — no pip, no ffmpeg, no
browser, no env vars, no config files.

## Installation

```bash
# as a tool (after PyPI publish)
pip install ttagent
ttagent "<url>" --json

# from source
git clone https://github.com/Bilal140202/ttagent.git
python ttagent/ttagent.py "<url>"
# or
python -m ttagent "<url>"
```

## Testing

```bash
python -m unittest discover -s tests -p "test_*.py"
# 66 tests, ~1s, zero network — synthetic fixtures only, never real IDs
```

## Verified behavior (as shipped)

| claim | evidence |
|---|---|
| `tikwm` slot decodes a live public video with HD + music + covers | live run: `status=ok`, video (2.0 MB, `ftyp`-verified), music (ID3-verified), cover (JPEG-verified), `downloaded: 3` |
| mirror-relative media paths are absolutized before download | offline tests |
| dead videos produce honest empties | live run: `status=empty`, `E_VIDEO_UNAVAILABLE`, exit 1 |
| magic-byte gate rejects HTML masquerading as media | offline tests |
| lookalike CDN hosts (`tiktokcdn.com.evil.io`) refused | offline tests |
| MCP handshake + 4-tool registry | offline stdio probe |

Re-verify against your own vantage point and update
`docs/endpoint-matrix.md` — that is the protocol.

## Limitations (the honest section)

* **Region walls are real.** A mirror worker in region A may not see a
  video visible in region B; the envelope reports what the doors showed,
  and nothing else.
* **Mirrors are borrowed ground.** If a mirror rate-limits or dies, the
  trace says so and the next slot takes over — but if all mirrors and
  the embed page are down, `oembed` metadata is the ceiling.
* **Slideshow posts** depend on the mirror exposing `images[]`; the
  official surface does not, and the envelope says which slot produced
  what.
* **Livestreams and private accounts** are out of scope — both require
  authentication, which violates constraint 1.

## Legal / ethics

ttagent accesses only publicly served documents over unauthenticated
HTTP(S), with politeness sleeps and hard caps, and it never circumvents
a paywall, a login, or a private post. Respect creators: videos, music
and captions remain the property of their authors; downstream use is
your responsibility. Do not use this tool at volumes that constitute
abuse.

## FAQ

**Why is there no login option?** Because the calling agent is a cloud
VM by definition — no session, no cookies. The whole design is "what
can a sessionless machine legitimately get?" — and the answer is
documented, versioned, and fail-closed.

**Why is the music download an MP3 even when TikTok serves M4A?** The
music URL decides: the file keeps the extension the CDN serves, and the
magic-byte check accepts both ID3 and raw AAC frame syncs. The manifest
records the real file name either way.

**A decode stopped working — is ttagent broken?** Check
`docs/endpoint-matrix.md` first. Surfaces flip; the matrix is the
impersonal record of flips, and slots are how they get absorbed.

**Does it work for livestreams or private videos?** No, by design —
both require authentication, which violates constraint 1.

## License

MIT — see [LICENSE](LICENSE).

## Acknowledgments

* [`xthread-agent`](https://github.com/Bilal140202/xthread-agent) — the architecture, the docs-as-contract system, the MCP wrapper, and the phrase "restraint is the rent".
* [`ytagent`](https://github.com/Bilal140202/ytagent) — "never trust a method's self-report", the verification doctrine this project merged into its delivery tier.
* [`igagent`](https://github.com/Bilal140202/igagent) — the Instagram sibling; the slot-failover provenance design was born there.
* The mirror-worker ecosystem — the doors that were already open.

## Links

* Repository: <https://github.com/Bilal140202/ttagent>
* Issues: <https://github.com/Bilal140202/ttagent/issues>
* Siblings: [`xthread-agent`](https://github.com/Bilal140202/xthread-agent) · [`ytagent`](https://github.com/Bilal140202/ytagent) · [`igagent`](https://github.com/Bilal140202/igagent)
