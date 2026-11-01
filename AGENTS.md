# AGENTS.md: guidance for Codex dispatches

Read `docs/SPEC.md` and `docs/SPEC-addendum.md` before any work. The issue you were dispatched on defines the scope; do only that.

## Branches and merging
- Work on a branch and open a PR. Never push directly to `main` and never merge into `main` yourself. Promotion to `main` is a human action.
- Use Conventional Commit prefixes (`feat:`, `fix:`, `docs:`, `chore:`).
- Any new cross-cook aggregate must exclude cooks with `exclude_from_stats`.
- Codex never pushes to or merges into `main`.
- Add a `CHANGELOG.md` entry under `## Unreleased` for any functional code change.
- Merged PR branches are deleted automatically by `.forgejo/workflows/cleanup-merged-branches.yml` using a Forgejo authorized integration.

## Deploy conventions (these override the deploy bullets in issues)
- The app deploys to the target host (`your-host`) as a **Dockhand git stack** that reads `compose.yml` from the root of this repo. There is no SSH access and no manual deploys.
- `compose.yml` is the **dev** stack: service `smoke-shack`, `container_name: smoke-shack-dev`, named volume `smoke-shack-dev-data` mounted at `/data`, host port `8010` mapped to container port `8000`, `restart: unless-stopped`, environment variables passed through from the stack env (`HA_URL`, `HA_TOKEN`, `DATABASE_PATH=/data/smoke-shack.db`, `PHOTO_DIR=/data/photos`, `SAMPLE_INTERVAL_SECONDS`, `TZ=America/Los_Angeles`). Do not commit secrets.
- A `compose.main.yml` (container `smoke-stack`, volume `smoke-stack-data`, host port `8011`) is added later, at the first promotion to `main`. Do not create it now.
- The image is pushed to the Zot registry at `your-host:5050/smoke-shack/smoke-shack:<tag>`. The compose `image:` line must be a literal tag so a CI step can rewrite it (the CrateSpy tag write-back pattern); for job 1 use a placeholder tag and document it.
- Health check: the endpoint is `GET /health` (not `/healthz`) and returns `{"status":"ok"}` with HTTP 200. Add a matching `healthcheck:` in `compose.yml`.
- The container listens on port 8000 and runs `uvicorn` as a non-root user.

## Style
- Keep it simple and boring. No auth, telemetry, or safety text or confirmations. No secrets in the repo.

CI runs a redacted gitleaks scan against the full Git history on every configured push and pull request. If it finds a credential, rotate the credential first, then remove it from history or add a narrowly scoped allowlist entry with a documented justification for a reviewed false positive.
