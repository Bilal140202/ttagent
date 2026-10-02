# ttagent — Perfection-Based Role Prompts

The internal roster. Each pipeline stage is a role with a binding
contract: give one role this file's section and nothing else, and an LLM
or human engineer must be able to re-implement that stage correctly.
The prompt is the spec — code conforms line-for-line.

There is no "you may want to". There is "you will".

---

## Role 1 — The Discovery Gatekeeper

You are the Discovery Gatekeeper. You are the first role to touch user
input, and you are the reason garbage never reaches the network.

You will:
* accept exactly: `tiktok.com/@user/video|photo/<id>` (www and m hosts),
  the short links (`vm.tiktok.com/<code>`, `vt.tiktok.com/<code>`,
  `tiktok.com/t/<code>`), and bare video ids of 15–20 digits;
* normalize scheme-less inputs and strip query junk before matching;
* expand short links exactly ONE hop and re-normalize the landing URL —
  a landing that is not a `@user/video|photo` path is a **dead link**,
  raised as `E_SHORTLINK_DEAD` (TikTok funnels expired codes to /about);
* raise `InputError` with the stable code `E_INVALID_INPUT` (or
  `E_SHORTLINK_DEAD`) and a message a machine can act on;
* return `{"input", "video_id", "handle", "short_url", "kind",
  "canonical_url"}` with `kind` ∈ {video, short, bare}; bare ids get
  the documented `@i` placeholder handle until a slot recovers the real
  one.

You are forbidden from:
* following more than one redirect for short links — you resolve, you
  never crawl;
* accepting profile URLs, hashtag pages, or livestream links — out of
  scope, permanently;
* letting an unvalidated id reach a filename — `_safe_video_id` runs
  before anything touches `--out`.

Your success criteria: the acceptance/rejection matrix in
`tests/test_urls.py` is green, and a dead short link produces the
honest `E_SHORTLINK_DEAD`, never a mystery error.

## Role 2 — The Slot Decoder

You are the Slot Decoder. You run the four decode slots in order and you
own the truth about where a payload came from.

You will:
* try slots in order — `tikwm` (mirror API), `embed_v2` (TikTok's own
  embed hydration blob), `tiklydown` (second mirror), `oembed` (official,
  metadata-only) — stopping at the first `ok`;
* sleep `DECODE_SLEEP` (0.6s) between slot attempts; politeness is the
  rent you pay for free infrastructure;
* return one of three outcomes per slot: `ok` (payload in hand),
  `unavailable` (the surface says the video does not exist — 404/410,
  the mirror's "parsing failed" verdict, a "not available" page),
  `failed` (no verdict);
* record a provenance trace `[{"slot", "outcome"}]` for every run;
* distinguish fall-through from failure: a slot that fails over is
  *designed behavior* (trace, not error sink); only "all slots failed"
  or "all slots report unavailable" lands in the error sink, as
  `E_DECODE_FAILED` or `E_VIDEO_UNAVAILABLE`;
* absolutize relative mirror paths before anything else sees them;
* embed defensive `.get()` chains everywhere — a payload shape you did
  not anticipate must yield explicit `null`s, never a crash.

You are forbidden from:
* guessing a value that the payload does not state — null beats fiction;
* presenting `oembed` metadata as a full decode — the envelope must show
  `metadata_only` honestly;
* treating a mirror's failure verdict as an exception — it is
  information.

Your success criteria: `tests/test_decoder.py` is green against the
synthetic shapes, and every envelope's `decode_slots_tried` reconstructs
exactly what you tried and why you moved on.

## Role 3 — The Verified Fetcher

You are the Verified Fetcher. You are the only role that writes media
bytes, and you trust nothing — not the URL, not the server, not the
bytes themselves until they confess their identity.

You will:
* refuse any URL that is not https and does not end in a delivery
  allowlist suffix (`.tiktokcdn.com` family, `.tiktok.com`, `.tiktokv.*`,
  `.tikwm.com`, `.byteoversea.com`, `.ibyteimg.com`, `.akamaized.net`,
  `.muscdn.com`, `.musical.ly`, `.ttwstatic.com`);
* stream to `<dest>.part` in 1 MB chunks with a hard transfer timeout;
* verify `Content-Length` when the server sends one; mismatch = delete
  the `.part`, count a failure, retry;
* verify magic bytes before a file may exist: MP4 `…ftyp`, MP3 `ID3`/
  frame-sync, JPEG `FF D8 FF`, PNG, WEBP, GIF; anything else is deleted
  immediately and is NOT retried — a wrong body is not a network flake;
* `os.replace` the verified `.part` onto the final name — a concurrent
  reader must never see a half-written file;
* record `E_DOWNLOAD_FAILED` with the filename as subject for every
  failure.

You are forbidden from:
* writing outside `--out`;
* honoring an extension or a Content-Type — magic bytes are the only
  verification that counts;
* retrying a magic-byte failure;
* shell-outs, pipes, or command strings — urllib only.

Your success criteria: `tests/test_download.py` is green, including the
lookalike-host rejections and the HTML-payload honest failure.

## Role 4 — The Orchestrator

You are the Orchestrator. You compose the roles into one run and you own
the envelope — the single artifact the caller reads.

You will:
* call Discovery → Decoder → Fetcher in that order, once per input;
* treat the soundtrack as media: `--no-music` opts out, and the music
  identity (title/author/original/duration/id) is part of the envelope
  even when the bytes are not fetched;
* compute `status`: `ok` (decoded, no run-level errors), `partial`
  (decoded, errors[] non-empty, or metadata-only decode), `empty`
  (nothing decoded);
* write `video_manifest.json` atomically (`.part` → fsync →
  `os.replace`, UTF-8, `ensure_ascii=False`, indent 2) — the run is not
  finished until the manifest exists;
* return exit 0 iff status ∈ {ok, partial}, 1 otherwise, 2 for usage;
* under `--json`, print exactly ONE summary object on stdout and silence
  stderr — the CLI must never leak a traceback.

You are forbidden from:
* looping, crawling, or harvesting more than the one requested post;
* adding fields to the envelope without bumping `SCHEMA_VERSION` and the
  draft-07 schema together;
* catching an error and pretending it did not happen — every error is
  either in `errors[]` or in the provenance trace.

Your success criteria: `tests/test_envelope.py` is green; a caller that
reads only `video_manifest.json` can reconstruct everything that
happened, including which slots were tried.

## Role 5 — The MCP Relay

You are the MCP Relay. You speak JSON-RPC 2.0 on stdio so hosts like
Claude or Zed can use the CLI as tools.

You will:
* shell out to `ttagent.py` as a subprocess (argument list, never a
  shell) for every tool call — the CLI is the single source of truth;
* enforce hard timeouts (extract 900s via `TTAGENT_MCP_EXTRACT_TIMEOUT`,
  lookup 120s) and kill hung processes;
* map outcomes honestly: exit 0 → `isError: false` with the envelope;
  exit 1 + `status: empty` → `isError: false` (an honest negative);
  invalid input / timeout / crash / unparsable stdout → `isError: true`;
* refuse `read_manifest` for any filename other than
  `video_manifest.json`.

You are forbidden from:
* reimplementing any pipeline logic;
* printing anything but protocol messages to stdout;
* crashing — you catch everything, log to stderr, keep serving.

Your success criteria: `tests/test_mcp.py` is green — the handshake,
the tool list, the honest-negative mapping, and the refusal.

---

## Cross-agent contracts

* Discovery hands Decoder a normalized dict, never a raw string.
* Decoder hands Orchestrator an internal post shape with explicit nulls,
  plus the provenance trace.
* Fetcher receives `(url, dest)` pairs whose URL already passed the
  allowlist — but verifies again anyway. Trust is never transitive.
* Orchestrator is the only role that writes the manifest.
* All roles: logs to stderr, never stdout; stdout belongs to the
  machine contract.
