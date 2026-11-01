import subprocess
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_tracked_files_do_not_contain_private_ipv4_address() -> None:
    tracked_files = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
    ).stdout.split(b"\0")
    private_address_prefix = b"192." + b"168."
    matches: list[str] = []

    for raw_path in tracked_files:
        if not raw_path:
            continue
        relative_path = Path(raw_path.decode())
        # Keep the dev image registry address until Public Launch, Phase 4.
        if (
            relative_path in {Path("CHANGELOG.md"), Path("compose.yml")}
            or relative_path.parts[0] == ".forgejo"
        ):
            continue
        if private_address_prefix in (REPOSITORY_ROOT / relative_path).read_bytes():
            matches.append(relative_path.as_posix())

    assert matches == [], f"private IPv4 address found in tracked files: {matches}"
