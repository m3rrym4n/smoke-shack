import subprocess
from pathlib import Path

SCRIPT_PATH = Path("scripts/set-app-version.cjs").resolve()


def test_set_app_version_updates_only_quoted_version_line(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    original = (
        "name: Smoke-Shack\n"
        'version: "1.2.0"\n'
        "image: m3rrym4n/smoke-shack\n"
        "arch:\n"
        "  - amd64\n"
    )
    config_path.write_text(original)

    subprocess.run(
        ["node", str(SCRIPT_PATH), "2.3.4", str(config_path)],
        check=True,
    )

    expected = original.replace('version: "1.2.0"', 'version: "2.3.4"')
    assert config_path.read_text() == expected


def test_set_app_version_fails_without_version_line(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    original = "name: Smoke-Shack\nimage: m3rrym4n/smoke-shack\n"
    config_path.write_text(original)

    result = subprocess.run(
        ["node", str(SCRIPT_PATH), "2.3.4", str(config_path)],
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode != 0
    assert config_path.read_text() == original
