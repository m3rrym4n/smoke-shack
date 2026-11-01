from pathlib import Path

import yaml

WORKFLOW_PATH = Path(".forgejo/workflows/main-release.yml")


def test_main_release_syncs_main_into_dev() -> None:
    workflow_text = WORKFLOW_PATH.read_text()
    workflow = yaml.safe_load(workflow_text)
    sync_job = workflow["jobs"]["sync-dev"]
    job_text = "\n".join(step.get("run", "") for step in sync_job["steps"])

    assert sync_job["needs"] == "release"
    assert "github.ref_name == 'main'" in sync_job["if"]
    assert sync_job["steps"][0]["with"]["fetch-depth"] == 0
    assert "git fetch origin main dev" in job_text

    ancestor_check = "git merge-base --is-ancestor origin/main origin/dev"
    merge = 'git merge --no-ff origin/main -m "chore: sync main into dev"'
    assert ancestor_check in job_text
    assert merge in job_text
    assert job_text.index(ancestor_check) < job_text.index(merge)

    assert "git merge --abort" in job_text
    assert "git push origin HEAD:dev" in job_text
    assert "--force" not in job_text
    assert "+" not in job_text
    assert "gh " not in job_text
