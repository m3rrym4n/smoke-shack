from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

import app.api
from app.config import Settings


def test_status_reads_build_version_from_file(
    sessions: sessionmaker[Session], monkeypatch, tmp_path: Path
) -> None:
    build_info = tmp_path / "build_info.txt"
    build_info.write_text("2.3.0-dev.4\n", encoding="utf-8")
    monkeypatch.setattr(app.api, "BUILD_INFO_PATH", build_info)

    with TestClient(app.api.create_app(Settings(), sessions)) as client:
        assert client.get("/status").json()["version"] == "2.3.0-dev.4"


def test_status_uses_dev_when_build_version_file_is_missing(
    sessions: sessionmaker[Session], monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(app.api, "BUILD_INFO_PATH", tmp_path / "missing.txt")

    with TestClient(app.api.create_app(Settings(), sessions)) as client:
        assert client.get("/status").json()["version"] == "dev"
