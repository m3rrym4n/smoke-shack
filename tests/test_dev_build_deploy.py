import shlex
import subprocess
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = REPOSITORY_ROOT / ".forgejo/workflows/dev-build-deploy.yml"


@pytest.mark.parametrize(
    "existing_image",
    [
        "192.168.1.73:5050/smoke-stack/smoke-stack:1.1.1-dev.2",
        "192.168.1.73:5050/smoke-shack/smoke-shack:1.1.1-dev.3",
    ],
)
def test_deployed_image_rewrite_replaces_any_existing_image_line(
    tmp_path: Path, existing_image: str
) -> None:
    workflow = WORKFLOW_PATH.read_text()
    sed_line = next(
        line.strip() for line in workflow.splitlines() if line.strip().startswith("sed -i ")
    )
    command = shlex.split(sed_line.replace("${{ env.IMAGE_TAG }}", "1.2.3-dev.4"))
    compose_path = tmp_path / "compose.yml"
    compose_path.write_text(f"services:\n  smoke-shack:\n    image: {existing_image}\n")
    command[-1] = str(compose_path)

    subprocess.run(command, check=True)

    assert compose_path.read_text() == (
        "services:\n"
        "  smoke-shack:\n"
        "    image: 192.168.1.73:5050/smoke-shack/smoke-shack:1.2.3-dev.4\n"
    )
