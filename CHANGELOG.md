# Changelog

## Unreleased

- Collapse brief Home Assistant data gaps into one Cook Log summary.
- Anchor the smoke source and plume to the grill photo while the page scrolls.
- Move the showcase logo into the bottom of the temperature gauge.
- Render a realistic, state-aware smoke plume above the full live page with a demo mode.
- Make Pit showcase image selection row-specific and save smoke positions immediately.
- Stack the Pit showcase vertically with full-width, frameless grill photos and wrapping names.
- Accept safely validated SVG files for Pit showcase logos.
- List and default live and planned cooks correctly in Pit Notes.
- Add live-cook smokestack wisps with grill-state intensity and a remembered motion toggle.
- Add a responsive Pit showcase with grill branding, editable pictures, and a smoke anchor.
- Add the grill name and uploadable showcase logo and photo APIs.
- Show planned, live, and incomplete cooks in the Cook Log with automatic refreshes.
- Add immediate photo uploads and galleries to the Order Pad and cook details.
- Add explicit live, planned, new-order, and closed-cook modes to the Order Pad UI.
- Add planned cooks that are atomically adopted when the next live cook starts.
- Include uncooked Butcher Case meat types in the Ask the Pitmaster filter.
- Complete the Order Pad with available-purchase selectors, pellet usage, and cook costs.
- Add the Ask the Pitmaster cook-time statistics board with bookmarkable filters.
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
