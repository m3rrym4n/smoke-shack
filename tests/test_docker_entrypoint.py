import os
import subprocess
from pathlib import Path

import pytest

ENTRYPOINT = Path(__file__).parents[1] / "docker-entrypoint.sh"


def test_entrypoint_has_valid_shell_syntax() -> None:
    subprocess.run(["sh", "-n", ENTRYPOINT], check=True)


@pytest.mark.skipif(os.geteuid() == 0, reason="requires a non-root test process")
def test_entrypoint_runs_command_unchanged_as_non_root() -> None:
    result = subprocess.run(
        [ENTRYPOINT, "echo", "ok"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout == "ok\n"
