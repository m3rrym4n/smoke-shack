# Smoke Stack

Smoke Stack is a small FastAPI service that records Green Mountain Grills cook data from
Home Assistant. Job 1 provides the database, HA ingestion, cook lifecycle, read-only API,
tests, and container scaffold.

## Run locally

Python 3.12 is required.

```sh
python3.12 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
cp config/entities.example.yaml config/entities.yaml
alembic upgrade head
uvicorn app.main:app --reload
```

Set the entity IDs in `config/entities.yaml` for the Home Assistant installation. The client
authenticates to `/api/websocket`, loads an initial state snapshot, subscribes to
`state_changed`, periodically refreshes all states, and reconnects with exponential backoff.

## Configuration

| Variable | Purpose | Default |
| --- | --- | --- |
| `HA_URL` | Home Assistant base URL, such as `http://homeassistant.local:8123` | empty (ingest disabled) |
| `HA_TOKEN` | Home Assistant long-lived access token | empty |
| `HA_WS_MAX_SIZE_BYTES` | Maximum Home Assistant websocket message size in bytes | `67108864` (64 MiB) |
| `DATABASE_PATH` | SQLite database path | `smoke-stack.db` |
| `PHOTO_DIR` | Photo storage directory | `photos` |
| `SMOKE_STACK_GRILL_NAME` | Grill name fallback when Home Assistant has none | `My grill` |
| `SAMPLE_INTERVAL_SECONDS` | Active-cook sampling interval | `10` |
| `DATA_GAP_EVENT_MIN_SECONDS` | Minimum gap length that gets its own Cook Log event | `120` |
| `INCOMPLETE_TIMEOUT_MINUTES` | Cool-down timeout before marking incomplete | `90` |
| `TZ` | Display timezone reserved for the UI | `America/Los_Angeles` |
| `ENTITIES_CONFIG` | Entity mapping YAML path | `config/entities.yaml` |

Never commit `HA_TOKEN`. `GET /health` reports only application health and does not depend on
Home Assistant. `GET /status` reports HA connection state, the latest event and sample times,
the active cook, the sampling interval, and the application version. Cook data is available at
`/api/cooks` and the per-cook detail, `samples`, and `events` routes.

## Data export

- `GET /api/export/cooks.csv` exports one row per cook. It accepts the same `meat_id`,
  `pellet_id`, and `status` filters as `GET /api/cooks`.
- `GET /api/export/cooks/{cook_id}/samples.csv` exports every raw sample for one cook,
  including a column for each extra probe found in that cook.
- `GET /api/export/all.json` exports cooks with nested event and photo metadata, meat,
  pellets, profiles with steps, and notes. Raw samples and photo binaries are intentionally
  excluded; use the per-cook samples CSV and photo URLs for those.

All exports download as date-stamped attachments. CSV free-text values that could be treated
as spreadsheet formulas are escaped with a leading apostrophe.

## Test and build

```sh
ruff check .
mypy app
pytest
docker build -t smoke-stack:local .
```

To run the Dockhand development stack, provide `HA_URL` and `HA_TOKEN` in its stack
environment and use `compose.yml`. The committed image tag `job1-placeholder` is deliberately
literal so CI can replace it with an immutable registry tag after publishing.

On pushes to `dev`, CI publishes a `dev-<short-sha>` image to the trusted local Zot registry
and commits that immutable tag back to `compose.yml`; no CI secrets are required. Pull request
runs build the image without publishing or changing the branch. `compose.main.yml` is
intentionally deferred until the first promotion to `main`, per the repository deployment
conventions.
