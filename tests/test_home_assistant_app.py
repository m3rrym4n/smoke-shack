from pathlib import Path

import yaml


def test_home_assistant_app_metadata() -> None:
    repository = yaml.safe_load(Path("repository.yaml").read_text())
    config = yaml.safe_load(Path("smoke-shack/config.yaml").read_text())

    assert repository["name"] == "Smoke-Shack"
    assert config["image"] == "m3rrym4n/smoke-shack"
    assert config["ingress"] is True
    assert config["ingress_port"] == 8000
    assert config["ingress_stream"] is True
    assert config["homeassistant_api"] is True
    assert isinstance(config["version"], str)
    assert config["version"]
