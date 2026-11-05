from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base, make_engine, make_session_factory
from app.ha import HAStatus
from app.models import Equipment
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
            )
        )
        session.commit()
    return factory


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(datetime(2026, 10, 16, 16, 57, 3, tzinfo=UTC))
