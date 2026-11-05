from pathlib import Path

import pytest

from app.api import create_app
from app.config import Settings
from app.grill_profiles import (
    DeviceEntity,
    GrillProfile,
    GrillProfileError,
    load_grill_profiles,
    resolve_channels,
)

PROFILE_DIRECTORY = Path("config/grill_profiles")


def _mock_entities(*, include_probe4: bool = True) -> list[DeviceEntity]:
    roles = [
        ("sensor", "grill_temp"),
        ("sensor", "target_temp"),
        ("sensor", "probe1_temp"),
        ("sensor", "probe2_temp"),
        ("sensor", "probe3_temp"),
    ]
    if include_probe4:
        roles.append(("sensor", "probe4_temp"))
    return [
        DeviceEntity(
            entity_id=f"{domain}.mock_masterbuilt_gravity_series_800_1_{role}",
            domain=domain,
            unique_id_suffix=f"mock_masterbuilt_gravity_series_800_1_{role}",
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
    assert result.channels[0].target_entity_id == (
        "sensor.mock_masterbuilt_gravity_series_800_1_target_temp"
    )
    assert all(channel.target_entity_id is None for channel in result.channels[1:])


def test_missing_probe4_returns_other_channels_and_reports_role() -> None:
    (profile,) = load_grill_profiles(PROFILE_DIRECTORY)

    result = resolve_channels(profile, _mock_entities(include_probe4=False))

    assert [channel.key for channel in result.channels] == ["pit", "probe1", "probe2", "probe3"]
    assert result.missing_roles == ("probe4",)


def test_units_must_use_database_value() -> None:
    (profile,) = load_grill_profiles(PROFILE_DIRECTORY)

    with pytest.raises(ValueError, match="Input should be 'F' or 'C'"):
        GrillProfile.model_validate({**profile.model_dump(), "units": "fahrenheit"})


def test_docker_image_copies_grill_profiles() -> None:
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")

    assert "COPY config ./config" in dockerfile


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
