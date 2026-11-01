import re
from pathlib import Path

import yaml

WORKFLOW_PATH = Path(".forgejo/workflows/main-release.yml")


def test_main_release_publishes_stable_image() -> None:
    workflow_text = WORKFLOW_PATH.read_text()
    workflow = yaml.safe_load(workflow_text)
    publish_job = workflow["jobs"]["publish-image"]
    job_text = "\n".join(step.get("run", "") for step in publish_job["steps"])

    assert publish_job["needs"] == "release"
    assert "github.ref_name == 'main'" in publish_job["if"]
    assert "secrets.DOCKERHUB_USERNAME" in workflow_text
    assert "secrets.DOCKERHUB_TOKEN" in workflow_text
    assert not re.search(r"DOCKERHUB_TOKEN:\s*(?!\$\{\{)[^\s]+", workflow_text)

    push_lines = [
        line.strip()
        for line in workflow_text.splitlines()
        if line.strip().startswith("docker push ")
    ]
    latest_pushes = [line for line in push_lines if ":latest" in line]
    assert latest_pushes == ["docker push m3rrym4n/smoke-shack:latest"]

    assert "git tag --points-at HEAD --list 'v[0-9]*'" in job_text
    assert "awk 'index($0, \"-\") == 0'" in job_text
    assert "semantic-release" not in job_text
