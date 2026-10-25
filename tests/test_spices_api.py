from __future__ import annotations

from conftest import FakeHAClient
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.api import create_app
from app.config import Settings
from app.models import Spice
from app.seed import seed_spices


def test_spice_seed_is_idempotent_and_preserves_edits(
    sessions: sessionmaker[Session],
) -> None:
    seed_spices(sessions)
    with sessions() as session:
        count = session.scalar(select(func.count()).select_from(Spice))
        gospel = session.scalar(
            select(Spice).where(Spice.name == "The Holy Gospel BBQ Rub")
        )
        assert gospel is not None
        gospel.price = 7.25
        gospel.size_oz = 14
        session.commit()

    seed_spices(sessions)
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(Spice)) == count == 16
        gospel = session.scalar(
            select(Spice).where(Spice.name == "The Holy Gospel BBQ Rub")
        )
        assert gospel is not None
        assert float(gospel.price or 0) == 7.25
        assert float(gospel.size_oz or 0) == 14


def test_spice_crud_validation_filter_order_and_unique(
    sessions: sessionmaker[Session],
) -> None:
    with TestClient(create_app(Settings(), sessions, FakeHAClient())) as client:
        zulu = client.post(
            "/api/spices",
            json={"brand": "Zulu", "name": "Sweet", "price": 5.5, "size_oz": 10},
        )
        alpha = client.post(
            "/api/spices", json={"brand": "Alpha", "name": "Hot", "notes": "Spicy"}
        )
        assert zulu.status_code == alpha.status_code == 201
        assert zulu.json()["price"] == 5.5
        assert zulu.json()["size_oz"] == 10
        assert alpha.json()["is_custom"] is False

        rows = client.get("/api/spices").json()
        keys = [(row["brand"].lower(), row["name"].lower()) for row in rows]
        assert keys == sorted(keys)
        assert client.get("/api/spices?brand=zULu").json() == [zulu.json()]
        assert client.get(f"/api/spices/{zulu.json()['id']}").json() == zulu.json()

        patched = client.patch(
            f"/api/spices/{zulu.json()['id']}", json={"price": 6, "notes": "New"}
        )
        assert patched.status_code == 200
        assert patched.json()["price"] == 6
        assert patched.json()["notes"] == "New"

        duplicate = client.post(
            "/api/spices", json={"brand": "zULU", "name": "sWEET"}
        )
        assert duplicate.status_code == 409
        assert client.post(
            "/api/spices", json={"brand": "Bad", "name": "Price", "price": -1}
        ).status_code == 422
        assert client.post(
            "/api/spices", json={"brand": "Bad", "name": "Size", "size_oz": 0}
        ).status_code == 422

        assert client.delete(f"/api/spices/{alpha.json()['id']}").status_code == 204
        assert client.get(f"/api/spices/{alpha.json()['id']}").status_code == 404


def test_custom_entries_and_protected_custom_blend(
    sessions: sessionmaker[Session],
) -> None:
    with TestClient(create_app(Settings(), sessions, FakeHAClient())) as client:
        custom = next(
            row for row in client.get("/api/spices").json() if row["name"] == "Custom blend"
        )
        assert custom["is_custom"] is True
        assert client.delete(f"/api/spices/{custom['id']}").status_code == 409
        assert client.patch(
            f"/api/spices/{custom['id']}", json={"name": "Renamed"}
        ).status_code == 400

        created = client.post("/api/spices", json={"brand": "custom", "name": "House mix"})
        assert created.status_code == 201
        assert created.json()["is_custom"] is True
