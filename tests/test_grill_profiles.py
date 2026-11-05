from pathlib import Path

import pytest

from app.api import create_app
from app.config import Settings
from app.grill_profiles import (
    DeviceEntity,
    GrillProfileError,
    load_grill_profiles,
    resolve_channels,
)

PROFILE_DIRECTORY = Path("config/grill_profiles")


def _mock_entities(*, include_probe4: bool = True) -> list[DeviceEntity]:
    roles = [
        ("sensor", "grill_temp_f"),
        ("number", "target_temp_f"),
        ("sensor", "probe1_temp_f"),
        ("sensor", "probe1_target_f"),
        ("sensor", "probe2_temp_f"),
        ("sensor", "probe2_target_f"),
        ("sensor", "probe3_temp_f"),
        ("sensor", "probe3_target_f"),
    ]
    if include_probe4:
        roles.extend((("sensor", "probe4_temp_f"), ("sensor", "probe4_target_f")))
    return [
        DeviceEntity(
            entity_id=f"{domain}.masterbuilt_{role}",
            domain=domain,
            unique_id_suffix=f"mock_{role}",
            original_name=role.replace("_", " "),
        )
        for domain, role in roles
    ]


def test_gravity_800_profile_resolves_all_channels() -> None:
    (profile,) = load_grill_profiles(PROFILE_DIRECTORY)

    result = resolve_channels(profile, _mock_entities())

    assert [channel.key for channel in result.channels] == [
        "pit",
        "probe1",
        "probe2",
        "probe3",
        "probe4",
    ]
    assert result.missing_roles == ()
    assert all(channel.target_entity_id is not None for channel in result.channels)


def test_missing_probe4_returns_other_channels_and_reports_role() -> None:
    (profile,) = load_grill_profiles(PROFILE_DIRECTORY)

    result = resolve_channels(profile, _mock_entities(include_probe4=False))

    assert [channel.key for channel in result.channels] == ["pit", "probe1", "probe2", "probe3"]
    assert result.missing_roles == ("probe4",)


def test_malformed_profile_has_clear_filename_error(tmp_path: Path) -> None:
    path = tmp_path / "broken.yaml"
    path.write_text("id: broken\nchannels: nope\n", encoding="utf-8")

    with pytest.raises(GrillProfileError, match=r"Malformed grill profile .*broken.yaml"):
        load_grill_profiles(tmp_path)


def test_malformed_profile_fails_app_startup(tmp_path: Path) -> None:
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    path = profiles / "broken.yaml"
    path.write_text("id: broken\nchannels: nope\n", encoding="utf-8")

    with pytest.raises(GrillProfileError, match=r"Malformed grill profile .*broken.yaml"):
        create_app(
            Settings(
                database_path=str(tmp_path / "smoke-shack.db"),
                grill_profiles_path=str(profiles),
            )
        )
