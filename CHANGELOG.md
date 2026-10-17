# Changelog

## Unreleased

- Add runtime Home Assistant and active-cook visibility through logs and `GET /status`.
- Publish dev images to Zot and write the immutable tag back to `compose.yml`.
- Use the real gmg-ha entities and states for cook phases, warnings, and probe targets.
- Install the Docker CLI in image-build jobs and keep pull request runs build-only.
- Run CI quality checks with uv-managed Python 3.12 on Forgejo runners.
- Rename the health endpoint to `/health` across the app and deployment configuration.
- Scaffold the FastAPI service, persistent cook lifecycle, Home Assistant ingest,
  read API, database migration, container, and CI/CD skeleton.
