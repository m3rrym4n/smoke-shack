# Contributing to Smoke-Shack

Thanks for helping improve Smoke-Shack. Keep changes small and focused, and target pull
requests at the `dev` branch.

## Development checks

Smoke-Shack requires Python 3.12. Create a virtual environment and install the development
dependencies with the same tooling used in CI:

```sh
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e '.[dev]'
```

Run all required checks before opening a pull request:

```sh
.venv/bin/ruff check .
.venv/bin/mypy app
.venv/bin/pytest
```

## Commits and pull requests

Use [Conventional Commits](https://www.conventionalcommits.org/) for commit messages and
pull request titles. In particular, `feat:` and `fix:` changes are releasable. Other useful
prefixes include `docs:` and `chore:`.

Open a small, focused pull request against `dev`, explain the change, and include tests where
appropriate. Confirm that Ruff, mypy, and pytest pass.

## Repository mirror

This GitHub repository is a one-way mirror of the private primary repository. GitHub pull
requests are welcome, but they are not merged on GitHub. The maintainer imports contributions
into the primary repository, reviews and merges them there, and the merged result then appears
on GitHub through the mirror.
