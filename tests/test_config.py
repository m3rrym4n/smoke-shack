from __future__ import annotations

from app.config import Settings


def test_new_grill_name_wins_when_both_are_set(monkeypatch) -> None:
    monkeypatch.setenv("SMOKE_SHACK_GRILL_NAME", "New name")
    monkeypatch.setenv("SMOKE_STACK_GRILL_NAME", "Old name")

    assert Settings.from_env().grill_name == "New name"


def test_old_grill_name_works_alone(monkeypatch) -> None:
    monkeypatch.delenv("SMOKE_SHACK_GRILL_NAME", raising=False)
    monkeypatch.setenv("SMOKE_STACK_GRILL_NAME", "Old name")

    assert Settings.from_env().grill_name == "Old name"


def test_missing_grill_names_give_empty_string(monkeypatch) -> None:
    monkeypatch.delenv("SMOKE_SHACK_GRILL_NAME", raising=False)
    monkeypatch.delenv("SMOKE_STACK_GRILL_NAME", raising=False)

    assert Settings.from_env().grill_name == ""


def test_empty_new_grill_name_falls_back_to_old_name(monkeypatch) -> None:
    monkeypatch.setenv("SMOKE_SHACK_GRILL_NAME", "")
    monkeypatch.setenv("SMOKE_STACK_GRILL_NAME", "Old name")

    assert Settings.from_env().grill_name == "Old name"
