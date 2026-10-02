# Endpoint Matrix — ttagent

The living trust anchor. Every public surface ttagent depends on, with
its status and the date it was last verified **from a named vantage
point**. A row without a "last verified" date is folklore, not evidence.

Maintenance protocol (impersonal, four steps):

1. Re-verify the row by hand (one curl, one look at the body).
2. Update the row + the "last verified" line.
3. Open an issue if a surface flipped (up or down) — flips are facts,
   not failures.
4. Keep it impersonal: "as verified from <vantage>, <date>".

## Decode slots

| Surface | Role | Status | Failure signature | Last verified |
|---|---|---|---|---|
| `www.tikwm.com/api/?url=<enc>&hd=1` | slot 1 `tikwm` | WORKING — full payload: HD/clean/watermarked URLs, music, stats, author, slideshows; relative media paths need absolutizing | `{"code":-1,"msg":"Url parsing is failed!..."}` → `unavailable` | 2026-10-02, datacenter VM (live decode + verified downloads) |
| `www.tiktok.com/embed/v2/<id>` | slot 2 `embed_v2` | Shell-only from datacenter IPs; hydration blob (`__UNIVERSAL_DATA_FOR_REHYDRATION__` / `SIGI_STATE`) absent | no blob → `failed` | 2026-10-02, datacenter VM (shell observed) |
| `api.tiklydown.eu.org/api/download?url=<enc>` | slot 3 `tiklydown` | UNREACHABLE from this vantage (connection failure) | network error → `failed` | 2026-10-02, datacenter VM |
| `www.tiktok.com/oembed?url=<enc>` | slot 4 `oembed` | OFFICIAL, metadata-only; 302-walled from this vantage at times; never carries video bytes | 302 / non-JSON → `failed` | 2026-10-02, datacenter VM (302 observed) |

## Delivery (CDN)

| Surface | Status | Notes | Last verified |
|---|---|---|---|
| `*.tiktokcdn-us.com` (video, via mirror) | WORKING | unauthenticated GET; Content-Length present; MP4 `ftyp isom` verified | 2026-10-02, datacenter VM (live 2.0 MB video) |
| `*.tiktokcdn-us.com` (music) | WORKING | ID3 magic verified | 2026-10-02, datacenter VM (live music track) |
| `*.tikwm.com` (mirror-proxied media) | WORKING | relative paths returned by the API are absolutized; URLs expire in minutes — download immediately | 2026-10-02, datacenter VM |
| `*.tiktok.com` / `*.tiktokv.com` / `*.byteoversea.com` / `ttwvideo.akamaized.net` / `*.muscdn.com` | ALLOWLISTED, unverified live | first-party families; magic-byte gate still applies | — |

## Short links

| Surface | Status | Notes | Last verified |
|---|---|---|---|
| `vm.tiktok.com/<code>`, `vt.tiktok.com/<code>`, `tiktok.com/t/<code>` | IMPLEMENTED, one-hop | expired codes land on `/about` → honest `E_SHORTLINK_DEAD` | 2026-10-02 (mechanism verified; vanity codes themselves are ephemeral) |

## Field observations

* The mirror's error verdicts are honest and machine-usable: code -1
  with "Url parsing is failed" reliably means dead/private/unparseable —
  it is the `unavailable` signal, not a generic failure.
* Mirror media URLs are **short-lived** (minutes). The decode → download
  gap inside one run is tiny by design; a caller who stores URLs for
  later is storing folklore.
* The official `oembed` endpoint is the stable floor: whenever it
  answers, the envelope gets a title, author, and thumbnail — with
  `metadata_only` recorded, because bytes are simply not part of that
  contract.
