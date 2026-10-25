from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.models import Spice


def seed_spices(factory: sessionmaker[Session]) -> None:
    seed_path = Path(__file__).with_name("spices.json")
    entries: list[dict[str, object]] = json.loads(seed_path.read_text())
    with factory() as session:
        for entry in entries:
            brand = str(entry["brand"])
            name = str(entry["name"])
            exists = session.scalar(
                select(Spice.id).where(
                    func.lower(Spice.brand) == brand.lower(),
                    func.lower(Spice.name) == name.lower(),
                )
            )
            if exists is None:
                session.add(Spice(**entry))
        session.commit()
