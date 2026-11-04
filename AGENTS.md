# AGENTS.md: guidance for Codex dispatches

Read `docs/SPEC.md` and `docs/SPEC-addendum.md` before any work. The issue you were dispatched on defines the scope; do only that.

## Branches and merging
- Work on a branch and open a PR. Never push directly to `main` and never merge into `main` yourself. Promotion to `main` is a human action.
- Open pull requests on this Forgejo repository only, with `dev` as the base branch, using the established Forgejo method. Never run `gh` or call any other GitHub API, and never create GitHub pull requests, issues, releases, or repositories; the GitHub mirror is read-only output. If the Forgejo pull request cannot be opened, stop and report it instead of falling back to GitHub.
- Use Conventional Commit prefixes (`feat:`, `fix:`, `docs:`, `chore:`).
- Any new cross-cook aggregate must exclude cooks with `exclude_from_stats`.
- Codex never pushes to or merges into `main`.
- Do not edit `CHANGELOG.md`; it is generated from commit messages at release time. Use a clear Conventional Commit subject, because it becomes the release note.
- Merged PR branches are deleted automatically by `.forgejo/workflows/cleanup-merged-branches.yml` using a Forgejo authorized integration.

## Deploy conventions (these override the deploy bullets in issues)
- Root `compose.yml` is the public install file. It uses the Docker Hub image, service and container `smoke-shack`, named volume `smoke-shack-data` mounted at `/data`, and host port `8011` mapped to container port `8000`. Do not point it at the dev stack or Zot.
- `deploy/dev/compose.yml` is the internal Dockhand dev stack on the target host (`your-host`): service `smoke-shack`, `container_name: smoke-shack-dev`, named volume `smoke-shack-dev-data` mounted at `/data`, and host port `8010` mapped to container port `8000`. It is the only compose file where CI writes the deployed image tag, and its `image:` line must remain a literal tag.
- Do not create `compose.main.yml`.
- Stable releases are published by CI to Docker Hub (multi-arch) and Zot. Codex does not touch release or publish workflows unless the issue says so.
- There is no SSH access and no manual deploys. Do not commit secrets.
- Health check: the endpoint is `GET /health` (not `/healthz`) and returns `{"status":"ok"}` with HTTP 200. Add a matching `healthcheck:` in `compose.yml`.
- The container listens on port 8000 and runs `uvicorn` as a non-root user.

## Style
- Keep it simple and boring. No auth, telemetry, or safety text or confirmations in the app UI. The Safety section in the docs is intentional; do not remove it. No secrets in the repo.

CI runs a gitleaks scan against the full Git history. If it finds a credential, rotate the credential first.
