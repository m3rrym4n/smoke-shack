# Smoke-Shack: product spec

Cook journal for a Green Mountain Grills Daniel Boone Prime WiFi pellet grill, controlled through Home Assistant (HA) using the `gmg-ha` integration (local UDP). It records the **raw samples** of every cook (not chart screenshots) so cooks can be aggregated and queried, e.g. "average cook time for a 4 lb pork picnic shoulder at 275".

Owner: Pacific Shift Labs. Keep the code simple, boring and well tested.

## 1. Stack and deployment

- Python 3.12, FastAPI, SQLite (WAL mode), SQLAlchemy 2 + Alembic, pytest, ruff, mypy.
- One Docker image, single container, one volume for the SQLite DB and uploaded photos.
- Forgejo-native CI/CD (`.forgejo/workflows/dev-build-deploy.yml`, `main-release.yml`), deployed through Dockhand to the target host (`your-host`).
- Configuration by environment variables only: `HA_URL`, `HA_TOKEN` (long-lived token, secret), `DATABASE_PATH`, `PHOTO_DIR`, `SAMPLE_INTERVAL_SECONDS` (default 10), `TZ`.
- HA entity IDs are **configuration, not code** (YAML or env): pit climate entity, pit temp, setpoint, probe 1 and 2 temps, fire state, power state, plus an optional list of extra probes (Bluetooth probes via ESP32 will be added later).
- No auth in v1 (LAN only). Do not add telemetry.

## 2. Ingest

- A background task holds a Home Assistant WebSocket connection (`/api/websocket`, auth with the token, `subscribe_events` for `state_changed` on the configured entities, plus a periodic poll for a full snapshot).
- While a cook is active, write one **sample** row every `SAMPLE_INTERVAL_SECONDS` (default 10 s): timestamp, pit temp, setpoint, probe temps, fire state, power state, HVAC mode. Keep raw values; never down-sample on write.
- Reconnect with backoff on disconnect. A gap longer than 3 sample intervals while a cook is active is a **data gap**: record an event `data_gap` with start and end, and flag the cook (`has_gap = true`). Never interpolate.
- On restart mid-cook, resume the active cook from the database (cook state is derived from stored rows, not memory).

## 3. Cook lifecycle and phases

A cook is auto-created when the grill is lit (power on / HVAC mode leaves Off). Phases, in order:

1. **Startup**: from ignition until the setpoint changes from 150 to any other value. The grill defaults to a 150 hold on startup; the user leaves that alone. Startup may be 0 seconds if the setpoint is already changed immediately.
2. **Cook**: from the setpoint leaving 150 until the user presses power off (shutdown).
3. **Cool down**: from power off until the grill finishes its cool-down cycle (fan stops / state returns to off).
4. **Grill time** = Startup + Cook + Cool down. Grill time closes when cool down completes.

Rules:
- If the setpoint returns to 150 mid-cook, it stays in the cook phase (the user never does this, but handle it).
- Fan-only mode: no cook is created for a fan-only run unless a cook is already active; treat fan-only before ignition as not a cook.
- Phase boundaries are stored as timestamps on the cook; phase durations are computed from them.
- A cook ends when cool down completes or after a configurable timeout (default 90 min) with an `incomplete` flag.

### Cook summary (computed and stored on the cook row)

- Phase durations (startup, cook, cool down, grill time).
- **Aggregate setpoint**: the setpoint held the longest during the cook phase (by seconds). The user can override it manually. This is the setpoint used when querying.
- **Time to done**: cook-phase time from the start of cook until the first time a probe reached its done target (when a target is set).
- `has_gap`, `incomplete` flags.

## 4. Events (timeline)

One `events` table for everything on the timeline.

- Automatic: fire lit, setpoint changed (from, to), mode changed, probe connected/disconnected, warnings, first time a probe reaches its done target, phase changes, data gaps.
- **User-added**: pinned by the user on the cook timeline. Fields: title (e.g. "The stall"), free-text description (e.g. "Wrapped in foil at the stall"), kind (stall, wrapped, spritzed, sauced, flipped, rested, custom), time (now, or an explicit time offset in the cook), optional photo. User events render as numbered pins on the chart and as entries in a cook log list; automatic events show in the log in a muted style.
- User events can be edited and deleted. Automatic events cannot.

## 5. Data model (tables)

- `cooks`: id, started_at, ended_at, status, meat_id (FK), pellet_id (FK), rotisserie (bool), seasonings, sauces, prep_time_minutes, results_text, profile_id (FK, nullable), phase timestamps, aggregate_setpoint, setpoint_override, time_to_done_seconds, has_gap, incomplete, created/updated.
- `samples`: cook_id, ts, pit_temp, setpoint, probe1, probe2, extra probes (JSON), fire_state, power_state, hvac_mode. Index on (cook_id, ts).
- `events`: id, cook_id, ts, kind, source (auto or user), title, description, data (JSON), photo_path.
- `photos`: id, cook_id, event_id (nullable), path, caption.
- `meat`: **one row per purchase**. id, type (e.g. "Pork butt"), pounds, price_per_pound, store, purchased_on (date). Total cost is computed (pounds x price_per_pound). A meat row links to at most one cook.
- `pellets`: id, vendor, product_name, price_per_pound, purchased_on (date).
- `profiles`: id, name, keep_warm (bool), keep_warm_temp, created/updated.
- `profile_steps`: id, profile_id, position, grill_temp, stop_mode (`time` or `internal_temp`), duration_minutes (for time), probe (1 or 2) and target_temp (for internal temp), instructions (default empty, UI shows "No instructions").
- `notes`: id, body, title, scope (this_cook, pellets, gear), cook_id (nullable), created_at.
- Alembic migrations from day one. Dates stored as ISO 8601; times as UTC.

## 6. Profiles (copied from the GMG app)

A profile is a programmable cook with any number of steps:
- Each step has a grill temperature and a stop condition: a duration (hours and/or minutes) **or** an internal probe temperature (which probe, and the target).
- Per-step instructions text (default "No instructions").
- Steps can be reordered, added and deleted.
- Optional **Keep Warm** at the end (with a hold temperature, e.g. 165 F). Off means shut down and cool down.
- A **Start Profile** action runs the profile: apply step 1's setpoint through HA (`climate.set_temperature`), watch the stop condition, then advance to the next step; at the end, keep warm or shut down. Starting a profile attaches it to the cook (`cooks.profile_id`). Profile steps taken are recorded as events.
- The runner must be restart-safe (its position is stored), and must not change the setpoint if a human changed it in the meantime without recording an event.
- Seed example: "Pulled Pork" = 380 F for 30 min, 380 F for 32 min, 215 F until probe 1 reads 193 F, then keep warm.

## 7. Notes

Free-form sticky notes, tagged by scope: this cook, pellets, gear. Title and body; filter by scope. A note can be tied to a cook.

## 8. Query API (the point of the whole thing)

- `GET /api/stats/cook-time`: filters meat type, pounds range, aggregate setpoint +/- N F (default 10), rotisserie, pellet vendor/product, store; returns count of matching cooks, average/min/max for startup, cook, cool down, grill time, and cook time per pound.
- `GET /api/cooks`, `GET /api/cooks/{id}`, `GET /api/cooks/{id}/samples` (raw), `GET /api/cooks/{id}/events`.
- Cost per cook: meat total + pellet cost where pounds used are known (v1: optional field `pellets_used_lb` on the cook; leave blank otherwise).
- Export: CSV and JSON for cooks and samples.
- An MCP tool wrapping the stats endpoint (later job). A Home Assistant dashboard embed of the live cook view (later job).

## 9. UI (look and feel is decided)

Direction: **BBQ joint signage**. The approved mockup at `docs/mockup/Signage.dc.html` is the design reference. Do not invent another style.

Design tokens:
- Page: wood paneling background (#4a2d19 with repeating-linear-gradient grain).
- Chalkboard panels: bg #1f2b25, 16px wood frame #7a4a24, inset shadow, chalk text #f1efe4.
- Accent yellow #f7d65a, pit red #a3231a, pit line #f4a38a, probe line #9fd3e6, muted #b9c3b5, order-pad cream #f6efdc with ink #23232e and blue #3b4a8a.
- Fonts (Google Fonts): Rye (painted sign, buttons), Bungee (neon), Caveat Brush (chalk headings and numbers), Patrick Hand (body).
- Components: enamel thermometer dial (SVG), neon "NOW SMOKING" sign, chalk chips, painted buttons with a hard shadow, menu rows with dotted leaders, taped paper notes, order pad form.
- Sections: header + nav; The Pit (dial, presets, Start / Fan / Shutdown); Today's Special (phase bar and leader rows); Probe boards; Chalked-up chart with numbered event pins; Cook Log + Pin an event; Profiles (list, step editor, keep warm, shape-of-the-cook diagram, Save and Start); Butcher Case (meat); Pellet Pantry; Pit Notes; Ask the Pitmaster (stats); Order Pad (cook form: meat dropdown from the meat table which fills weight, pellets dropdown from the pellets table, seasonings, sauces, prep time, rotisserie yes/no, results, photo).
- **Responsive**: must work on desktop and phone browsers. Min 44 px touch targets, flex-wrap rows, no horizontal page scroll (the chart may scroll sideways inside its own panel on a phone). No frontend build step in v1: server-rendered templates (Jinja2) with a small amount of vanilla JS or htmx, vendored locally. Fonts may load from Google Fonts.
- Start / Fan / Shutdown buttons call HA `climate.set_hvac_mode` (Heat / Fan only / Off). Do not add safety lectures, confirmations for Start, or warning text. A short confirmation on Shutdown only.

## 10. Build plan (in order)

1. Scaffold, schema + migrations, HA ingest, phase state machine, tests, Docker, CI/CD skeleton (issue 1).
2. CRUD APIs for meat, pellets, notes, profiles, user events, cooks (including photos) + query/stats API + CSV/JSON export.
3. UI shell and the live cook view (dial, phase bar, probes, chart with event pins, Pin an event).
4. UI for Butcher Case, Pellet Pantry, Notes, Order Pad, Ask the Pitmaster.
5. Profiles UI and the profile runner.
6. MCP tool + HA dashboard embed; deploy hardening.

Out of scope for now: pizza mode (needs gmg-local protocol work), Bluetooth probes (ESP32 proxy; the entity list is already configurable), multi-user auth.
