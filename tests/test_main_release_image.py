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
    assert "gh " not in job_text

    push_lines = [
        line.strip()
        for line in job_text.splitlines()
        if line.strip().startswith("docker push ")
    ]
    zot_registry = "192." + "168.1.73:5050"
    assert push_lines == [
        f'docker push "{zot_registry}/smoke-shack/smoke-shack:${{RELEASE_VERSION}}"'
    ]

    assert "git tag --points-at HEAD --list 'v[0-9]*'" in job_text
    assert "awk 'index($0, \"-\") == 0'" in job_text
    assert "semantic-release" not in job_text

    binfmt = "tonistiigi/binfmt:qemu-v9.2.2 --install arm64"
    amd64_build = "--platform linux/amd64"
    arm64_build = "--platform linux/arm64"
    amd64_scan = '"smoke-shack-scan:amd64-${RELEASE_VERSION}"'
    arm64_scan = '"smoke-shack-scan:arm64-${RELEASE_VERSION}"'
    multi_platform_push = "--platform linux/amd64,linux/arm64"
    first_push = job_text.index("--push")

    assert job_text.index(binfmt) < job_text.index("docker buildx create")
    assert job_text.index("docker buildx create") < job_text.index(amd64_build)
    assert job_text.index(amd64_build) < job_text.index(amd64_scan)
    assert job_text.index(arm64_build) < job_text.index(arm64_scan)
    assert job_text.index(amd64_scan) < first_push
    assert job_text.index(arm64_scan) < first_push
    assert multi_platform_push in job_text
    assert 'm3rrym4n/smoke-shack:${RELEASE_VERSION}' in job_text
    assert "m3rrym4n/smoke-shack:latest" in job_text

    inspect_start = job_text.index("docker buildx imagetools inspect")
    inspect_end = job_text.index(binfmt)
    skip_check = job_text[inspect_start:inspect_end]
    assert "linux/amd64" in skip_check
    assert "linux/arm64" in skip_check
