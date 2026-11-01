import re
from pathlib import Path

import yaml

WORKFLOW_PATH = Path(".forgejo/workflows/main-release.yml")


def test_main_release_creates_public_release() -> None:
    workflow_text = WORKFLOW_PATH.read_text()
    workflow = yaml.safe_load(workflow_text)
    public_job = workflow["jobs"]["public-release"]
    job_text = "\n".join(step.get("run", "") for step in public_job["steps"])

    assert public_job["needs"] == "release"
    assert "github.ref_name == 'main'" in public_job["if"]
    assert "secrets.GH_RELEASE_TOKEN" in workflow_text
    assert not re.search(r"GH_RELEASE_TOKEN:\s*(?!\$\{\{)[^\s]+", workflow_text)

    existing_release = "/releases/tags/${RELEASE_TAG}"
    tag_check = "/git/ref/tags/${RELEASE_TAG}"
    create_release = '"${api_url}/releases"'
    assert existing_release in job_text
    assert job_text.index(existing_release) < job_text.index(tag_check)
    assert job_text.index(tag_check) < job_text.rindex(create_release)

    assert "gh " not in job_text
    assert "awk 'index($0, \"-\") == 0'" in job_text
