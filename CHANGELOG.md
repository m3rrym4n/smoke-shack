# Changelog

## Unreleased

- Add the Pit Notes board with cook-aware create, filtering, inline edit, and delete controls.
- Add the Pellet Pantry purchase board with create, edit, linked-cook, and delete controls.
- Add the Butcher Case purchase board with create, edit, linked-cook, and delete controls.
- Preserve otherwise valid samples when only one core grill entity is unavailable.
- Prevent older dev builds from overwriting newer deployed image tags during CI write-back races.
- Sample the latest Home Assistant grill state on a timer while connected.
- Ignore implausible grill snapshots and coalesce Home Assistant update bursts.
- Add live event pinning and editing plus the cook Order Pad form.
- Add cook temperature charts, event logs, paginated cook history, and read-only cook details.
- Add the read-only live cook boards with pit gauge, phase progress, probes, and paused background polling.
- Add the BBQ signage UI shell, hash navigation, and active-cook neon indicator.
- Add filtered cook CSV, raw sample CSV, and full journal JSON export APIs.
- Add filtered cook duration statistics and meat-type count APIs.
- Add cook and event photo upload, serving, editing, listing, and deletion APIs.
- Add cook journal editing, linked summaries and costs, filtering, pagination, and deletion.
- Add profiles and ordered profile steps CRUD APIs.
- Add notes CRUD and editable user timeline event APIs.
- Add meat and pellet purchase CRUD APIs with filtering and cook reference protection.
- Raise the configurable HA websocket message limit and retain only configured entity states.
- Add runtime Home Assistant and active-cook visibility through logs and `GET /status`.
- Publish dev images to Zot and write the immutable tag back to `compose.yml`.
- Use the real gmg-ha entities and states for cook phases, warnings, and probe targets.
- Install the Docker CLI in image-build jobs and keep pull request runs build-only.
- Run CI quality checks with uv-managed Python 3.12 on Forgejo runners.
- Rename the health endpoint to `/health` across the app and deployment configuration.
- Scaffold the FastAPI service, persistent cook lifecycle, Home Assistant ingest,
  read API, database migration, container, and CI/CD skeleton.
