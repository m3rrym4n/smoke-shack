from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict

from app.models import Sample


@dataclass(frozen=True)
class SampleChannel:
    key: str
    label: str
    role: str
    value: float | None
    target: float | None


class CompatibilityValues(TypedDict):
    pit_temp: float | None
    setpoint: float | None
    probe1: float | None
    probe2: float | None
    probe1_target: float | None
    probe2_target: float | None
    extra_probes: dict[str, float | None]


def sample_channels(sample: Sample) -> list[SampleChannel]:
    """Return raw channel readings in equipment order, without calibration."""
    return [
        SampleChannel(
            key=reading.channel.key,
            label=reading.channel.label,
            role=reading.channel.role,
            value=reading.value,
            target=reading.target,
        )
        for reading in sorted(
            sample.channel_readings,
            key=lambda reading: (reading.channel.position, reading.channel.id),
        )
    ]


def channel_map(sample: Sample) -> dict[str, SampleChannel]:
    return {channel.key: channel for channel in sample_channels(sample)}


def compatibility_values(sample: Sample) -> CompatibilityValues:
    """Build the legacy sample fields from channel readings.

    The fallback keeps model-only callers and pre-migration test fixtures usable. Upgraded
    databases always have channel readings, which take precedence over the dual-write columns.
    """
    channels = sample_channels(sample)
    if not channels:
        return {
            "pit_temp": sample.pit_temp,
            "setpoint": sample.setpoint,
            "probe1": sample.probe1,
            "probe2": sample.probe2,
            "probe1_target": sample.probe1_target,
            "probe2_target": sample.probe2_target,
            "extra_probes": sample.extra_probes or {},
        }
    by_key = {channel.key: channel for channel in channels}

    def reading(key: str, field: str) -> float | None:
        channel = by_key.get(key)
        return getattr(channel, field) if channel is not None else None

    return {
        "pit_temp": reading("pit", "value"),
        "setpoint": reading("pit", "target"),
        "probe1": reading("probe1", "value"),
        "probe2": reading("probe2", "value"),
        "probe1_target": reading("probe1", "target"),
        "probe2_target": reading("probe2", "target"),
        "extra_probes": {
            channel.key: channel.value
            for channel in channels
            if channel.key not in {"pit", "probe1", "probe2"}
        },
    }


def channel_payload(sample: Sample) -> list[dict[str, str | float | None]]:
    return [
        {
            "key": channel.key,
            "label": channel.label,
            "role": channel.role,
            "value": channel.value,
            "target": channel.target,
        }
        for channel in sample_channels(sample)
    ]
