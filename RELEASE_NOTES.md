# Release Notes

## v1.0.0 — 2026-10-02

Initial public release. Sibling to `xthread-agent` (X/Twitter threads),
`ytagent` (YouTube), and `igagent` (Instagram) — same doctrine, new
platform.

### The pipeline

| Tier | Slots | Notes |
|---|---|---|
| Discovery | normalize / short-link expand | @user/video, /photo, vm./vt./t/ links (one hop, dead-link verdict), bare 15–20 digit ids |
| Decode | `tikwm` → `embed_v2` → `tiklydown` → `oembed` | provenance trace on every run; honest nulls; metadata-only floor |
| Deliver | CDN fetcher | TikTok CDN + mirror allowlist, magic-byte verification (MP4/MP3/JPEG/PNG), atomic writes |

### Highlights

* Single-file stdlib-only tool (`ttagent.py`), Python 3.9+, zero pip
  dependencies, byte-identical PyPI package (`pip install ttagent`).
* **The soundtrack is media**: music harvested by default with full
  identity in the envelope (`--no-music` to skip).
* Slideshow ("photo mode") support: every exposed still frame saved and
  recorded.
* `video_manifest.json` envelope (schema_version 1.0) with draft-07
  schema; `--json` stdout contract; exit codes 0/1/2.
* MCP stdio server (`mcp_server.py`): `extract_video`, `lookup_video`,
  `read_manifest`, `get_schema`.
* 66 offline tests, ~1s, zero network; CI matrix 3.9–3.13.
* `demo.py` consumes the tool exactly as an external agent would.

### Verified from a datacenter vantage point (2026-10-02)

* Live harvest: video (2.0 MB, `ftyp isom` verified) + soundtrack
  (ID3-verified) + cover (JPEG-verified) from a public video URL in
  ~3 s via the `tikwm` slot.
* Live dead video: `status=empty`, `E_VIDEO_UNAVAILABLE`, exit 1.

### Known limits (documented, honest)

* Region walls: what a mirror in one region sees is the truth this tool
  reports; nothing else.
* Mirrors are borrowed ground — the slot architecture and the endpoint
  matrix are the absorption mechanism.
* Livestreams and private accounts are out of scope by constraint 1.
