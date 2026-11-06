from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base, make_engine, make_session_factory
from app.ha import HAStatus
from app.models import Channel, Equipment
from app.service import GrillSnapshot


@dataclass
class FakeClock:
    current: datetime

    def now(self) -> datetime:
        return self.current

    def advance(self, **kwargs: float) -> datetime:
        self.current += timedelta(**kwargs)
        return self.current


class FakeHAClient:
    def __init__(self, snapshots: list[GrillSnapshot] | None = None) -> None:
        self.items = snapshots or []
        self.status = HAStatus(configured=True)

    async def snapshots(self) -> AsyncIterator[GrillSnapshot]:
        for snapshot in self.items:
            yield snapshot


@pytest.fixture
def sessions(tmp_path: Path) -> sessionmaker[Session]:
    engine = make_engine(str(tmp_path / "test.db"))
    Base.metadata.create_all(engine)
    factory = make_session_factory(engine)
    with factory() as session:
        session.add(
            Equipment(
                nickname="Grill",
                type="pellet",
                fuel_type="pellets",
                units="F",
                connected=True,
            )
        )
        session.commit()
    return factory


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(datetime(2026, 10, 16, 16, 57, 3, tzinfo=UTC))


@pytest.fixture
def masterbuilt_gravity_800_snapshot() -> GrillSnapshot:
    """Reusable five-channel snapshot for Smoke Shack and grill-sim scenarios."""
    return GrillSnapshot(
        pit_temp=300,
        setpoint=300,
        probe1=155,
        probe2=160,
        probe1_target=195,
        probe2_target=200,
        extra_probes={"probe3": 165, "probe4": 170},
        extra_probe_targets={"probe3": 205, "probe4": 210},
        fire_state="Running",
        power_state="On",
        hvac_mode="heat",
        startup_ends_at_setpoint=True,
    )


def add_channels(
    sessions: sessionmaker[Session], keys: tuple[str, ...] = ("pit", "probe1", "probe2")
) -> None:
    with sessions() as session:
        equipment = session.query(Equipment).one()
        for position, key in enumerate(keys):
            session.add(
                Channel(
                    equipment_id=equipment.id,
                    key=key,
                    role="pit" if key == "pit" else "meat",
                    label=key.title(),
                    source_entity=f"sensor.{key}",
                    target_entity=f"climate.{key}",
                    position=position,
                )
            )
        session.commit()
