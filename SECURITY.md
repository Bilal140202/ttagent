# Security Policy

## Threat model (what ttagent defends against)

ttagent fetches attacker-influenceable content (public web pages, CDN
URLs) and writes files. The defenses, in order of importance:

1. **Delivery allowlist** — media downloads only from `https://` hosts
   ending in the configured suffix table (TikTok CDN families,
   `.tiktok.com`, the mirror worker, byteoversea, akamaized,
   muscdn/musical.ly). Everything else is refused before a socket opens.
   Lookalike hosts fail the suffix check.
2. **Filename hygiene** — shortcodes must match the strict alphabet and
   length bounds; media ids must be ≤ 25 digits. Nothing from a payload
   reaches a filename unvalidated.
3. **Magic-byte verification** — a body that does not identify as
   JPEG/PNG/WEBP/MP4/MP3/GIF is deleted. A hostile "image" that is a
   polyglot script will not pass `ftyp` / `ID3` / `FF D8 FF` checks untested.
4. **Atomic writes** — `.part` + `os.replace` within `--out`; readers
   never observe partial files; nothing is written outside the output
   directory.
5. **Response caps** — decode responses are capped (15 MB); downloads
   verify Content-Length; no unbounded reads.
6. **No shell, no eval** — urllib and argument-list subprocesses only
   (the MCP server shells out with lists, never strings).

## Out of scope

* Availability of upstream surfaces (embed pages, CDNs) — tracked in
  `docs/endpoint-matrix.md`, not treated as a vulnerability.
* The content of downloaded media when it *is* valid media — it is
  untrusted data by definition; handle it like any other download.

## Reporting

Open a private security advisory via GitHub ("Report a vulnerability")
rather than a public issue. Include the invocation, the input, and the
manifest/errors if applicable.
