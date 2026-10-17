# SPEC addendum (read after SPEC.md; these items override it)

## Timestamps on every timeline entry

Every event, sample and phase boundary carries a full timestamp (date **and** time of day), not just a date or an elapsed time.

- Store as timezone-aware UTC ISO 8601 with seconds (e.g. `2026-10-16T16:57:03Z`). Never store a bare date for an event.
- `events.ts`, `samples.ts` and all phase timestamps on `cooks` (`started_at`, `startup_ended_at`, `cook_ended_at`, `cooldown_ended_at`) are full datetimes.
- User-added events: the user can choose "right now" (server time) or pick an explicit date and time. Both are stored as a full datetime.
- Display in the timezone from the `TZ` environment variable (Stan is in America/Los_Angeles). Every timeline entry shows the date, the clock time and the elapsed time into the cook, e.g. `Oct 16 · 10:57 AM · 1h 15m`.
- The read API returns the UTC timestamp plus the elapsed seconds since the cook started (`elapsed_seconds`) for every event and sample, so the UI never has to compute it.
- Only `meat.purchased_on` and `pellets.purchased_on` are plain dates.
- Add a test: an event created at a known fake-clock time round-trips with the exact same date, time and elapsed seconds through the API.
