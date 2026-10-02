# PROJECT_CONTEXT.md — Read Me Before Touching Anything

This is the maintainer manifesto, in the tradition of the sibling
projects. It explains why the code is the way it is, which walls are
load-bearing, which parts are fragile, and what is deliberately left
undone. Code explains *how*; this explains *why*.

## 1. Why this exists

The sibling pair proved the same thesis on two platforms: a
sessionless machine can still get real work done if you build on the
public surfaces that platforms serve for their own reasons. TikTok is
the platform where the "ecosystem of mirror workers" thesis is most
visible — an entire community-run delivery layer exists in the open —
and also where the volatility thesis is most visible: mirrors rotate,
regions differ, and the official surface gives metadata but not bytes.
ttagent composes both realities: four decode slots ordered
richest-first, ending at the official `oembed` as the honest
metadata-only floor.

## 2. Load-bearing walls (do not casually reverse)

* **Single file, stdlib only.** `ttagent.py` is the product; the package
  directory is a byte-identical synced copy (drift fails CI). The
  deployment story — copy one file into a bare sandbox — is a feature.
* **Slots, not brands.** `tikwm` / `embed_v2` / `tiklydown` / `oembed`
  are interchangeable implementations of one contract. When one dies,
  replace the slot function in `DECODE_SLOT_FNS`; do not restructure.
* **Fall-through is not failure.** A slot that yields `failed` hands
  control to the next slot and shows up in the provenance trace — not
  in `errors[]`. Run-level errors are reserved for verdicts ("all slots
  failed" / "all slots report unavailable") and fetcher/orchestrator
  failures. This distinction is what keeps `status` meaningful.
* **The delivery allowlist is the security model.** https-only plus a
  fixed host-suffix table covering the TikTok CDN families, the mirror
  worker, and the music CDNs. Everything else is refused before a
  socket opens. Together with magic-byte verification and atomic
  writes, this is the whole trust story.
* **The soundtrack is media.** A TikTok post is video + music. The
  envelope's `media.music` carries the identity even when the bytes are
  not fetched, and `--no-music` is the only way to skip the download.
  Eroding this distinction would make the tool a plain "video
  downloader" and lose the platform's actual shape.
* **Explicit nulls.** A field the slot did not expose is `null`, never
  a guess, never an empty string, never a fabricated default.

## 3. Fragile parts (ranked by fragility)

1. **The mirror worker.** `tikwm` is the primary slot and a third-party
   service: rate limits, region drift, and outright death are all
   plausible. The slot's error taxonomy maps its honest verdicts
   ("parsing failed" → unavailable) so the trace stays meaningful when
   it goes.
2. **The embed hydration blob.** `__UNIVERSAL_DATA_FOR_REHYDRATION__`
   and `SIGI_STATE` are internal TikTok structures; shapes change
   without notice, and datacenter IPs often get a shell with no blob at
   all.
3. **CDN URL signatures.** Mirror-proxied URLs expire fast (minutes).
   ttagent downloads immediately after decode and never persists URLs
   as if they were durable — callers should not either.
4. **`data-video-id` recovery in oembed.** The official endpoint does
   not return the numeric id as a field; it is scraped from the embed
   snippet. Cheap, replaceable, honest about its venue.

## 4. Deliberate debts (known, documented, not fixed)

* Slideshows depend on the mirror exposing `images[]`. A future slot
  could add a second mirror; the envelope's `extraction_source` tells
  the caller which floor they are standing on.
* The `hd` variant is downloaded only when the mirror returns a
  *distinct* `hdplay` URL; when primary==HD there is one file, and the
  envelope reflects that rather than duplicating bytes.
* `demo.py`, `mcp_server.py`, and the tests all re-derive the tool path
  relative to their own file. If you move files, move them together.
* The endpoint matrix is verified from one vantage point (a datacenter
  VM). The protocol asks every maintainer to re-verify from theirs.

## 5. Design principles (do not casually reverse)

* **Honesty over completeness.** `status: partial`, structured
  `errors[]`, `reason:` strings — never fabricate a value.
* **404 is a filter, not an error.** But when every slot reports
  unavailable, the honest verdict is `E_VIDEO_UNAVAILABLE` — a verdict,
  recorded once, at the run level.
* **Politeness is a hard constraint.** 0.6 s decode sleeps, bounded
  retries, response caps, one post per invocation. "Restraint is the
  rent."
* **The docs are the spec.** `agent.md` (for machines) and `agents.md`
  (role prompts) are binding. Code conforms to them; when it cannot,
  the docs change first, deliberately.
* **Synthetic fixtures only.** No real handles, video ids, or CDN URLs
  in the repo — not in tests, not in docs, not in issues.

## 6. How to change something safely

1. Say which wall you are touching, out loud, in the PR description.
2. New behavior → tests first (offline, synthetic, fast).
3. New envelope field → bump `SCHEMA_VERSION`, update the draft-07
   schema, update `agent.md` §4, in one commit.
4. New/dead slot → update `DECODE_SLOT_FNS`, the trace test, and the
   endpoint matrix row.
5. Run: full suite → `sync_package.py --check` → CLI smoke → MCP probe.
