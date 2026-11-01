from __future__ import annotations

from datetime import UTC, date, datetime

from conftest import FakeHAClient
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.api import create_app
from app.config import Settings
from app.models import Cook


def test_meat_crud_filter_and_sort(sessions: sessionmaker[Session]) -> None:
    with TestClient(create_app(Settings(), sessions, FakeHAClient())) as client:
        older = client.post(
            "/api/meat",
            json={
                "type": "Pork butt",
                "pounds": 8.5,
                "price_per_pound": 2.49,
                "store": "Butcher",
                "purchased_on": "2026-10-15",
            },
        )
        newer = client.post(
            "/api/meat",
            json={
                "type": "Beef brisket",
                "pounds": 12,
                "price_per_pound": 5,
                "purchased_on": "2026-10-16",
            },
        )

        assert older.status_code == 201
        assert older.json()["cooked"] is False
        assert isinstance(older.json()["pounds"], float)
        assert isinstance(older.json()["price_per_pound"], float)
        assert [row["id"] for row in client.get("/api/meat").json()] == [
            newer.json()["id"],
            older.json()["id"],
        ]
        assert client.get("/api/meat?type=PORK").json() == [older.json()]
        assert client.get(f"/api/meat/{older.json()['id']}").json() == older.json()

        patched = client.patch(
            f"/api/meat/{older.json()['id']}", json={"store": "Market", "pounds": 9}
        )
        assert patched.status_code == 200
        assert patched.json()["store"] == "Market"
        assert patched.json()["pounds"] == 9

        cooked = client.patch(f"/api/meat/{older.json()['id']}", json={"cooked": True})
        assert cooked.status_code == 200
        assert cooked.json()["cooked"] is True
        assert client.get("/api/meat?cooked=true").json() == [cooked.json()]
        assert client.get("/api/meat?cooked=false").json() == [newer.json()]
        assert client.get("/api/meat?type=pork&cooked=true").json() == [cooked.json()]
        assert client.get("/api/meat?type=beef&cooked=true").json() == []

        uncooked = client.patch(f"/api/meat/{older.json()['id']}", json={"cooked": False})
        assert uncooked.status_code == 200
        assert uncooked.json()["cooked"] is False

        assert client.delete(f"/api/meat/{newer.json()['id']}").status_code == 204
        assert client.get(f"/api/meat/{newer.json()['id']}").json() == {
            "detail": "Meat not found"
        }


def test_meat_defaults_validation_and_referenced_delete(sessions: sessionmaker[Session]) -> None:
    with TestClient(create_app(Settings(), sessions, FakeHAClient())) as client:
        created = client.post(
            "/api/meat", json={"type": "Chicken", "pounds": 4, "price_per_pound": 0}
        )
        assert created.status_code == 201
        assert created.json()["purchased_on"] == date.today().isoformat()
        assert created.json()["cooked"] is False
        for payload in (
            {"type": "", "pounds": 1, "price_per_pound": 1},
            {"type": "   ", "pounds": 1, "price_per_pound": 1},
            {"type": "Pork", "pounds": 0, "price_per_pound": 1},
            {"type": "Pork", "pounds": 1, "price_per_pound": -1},
        ):
            assert client.post("/api/meat", json=payload).status_code == 422

        meat_id = created.json()["id"]
        with sessions() as session:
            session.add(Cook(started_at=datetime.now(UTC), meat_id=meat_id))
            session.commit()
        conflict = client.delete(f"/api/meat/{meat_id}")
        assert conflict.status_code == 409
        assert conflict.json() == {"detail": "Meat is referenced by a cook"}
        assert client.patch("/api/meat/9999", json={"store": "X"}).status_code == 404
        assert client.delete("/api/meat/9999").status_code == 404


def test_pellet_crud_sort_validation_and_referenced_delete(
    sessions: sessionmaker[Session],
) -> None:
    with TestClient(create_app(Settings(), sessions, FakeHAClient())) as client:
        zulu = client.post(
            "/api/pellets",
            json={
                "vendor": "Zulu",
                "product_name": "Oak",
                "price_per_pound": 1.25,
                "purchased_on": "2026-10-16",
            },
        )
        alpha = client.post(
            "/api/pellets",
            json={"vendor": "Alpha", "product_name": "Hickory", "price_per_pound": 0},
        )
        assert zulu.status_code == alpha.status_code == 201
        assert alpha.json()["purchased_on"] == date.today().isoformat()
        assert isinstance(zulu.json()["price_per_pound"], float)
        assert [row["vendor"] for row in client.get("/api/pellets").json()] == [
            "Alpha",
            "Zulu",
        ]
        pellet_id = zulu.json()["id"]
        assert client.get(f"/api/pellets/{pellet_id}").json() == zulu.json()
        patched = client.patch(f"/api/pellets/{pellet_id}", json={"product_name": "Blend"})
        assert patched.status_code == 200
        assert patched.json()["product_name"] == "Blend"

        for payload in (
            {"vendor": "", "product_name": "Oak", "price_per_pound": 1},
            {"vendor": "Zulu", "product_name": "", "price_per_pound": 1},
            {"vendor": "Zulu", "product_name": "Oak", "price_per_pound": -1},
        ):
            assert client.post("/api/pellets", json=payload).status_code == 422

        with sessions() as session:
            session.add(Cook(started_at=datetime.now(UTC), pellet_id=pellet_id))
            session.commit()
        assert client.delete(f"/api/pellets/{pellet_id}").status_code == 409
        assert client.get("/api/pellets/9999").json() == {"detail": "Pellet not found"}
        assert client.patch("/api/pellets/9999", json={"vendor": "X"}).status_code == 404
        assert client.delete("/api/pellets/9999").status_code == 404
        assert client.delete(f"/api/pellets/{alpha.json()['id']}").status_code == 204


def test_pellet_upc_bag_size_cost_and_filter(sessions: sessionmaker[Session]) -> None:
    base = {"vendor": "Bear Mountain", "product_name": "Oak", "price_per_pound": 1.23}
    with TestClient(create_app(Settings(), sessions, FakeHAClient())) as client:
        legacy = client.post("/api/pellets", json=base)
        assert legacy.status_code == 201
        assert legacy.json()["upc"] is None
        assert legacy.json()["bag_size_lb"] is None
        assert legacy.json()["bag_cost"] is None

        created = client.post(
            "/api/pellets",
            json={**base, "product_name": "Hickory", "upc": "0 12345-67890 5", "bag_size_lb": 20},
        )
        assert created.status_code == 201, created.text
        assert created.json()["upc"] == "012345678905"
        assert created.json()["bag_size_lb"] == 20
        assert created.json()["bag_cost"] == 24.6

        pellet_id = created.json()["id"]
        patched = client.patch(
            f"/api/pellets/{pellet_id}",
            json={"upc": "0000-0000", "bag_size_lb": 2.5},
        )
        assert patched.status_code == 200, patched.text
        assert patched.json()["upc"] == "00000000"
        assert patched.json()["bag_cost"] == 3.08
        assert client.get("/api/pellets?upc=0000-0000").json() == [patched.json()]
        assert client.get("/api/pellets?upc=012345678905").json() == []

        cleared = client.patch(f"/api/pellets/{pellet_id}", json={"upc": "", "bag_size_lb": None})
        assert cleared.status_code == 200
        assert cleared.json()["upc"] is None
        assert cleared.json()["bag_size_lb"] is None
        assert cleared.json()["bag_cost"] is None

        for upc in ("1234567", "123456789012345", "1234567A"):
            response = client.post("/api/pellets", json={**base, "upc": upc})
            assert response.status_code == 422
            assert "8 to 14 digits" in response.text
            assert client.patch(f"/api/pellets/{pellet_id}", json={"upc": upc}).status_code == 422
        for bag_size in (0, -1, 100.01, 101):
            assert (
                client.post("/api/pellets", json={**base, "bag_size_lb": bag_size}).status_code
                == 422
            )
            assert (
                client.patch(
                    f"/api/pellets/{pellet_id}", json={"bag_size_lb": bag_size}
                ).status_code
                == 422
            )
        assert client.get("/api/pellets?upc=not-a-upc").status_code == 422
