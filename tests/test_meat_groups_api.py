from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.api import create_app
from app.config import Settings
from app.models import Cook, Meat, MeatGroup, MeatGroupType


def _client(sessions: sessionmaker[Session], tmp_path: object) -> TestClient:
    return TestClient(
        create_app(
            settings=Settings(database_path=":memory:", photo_dir=str(tmp_path)),
            sessions=sessions,
        )
    )


def _meat(meat_type: str) -> Meat:
    return Meat(
        type=meat_type,
        pounds=Decimal("8.00"),
        price_per_pound=Decimal("2.00"),
        purchased_on=date(2026, 1, 1),
    )


def test_meat_group_crud_duplicate_and_ungrouped_types(
    sessions: sessionmaker[Session], tmp_path: object
) -> None:
    with sessions() as session:
        session.add_all([_meat("Pork Butt"), _meat("Chicken")])
        session.commit()

    with _client(sessions, tmp_path) as client:
        created = client.post("/api/meat-groups", json={"name": "Pork shoulder"})
        group_id = created.json()["id"]
        duplicate = client.post("/api/meat-groups", json={"name": " pork SHOULDER "})
        replaced = client.put(
            f"/api/meat-groups/{group_id}/types", json={"types": [" PORK BUTT "]}
        )
        listed = client.get("/api/meat-groups")
        renamed = client.patch(f"/api/meat-groups/{group_id}", json={"name": "Shoulder"})
        deleted = client.delete(f"/api/meat-groups/{group_id}")

    assert created.status_code == 201
    assert duplicate.status_code == 409
    assert replaced.json()["types"] == ["pork butt"]
    assert listed.json()["ungrouped_types"] == ["Chicken"]
    assert renamed.json()["name"] == "Shoulder"
    assert deleted.status_code == 204


def test_replacing_types_moves_members_and_deleting_group_preserves_meat_and_cook(
    sessions: sessionmaker[Session], tmp_path: object
) -> None:
    with sessions() as session:
        meat = _meat("Pork butt")
        first = MeatGroup(name="First")
        second = MeatGroup(name="Second")
        session.add_all([meat, first, second])
        session.flush()
        session.add(MeatGroupType(group_id=first.id, type_key="pork butt"))
        cook = Cook(
            started_at=datetime(2026, 1, 1, tzinfo=UTC),
            status="planned",
            meat_id=meat.id,
        )
        session.add(cook)
        session.commit()
        first_id, second_id, meat_id, cook_id = first.id, second.id, meat.id, cook.id

    with _client(sessions, tmp_path) as client:
        moved = client.put(
            f"/api/meat-groups/{second_id}/types", json={"types": ["Pork Butt"]}
        )
        groups = client.get("/api/meat-groups").json()["groups"]
        deleted = client.delete(f"/api/meat-groups/{second_id}")

    assert moved.status_code == 200
    assert next(group for group in groups if group["id"] == first_id)["types"] == []
    assert deleted.status_code == 204
    with sessions() as session:
        assert session.get(Meat, meat_id) is not None
        assert session.get(Cook, cook_id) is not None
