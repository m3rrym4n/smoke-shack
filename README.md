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
| `DATABASE_PATH` | SQLite database path | `smoke-stack.db` |
| `PHOTO_DIR` | Photo storage directory | `photos` |
| `SAMPLE_INTERVAL_SECONDS` | Active-cook sampling interval | `10` |
| `INCOMPLETE_TIMEOUT_MINUTES` | Cool-down timeout before marking incomplete | `90` |
| `TZ` | Display timezone reserved for the UI | `America/Los_Angeles` |
| `ENTITIES_CONFIG` | Entity mapping YAML path | `config/entities.yaml` |

Never commit `HA_TOKEN`. The API is available at `/health`, `/api/cooks`, and the per-cook
detail, `samples`, and `events` routes.

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

The CI deploy section is intentionally a stub for job 1. Completing it requires Forgejo
secrets named `REGISTRY_USERNAME`, `REGISTRY_PASSWORD`, `DOCKHAND_URL`, and `DOCKHAND_TOKEN`.
No secret values belong in this repository. `compose.main.yml` is intentionally deferred until
the first promotion to `main`, per the repository deployment conventions.
