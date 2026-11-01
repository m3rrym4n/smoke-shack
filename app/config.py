from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class EntityConfig:
    pit_climate: str
    pit_temp: str
    probe1_temp: str
    probe2_temp: str
    probe1_connection: str
    probe2_connection: str
    probe1_climate: str
    probe2_climate: str
    fire_state: str
    power_state: str
    warning: str
    extra_probes: tuple[str, ...] = ()

    @property
    def all(self) -> set[str]:
        return {
            self.pit_climate,
            self.pit_temp,
            self.probe1_temp,
            self.probe2_temp,
            self.probe1_connection,
            self.probe2_connection,
            self.probe1_climate,
            self.probe2_climate,
            self.fire_state,
            self.power_state,
            self.warning,
            *self.extra_probes,
        }


@dataclass(frozen=True)
class Settings:
    ha_url: str = ""
    ha_token: str = ""
    database_path: str = "smoke-stack.db"
    photo_dir: str = "photos"
    grill_name: str = ""
    sample_interval_seconds: int = 10
    data_gap_event_min_seconds: int = 120
    ha_ws_max_size_bytes: int = 67_108_864
    incomplete_timeout_minutes: int = 90
    tz: str = "America/Los_Angeles"
    entities_path: str = "config/entities.yaml"
    restore_max_bytes: int = 500 * 1024 * 1024

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            ha_url=os.getenv("HA_URL", ""),
            ha_token=os.getenv("HA_TOKEN", ""),
            database_path=os.getenv("DATABASE_PATH", "smoke-stack.db"),
            photo_dir=os.getenv("PHOTO_DIR", "photos"),
            grill_name=os.getenv("SMOKE_SHACK_GRILL_NAME")
            or os.getenv("SMOKE_STACK_GRILL_NAME")
            or "",
            sample_interval_seconds=int(os.getenv("SAMPLE_INTERVAL_SECONDS", "10")),
            data_gap_event_min_seconds=int(os.getenv("DATA_GAP_EVENT_MIN_SECONDS", "120")),
            ha_ws_max_size_bytes=int(os.getenv("HA_WS_MAX_SIZE_BYTES", "67108864")),
            incomplete_timeout_minutes=int(os.getenv("INCOMPLETE_TIMEOUT_MINUTES", "90")),
            tz=os.getenv("TZ", "America/Los_Angeles"),
            entities_path=os.getenv("ENTITIES_CONFIG", "config/entities.yaml"),
            restore_max_bytes=int(os.getenv("RESTORE_MAX_BYTES", str(500 * 1024 * 1024))),
        )

    def load_entities(self) -> EntityConfig:
        raw = yaml.safe_load(Path(self.entities_path).read_text())
        return EntityConfig(
            pit_climate=str(raw["pit_climate"]),
            pit_temp=str(raw["pit_temp"]),
            probe1_temp=str(raw["probe1_temp"]),
            probe2_temp=str(raw["probe2_temp"]),
            probe1_connection=str(raw["probe1_connection"]),
            probe2_connection=str(raw["probe2_connection"]),
            probe1_climate=str(raw["probe1_climate"]),
            probe2_climate=str(raw["probe2_climate"]),
            fire_state=str(raw["fire_state"]),
            power_state=str(raw["power_state"]),
            warning=str(raw["warning"]),
            extra_probes=tuple(raw.get("extra_probes", [])),
        )
