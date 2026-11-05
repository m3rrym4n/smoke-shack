from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


class GrillProfileError(RuntimeError):
    """Raised when a grill mapping profile cannot be loaded."""


class EntityRole(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str = Field(min_length=1)
    domain: str = Field(min_length=1)
    optional: bool = False


class DeviceMatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    manufacturer: str = Field(min_length=1)
    model: str = Field(min_length=1)


class ChannelProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=1)
    role: Literal["pit", "meat"]
    label: str = Field(min_length=1)
    source: EntityRole
    target: EntityRole | None = None


class GrillProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    maker: str = Field(min_length=1)
    model: str = Field(min_length=1)
    type: Literal["pellet"]
    fuel_type: str = Field(min_length=1)
    units: Literal["F", "C"]
    device_match: DeviceMatch
    channels: tuple[ChannelProfile, ...] = Field(min_length=1)
    power: EntityRole
    heating: EntityRole
    lid_open: EntityRole
    door_open: EntityRole
    error: EntityRole
    last_reported: EntityRole
    cook_start: EntityRole

    @field_validator("channels")
    @classmethod
    def unique_channel_keys(
        cls, channels: tuple[ChannelProfile, ...]
    ) -> tuple[ChannelProfile, ...]:
        keys = [channel.key for channel in channels]
        if len(keys) != len(set(keys)):
            raise ValueError("channel keys must be unique")
        return channels


@dataclass(frozen=True)
class DeviceEntity:
    entity_id: str
    domain: str
    unique_id_suffix: str | None = None
    original_name: str | None = None


@dataclass(frozen=True)
class ResolvedChannel:
    key: str
    role: Literal["pit", "meat"]
    label: str
    source_entity_id: str
    target_entity_id: str | None


@dataclass(frozen=True)
class Resolution:
    channels: tuple[ResolvedChannel, ...]
    missing_roles: tuple[str, ...]


def load_grill_profiles(directory: str | Path) -> tuple[GrillProfile, ...]:
    profile_directory = Path(directory)
    try:
        paths = sorted(profile_directory.glob("*.yaml"))
    except OSError as exc:
        raise GrillProfileError(
            f"Cannot read grill profile directory {profile_directory}: {exc}"
        ) from exc

    if not paths:
        raise GrillProfileError(f"No grill profiles found in {profile_directory}")

    profiles: list[GrillProfile] = []
    ids: set[str] = set()
    for path in paths:
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
            profile = GrillProfile.model_validate(raw)
        except (OSError, yaml.YAMLError, ValidationError) as exc:
            raise GrillProfileError(f"Malformed grill profile {path}: {exc}") from exc
        if profile.id in ids:
            raise GrillProfileError(f"Duplicate grill profile id {profile.id!r} in {path}")
        ids.add(profile.id)
        profiles.append(profile)
    return tuple(profiles)


def resolve_channels(profile: GrillProfile, entities: Iterable[DeviceEntity]) -> Resolution:
    available = tuple(entities)
    resolved: list[ResolvedChannel] = []
    missing: list[str] = []
    for channel in profile.channels:
        source = _find_entity(channel.source, available)
        target = _find_entity(channel.target, available) if channel.target else None
        if source is None or (
            channel.target is not None and not channel.target.optional and target is None
        ):
            missing.append(channel.key)
            continue
        resolved.append(
            ResolvedChannel(
                key=channel.key,
                role=channel.role,
                label=channel.label,
                source_entity_id=source.entity_id,
                target_entity_id=target.entity_id if target else None,
            )
        )
    return Resolution(tuple(resolved), tuple(missing))


def _find_entity(
    role: EntityRole | None, entities: tuple[DeviceEntity, ...]
) -> DeviceEntity | None:
    if role is None:
        return None
    for entity in entities:
        if entity.domain != role.domain:
            continue
        identifiers = (entity.unique_id_suffix, entity.original_name)
        if any(
            identifier and _has_stable_suffix(identifier, role.role) for identifier in identifiers
        ):
            return entity
    return None


def _has_stable_suffix(identifier: str, role: str) -> bool:
    normalized = identifier.casefold().replace(" ", "_")
    expected = role.casefold()
    return normalized == expected or normalized.endswith(f"_{expected}")
