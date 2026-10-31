# Smoke-Shack: public read-only page (spec addendum)

Addendum to `docs/SPEC.md` and `docs/SPEC-addendum.md`. Describes an external, read-only, live view of Smoke-Shack hosted on Cloudflare, in the same style as Rinse Index (one Worker with Static Assets, no admin UI, no CMS). If this file conflicts with the SPEC on anything public-page related, this file wins.

## 1. Goals and non-goals

- A public page that shows everything the private app shows except controls and editing: live cook, cook log and timeline, charts, Butcher Case (meat), Pellet Pantry, Profiles, Pit Notes, and the "Ask the Pitmaster" stats.
- The page is **live**: while a cook is active, visitors see the pit temp, probes and timeline update in near real time.
- No controls, no forms, no write path of any kind from the public side.
- Nothing on the internet connects into the homelab. Smoke-Shack (on Factory) only makes **outbound** HTTPS calls.
- Runs on the Cloudflare **free** plan. No cost surprises: free-plan overages fail, they do not bill.

Non-goals: authentication for viewers, comments, sending anything to the grill, exposing Home Assistant, photos in the first release (phase 2).

## 2. Architecture

```
Smoke-Shack (Factory, private)                Cloudflare (public)
  HA ingest -> SQLite                          +-----------------------------------------+
  publisher (outbound HTTPS only) ----------->  | Worker "smoke-shack-public"             |
    live push (every 15 s during a cook)       |  /            static page (Static Assets)|
    snapshot sections (on change)              |  /api/ingest/* signed POST (HMAC)        |
                                               |  /api/live, /api/live/ws  public GET     |
                                               |  /api/data/*   public GET                |
                                               +-------+------------------+--------------+
                                                       |                  |
                                              Durable Object (SQLite)   Workers KV
                                              live cook state + series  snapshot sections
```

- **Live state** lives in one Durable Object (SQLite-backed, the only kind on the free plan). KV is **not** used for live data (1,000 writes/day, up to about 60 s propagation).
- **Snapshot data** (past cooks, meat, pellets, profiles, notes) lives in KV, one key per section, written only when its content hash changed.
- Frontend: plain HTML/CSS/TypeScript, no framework, the BBQ joint signage design from the mockup, read-only. Degrades gracefully (a styled "offline" state) if the API fails.
- Storage access sits behind a small adapter interface so a future move off Cloudflare is an adapter swap.

## 3. Security model

- **Inbound to the homelab: none.** The publisher only calls out.
- **Write path** (`/api/ingest/*`): every request carries `X-Timestamp` (unix seconds) and `X-Signature` = hex `HMAC-SHA256(PUSH_SECRET, timestamp + "." + raw_body)`. The Worker rejects a timestamp more than 300 s from its clock, compares signatures in constant time, and rejects live messages whose `seq` is not greater than the last accepted `seq`. The secret is never sent over the wire. HTTPS only.
- `PUSH_SECRET` is a Worker Secret on Cloudflare and the env var `PUBLIC_PUSH_SECRET` in the Dockhand stack. Never committed.
- **Blast radius of a leaked secret:** someone can post fake data to the page. They cannot reach the homelab, Home Assistant, or the grill.
- **Public payloads are built from an explicit allowlist** (section 5), never by dumping database rows. They must never contain: HA URL or token, entity IDs, internal IPs, hostnames, file system paths, or the push secret.
- Free-text fields (notes, seasonings, sauces, results, event descriptions) are user-authored and may contain private details. The `PUBLIC_HIDE` setting can remove categories (section 5). The page must render all text as text (no HTML injection).
- The public API is GET-only. Any other method returns 405.

## 4. Cloudflare free-plan budget (verified against Cloudflare docs, 2026-10)

| Limit (free) | Per day | Planned use |
|---|---|---|
| Worker requests | 100,000 | live pushes about 2,900 per 12 h cook, plus viewer API calls |
| Durable Object requests | 100,000 | same pushes plus viewer connects |
| Durable Object rows written | 100,000 | one row per live sample, about 2,900 per cook |
| Durable Object compute | 13,000 GB-s | one object, hibernating WebSockets |
| KV writes | 1,000 | a few per cook end or edit |
| KV reads | 100,000 | cached reads |

Rules that keep it inside the budget:
- Static assets (HTML/CSS/JS) are served by Static Assets and do not count against Worker requests.
- Viewers get live data over a **hibernating WebSocket** (one request on connect, outgoing messages free). Cap at 100 concurrent sockets; above that the page falls back to polling `/api/live` every 15 s, which the Worker answers from a 10 s cache.
- Snapshot reads are cached (Cache API, 30 s).
- When the Worker is over quota the page shows its offline state; Smoke-Shack keeps recording locally regardless.

## 5. Public data contract

Settings in Smoke-Shack (env, all optional):

| Env | Default | Meaning |
|---|---|---|
| `PUBLIC_PUSH_URL` | empty | Base URL of the Worker, e.g. `https://example/`. Empty disables the publisher entirely. |
| `PUBLIC_PUSH_SECRET` | empty | HMAC secret. Required when the URL is set. |
| `PUBLIC_LIVE_INTERVAL_SECONDS` | 15 | Live push interval while a cook is active. |
| `PUBLIC_HIDE` | empty | Comma list of `prices`, `stores`, `notes`, `freetext`. `prices` removes all price and cost fields; `stores` removes store names; `notes` removes the notes section; `freetext` removes seasonings, sauces, results and event descriptions. |

All timestamps are UTC ISO with `Z` and seconds, as in `SPEC-addendum.md`. Payload builders live in `app/public.py` and are covered by tests that fail if a field outside the allowlist appears.

### Live message: `POST /api/ingest/live`

```
{
  "seq": 1234,                       // strictly increasing per Smoke-Shack process run, plus "run_id"
  "run_id": "uuid",                  // new value each process start; seq restarts at 1
  "sent_at": "ISO",
  "grill": "off" | "startup" | "cook" | "cooldown",
  "cook": null | {
    "id": int, "started_at": "ISO", "phase": str, "has_gap": bool,
    "meat": {"type": str, "pounds": number} | null,
    "pellet": {"vendor": str, "product_name": str} | null,
    "profile_name": str | null
  },
  "sample": null | {"ts": "ISO", "elapsed_seconds": int, "pit_temp": n, "setpoint": n,
                     "probe1": n|null, "probe2": n|null, "probe1_target": n|null, "probe2_target": n|null},
  "new_events": [ {"id": int, "ts": "ISO", "elapsed_seconds": int, "kind": str, "title": str, "description": str|null} ]
}
```
The Worker appends `sample` to the Durable Object's series for that cook and relays the message to connected viewers.
If the Worker does not hold the cook's earlier series (new cook, Worker restart, missed seq), it answers `409 {"need": "resync"}` and Smoke-Shack sends `POST /api/ingest/live/resync` with the cook object, every sample so far, and all events (about 4,400 samples max for a 12 h cook). After a cook ends, one final live message with `grill: "off"` and `cook: null` clears the live view.

### Snapshot sections: `PUT /api/ingest/snapshot/<section>`

Sections: `cooks-index`, `cook-<id>` (detail: cook fields, events, samples downsampled to at most one per 30 s), `meat`, `pellets`, `profiles` (with steps), `notes`, `meta` (`updated_at`, app version). The Worker stores each in KV under the same name and skips the write when the body hash matches. Pushed: at process start (all sections), after a cook ends, after any edit through the private API (debounced 5 s), and once a day as a heartbeat.

Allowlisted fields: the cook fields in the existing cook JSON (phase times, durations, effective setpoint, status, flags), embedded meat and pellet summaries, profile name, journal text fields (subject to `PUBLIC_HIDE`), events and samples as in the live message. `prices` hides `price_per_pound` and cost; `stores` hides `store`.

### Public read API (Worker)

- `GET /api/live`: current live state, plus `online` (false when no live push for 90 s) and `last_update`.
- `GET /api/live/ws`: WebSocket; sends the current state on connect, then each live message.
- `GET /api/data/<section>`: the stored snapshot sections (`cooks-index`, `cook/<id>`, `meat`, `pellets`, `profiles`, `notes`, `meta`).
- "Ask the Pitmaster" runs in the browser over `cooks-index` (filters by meat type, pounds, setpoint, dates; averages and min/max), so it needs no extra endpoint.

## 6. Failure behavior

- The publisher runs in its own task. A failing push never blocks or slows ingest or recording.
- Failed pushes retry with exponential backoff (5 s up to 5 min). Live messages are dropped, not queued; a resync restores state.
- `GET /status` on Smoke-Shack gains `public`: `{"enabled": bool, "last_push_at": ISO|null, "last_error": str|null}`.
- The page shows "Grill link offline, last seen <time>" when `online` is false, and still shows history from snapshots.

## 7. Repos, deploy and build order

- New Forgejo repo `m3rrym4n/smoke-shack-public` (TypeScript Worker + static frontend), registered with Variflex, CI copied from CrateSpy's Forgejo pattern (typecheck, tests). Forgejo only; nothing on GitHub.
- Deploy: Forgejo Actions runs `wrangler deploy` with `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` as repo secrets. `PUSH_SECRET` is set once with `wrangler secret put`. Custom domain: to be decided.
- Order: (1) public payload builders and preview endpoints in Smoke-Shack, (2) publisher client and snapshot push, (3) live push loop, (4) Worker scaffold with signed ingest, (5) snapshot storage and read API, (6) live Durable Object and WebSocket, (7) frontend in slices (live board, cook log and timeline, Butcher/Pellets/Profiles/Notes, Ask). The frontend slices need the mockup committed under `docs/mockup/`.
- Issues stay small (one slice per job) to avoid timeouts.

## 8. Open items

- Public hostname.
- Photos on the public page (needs R2 or similar; phase 2).
- Whether prices, stores and notes should be hidden by default (currently shown unless `PUBLIC_HIDE` says otherwise).
