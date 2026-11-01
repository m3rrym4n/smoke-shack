from __future__ import annotations

import pytest

from app.config import HAConnection, Settings


def test_supervisor_uses_data_paths_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPERVISOR_TOKEN", "supervisor-secret")
    monkeypatch.delenv("DATABASE_PATH", raising=False)
    monkeypatch.delenv("PHOTO_DIR", raising=False)

    settings = Settings.from_env()

    assert settings.database_path == "/data/smoke-shack.db"
    assert settings.photo_dir == "/data/photos"


@pytest.mark.parametrize(
    ("variable", "value", "attribute"),
    [
        ("DATABASE_PATH", "/custom/database.db", "database_path"),
        ("PHOTO_DIR", "/custom/photos", "photo_dir"),
    ],
)
def test_explicit_data_path_wins_with_supervisor(
    monkeypatch: pytest.MonkeyPatch, variable: str, value: str, attribute: str
) -> None:
    monkeypatch.setenv("SUPERVISOR_TOKEN", "supervisor-secret")
    monkeypatch.setenv(variable, value)

    assert getattr(Settings.from_env(), attribute) == value


def test_empty_data_paths_use_supervisor_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPERVISOR_TOKEN", "supervisor-secret")
    monkeypatch.setenv("DATABASE_PATH", "")
    monkeypatch.setenv("PHOTO_DIR", "")

    settings = Settings.from_env()

    assert settings.database_path == "/data/smoke-shack.db"
    assert settings.photo_dir == "/data/photos"


def test_data_paths_keep_old_defaults_without_supervisor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SUPERVISOR_TOKEN", raising=False)
    monkeypatch.delenv("DATABASE_PATH", raising=False)
    monkeypatch.delenv("PHOTO_DIR", raising=False)

    settings = Settings.from_env()

    assert settings.database_path == "smoke-stack.db"
    assert settings.photo_dir == "photos"


def test_new_grill_name_wins_when_both_are_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SMOKE_SHACK_GRILL_NAME", "New name")
    monkeypatch.setenv("SMOKE_STACK_GRILL_NAME", "Old name")

    assert Settings.from_env().grill_name == "New name"


def test_old_grill_name_works_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SMOKE_SHACK_GRILL_NAME", raising=False)
    monkeypatch.setenv("SMOKE_STACK_GRILL_NAME", "Old name")

    assert Settings.from_env().grill_name == "Old name"


def test_missing_grill_names_give_empty_string(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SMOKE_SHACK_GRILL_NAME", raising=False)
    monkeypatch.delenv("SMOKE_STACK_GRILL_NAME", raising=False)

    assert Settings.from_env().grill_name == ""


def test_empty_new_grill_name_falls_back_to_old_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SMOKE_SHACK_GRILL_NAME", "")
    monkeypatch.setenv("SMOKE_STACK_GRILL_NAME", "Old name")

    assert Settings.from_env().grill_name == "Old name"


@pytest.mark.parametrize(
    ("base_url", "websocket_url", "template_url", "host"),
    [
        (
            "http://ha:8123",
            "ws://ha:8123/api/websocket",
            "http://ha:8123/api/template",
            "ha",
        ),
        (
            "https://ha.example.com",
            "wss://ha.example.com/api/websocket",
            "https://ha.example.com/api/template",
            "ha.example.com",
        ),
    ],
)
def test_direct_connection_urls(
    base_url: str, websocket_url: str, template_url: str, host: str
) -> None:
    connection = Settings(ha_url=base_url, ha_token="direct-secret").ha_connection

    assert connection == HAConnection(websocket_url, template_url, "direct-secret", host)


def test_supervisor_connection() -> None:
    connection = Settings(supervisor_token="supervisor-secret").ha_connection

    assert connection == HAConnection(
        "ws://supervisor/core/websocket",
        "http://supervisor/core/api/template",
        "supervisor-secret",
        "supervisor",
    )


def test_supervisor_token_is_read_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPERVISOR_TOKEN", "supervisor-secret")

    connection = Settings.from_env().ha_connection

    assert connection is not None
    assert connection.token == "supervisor-secret"


@pytest.mark.parametrize(
    ("ha_url", "ha_token"),
    [("http://ha:8123", ""), ("", "direct-secret")],
)
def test_partial_direct_config_uses_supervisor(ha_url: str, ha_token: str) -> None:
    connection = Settings(
        ha_url=ha_url,
        ha_token=ha_token,
        supervisor_token="supervisor-secret",
    ).ha_connection

    assert connection is not None
    assert connection.host == "supervisor"
    assert connection.token == "supervisor-secret"


def test_complete_direct_config_wins_over_supervisor() -> None:
    connection = Settings(
        ha_url="http://ha:8123",
        ha_token="direct-secret",
        supervisor_token="supervisor-secret",
    ).ha_connection

    assert connection is not None
    assert connection.host == "ha"
    assert connection.token == "direct-secret"


def test_no_connection_configured() -> None:
    assert Settings().ha_connection is None


def test_tokens_are_hidden_from_settings_repr() -> None:
    rendered = repr(
        Settings(ha_token="direct-secret", supervisor_token="supervisor-secret")
    )

    assert "direct-secret" not in rendered
    assert "supervisor-secret" not in rendered
