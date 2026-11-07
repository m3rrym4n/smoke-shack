from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.api import create_app
from app.config import Settings
from app.models import (
    Cook,
    Equipment,
    Event,
    Meat,
    Note,
    Pellet,
    Photo,
    Profile,
    Sample,
    Spice,
    cook_spices,
)


def _cook(started_at: datetime, **values: object) -> Cook:
    defaults: dict[str, object] = {
        "started_at": started_at,
        "ended_at": started_at + timedelta(hours=1),
        "status": "complete",
    }
    defaults.update(values)
    return Cook(**defaults)


def test_cook_list_and_detail_include_journal_and_linked_summaries(
    sessions: sessionmaker[Session],
) -> None:
    with sessions() as session:
        meat = Meat(
            type="Pork butt",
            pounds=Decimal("4.25"),
            price_per_pound=Decimal("3.20"),
            store="Butcher",
            purchased_on=date(2026, 10, 15),
        )
        pellet = Pellet(
            vendor="Bear Mountain",
            product_name="Hickory",
            price_per_pound=Decimal("1.40"),
            purchased_on=date(2026, 10, 1),
        )
        profile = Profile(name="Pulled Pork", keep_warm=False)
        session.add_all([meat, pellet, profile])
        session.flush()
        cook = _cook(
            datetime(2026, 10, 16, 16, 57, 3, tzinfo=UTC),
            meat_id=meat.id,
            pellet_id=pellet.id,
            profile_id=profile.id,
            rotisserie=True,
            seasonings="Salt",
            sauces="Vinegar",
            prep_time_minutes=20,
            results_text="Tender",
            setpoint_override=275,
            pellets_used_lb=2.5,
        )
        session.add(cook)
        session.commit()
        cook_id = cook.id

    with TestClient(create_app(Settings(), sessions)) as client:
        listed = client.get("/api/cooks").json()[0]
        detail = client.get(f"/api/cooks/{cook_id}").json()

    assert listed["meat"] == {
        "id": meat.id,
        "type": "Pork butt",
        "pounds": 4.25,
        "price_per_pound": 3.2,
        "store": "Butcher",
        "purchased_on": "2026-10-15",
    }
    assert listed["pellet"] == {
        "id": pellet.id,
        "type": "pellets",
        "vendor": "Bear Mountain",
        "product_name": "Hickory",
        "price_per_pound": 1.4,
    }
    assert listed["fuel"] == listed["pellet"]
    assert listed["fuel_id"] == pellet.id
    assert listed["profile_name"] == "Pulled Pork"
    assert listed["rotisserie"] is True
    assert listed["seasonings"] == "Salt"
    assert listed["sauces"] == "Vinegar"
    assert listed["prep_time_minutes"] == 20
    assert listed["results_text"] == "Tender"
    assert listed["setpoint_override"] == 275
    assert listed["pellets_used_lb"] == 2.5
    assert "cost" not in listed
    assert detail["cost"] == {"meat_cost": 13.6, "pellet_cost": 3.5}


def test_patch_cook_and_reject_unknown_reference(sessions: sessionmaker[Session]) -> None:
    started = datetime(2026, 10, 16, 16, 57, 3, tzinfo=UTC)
    with sessions() as session:
        meat = Meat(
            type="Brisket",
            pounds=Decimal("8.00"),
            price_per_pound=Decimal("5.00"),
            purchased_on=date(2026, 10, 16),
        )
        session.add(meat)
        session.add(cook := _cook(started))
        session.commit()
        meat_id, cook_id = meat.id, cook.id

    with TestClient(create_app(Settings(), sessions)) as client:
        response = client.patch(
            f"/api/cooks/{cook_id}",
            json={
                "meat_id": meat_id,
                "rotisserie": True,
                "seasonings": "Pepper",
                "prep_time_minutes": 15,
                "setpoint_override": 250,
                "exclude_from_stats": True,
            },
        )
        unknown = client.patch(f"/api/cooks/{cook_id}", json={"meat_id": 9999})

    assert response.status_code == 200
    assert response.json()["meat_id"] == meat_id
    assert response.json()["seasonings"] == "Pepper"
    assert response.json()["exclude_from_stats"] is True
    assert unknown.status_code == 422
    assert unknown.json() == {"detail": "Meat not found"}

    with sessions() as session:
        assert session.get(Cook, cook_id).exclude_from_stats is True


def test_patch_cook_records_grill_and_rejects_unknown_grill(
    sessions: sessionmaker[Session],
) -> None:
    started = datetime(2026, 10, 16, 16, 57, 3, tzinfo=UTC)
    with sessions() as session:
        grill = session.query(Equipment).one()
        grill.maker = "Masterbuilt"
        grill.model = "Gravity Series 800"
        session.add(cook := _cook(started, equipment_id=None))
        session.commit()
        grill_id, cook_id = grill.id, cook.id

    with TestClient(create_app(Settings(), sessions)) as client:
        saved = client.patch(f"/api/cooks/{cook_id}", json={"equipment_id": grill_id})
        unknown = client.patch(f"/api/cooks/{cook_id}", json={"equipment_id": 9999})

    assert saved.status_code == 200
    assert saved.json()["equipment_id"] == grill_id
    assert saved.json()["grill_manufacturer"] == "Masterbuilt"
    assert saved.json()["grill_model"] == "Gravity Series 800"
    assert unknown.status_code == 422
    assert unknown.json() == {"detail": "Equipment not found"}


def test_list_cooks_filters_and_paginates(sessions: sessionmaker[Session]) -> None:
    started = datetime(2026, 10, 16, 12, 0, tzinfo=UTC)
    with sessions() as session:
        meat = Meat(
            type="Ribs",
            pounds=Decimal("3.00"),
            price_per_pound=Decimal("4.00"),
            purchased_on=date(2026, 10, 16),
        )
        pellet = Pellet(
            vendor="Vendor",
            product_name="Blend",
            price_per_pound=Decimal("1.00"),
            purchased_on=date(2026, 10, 16),
        )
        session.add_all([meat, pellet])
        session.flush()
        session.add_all(
            [
                _cook(started, meat_id=meat.id, pellet_id=pellet.id, status="complete"),
                _cook(started + timedelta(hours=1), meat_id=meat.id, status="incomplete"),
                _cook(started + timedelta(hours=2), pellet_id=pellet.id, status="complete"),
            ]
        )
        active = _cook(started + timedelta(hours=3), ended_at=None, status="cook")
        session.add(active)
        session.flush()
        session.add(
            Sample(
                cook_id=active.id,
                ts=started + timedelta(hours=3, minutes=1),
                setpoint=275,
                extra_probes={},
            )
        )
        session.commit()
        meat_id, pellet_id, active_id = meat.id, pellet.id, active.id

    with TestClient(create_app(Settings(), sessions)) as client:
        all_cooks = client.get("/api/cooks").json()
        assert len(client.get(f"/api/cooks?meat_id={meat_id}").json()) == 2
        assert len(client.get(f"/api/cooks?pellet_id={pellet_id}").json()) == 2
        assert len(client.get("/api/cooks?status=incomplete").json()) == 1
        page = client.get("/api/cooks?limit=1&offset=1").json()
        assert page[0]["status"] == "complete"
        assert [cook["id"] for cook in client.get("/api/cooks?state=cook").json()] == [active_id]

    assert all_cooks[0]["id"] == active_id
    assert all_cooks[0]["current_setpoint"] == 275


def test_cook_list_includes_each_grill_and_allows_missing_equipment(
    sessions: sessionmaker[Session],
) -> None:
    started = datetime(2026, 10, 16, 12, 0, tzinfo=UTC)
    with sessions() as session:
        gmg = session.query(Equipment).one()
        gmg.maker = "Green Mountain Grills"
        gmg.model = "Daniel Boone"
        masterbuilt = Equipment(
            nickname="Patio Grill",
            maker="Masterbuilt",
            model="Gravity Series 800",
            type="charcoal",
            fuel_type="charcoal",
            units="F",
            connected=False,
        )
        session.add(masterbuilt)
        session.flush()
        session.add_all(
            [
                _cook(started, equipment_id=gmg.id),
                _cook(started + timedelta(hours=1), equipment_id=masterbuilt.id),
                _cook(started + timedelta(hours=2), equipment_id=None),
            ]
        )
        session.commit()

    with TestClient(create_app(Settings(), sessions)) as client:
        cooks = client.get("/api/cooks").json()

    assert [(cook["grill_manufacturer"], cook["grill_model"]) for cook in cooks] == [
        (None, None),
        ("Masterbuilt", "Gravity Series 800"),
        ("Green Mountain Grills", "Daniel Boone"),
    ]


def test_delete_cook_rejects_active_and_removes_children(
    sessions: sessionmaker[Session],
) -> None:
    started = datetime(2026, 10, 16, 16, 57, 3, tzinfo=UTC)
    with sessions() as session:
        active = _cook(started, ended_at=None, status="cook")
        finished = _cook(started - timedelta(hours=2))
        session.add_all([active, finished])
        session.flush()
        sample = Sample(cook_id=finished.id, ts=started, extra_probes={})
        event = Event(
            cook_id=finished.id,
            ts=started,
            kind="custom",
            source="user",
            title="Wrapped",
            data={},
        )
        session.add_all([sample, event])
        session.flush()
        session.add(Photo(cook_id=finished.id, event_id=event.id, path="photo.jpg"))
        session.add(
            Note(title="Remember", body="Good cook", scope="this_cook", cook_id=finished.id)
        )
        session.commit()
        active_id, finished_id = active.id, finished.id

    with TestClient(create_app(Settings(), sessions)) as client:
        conflict = client.delete(f"/api/cooks/{active_id}")
        deleted = client.delete(f"/api/cooks/{finished_id}")

    assert conflict.status_code == 409
    assert conflict.json() == {"detail": "Active cook cannot be deleted"}
    assert deleted.status_code == 204
    with sessions() as session:
        assert session.get(Cook, finished_id) is None
        for model in (Sample, Event, Photo):
            assert session.scalar(select(func.count()).select_from(model)) == 0
        note = session.scalar(select(Note))
        assert note is not None
        assert note.cook_id is None


def test_planned_cook_create_list_next_unlink_and_delete(
    sessions: sessionmaker[Session],
) -> None:
    with sessions() as session:
        meat = Meat(
            type="Brisket",
            pounds=Decimal("9.50"),
            price_per_pound=Decimal("4.00"),
            purchased_on=date(2026, 10, 16),
        )
        pellet = Pellet(
            vendor="CookinPellets",
            product_name="Perfect Mix",
            price_per_pound=Decimal("1.10"),
            purchased_on=date(2026, 10, 16),
        )
        session.add_all([meat, pellet])
        session.commit()
        meat_id, pellet_id = meat.id, pellet.id

    payload = {
        "state": "planned",
        "meat_id": meat_id,
        "pellet_id": pellet_id,
        "rotisserie": True,
        "seasonings": "Salt and pepper",
        "sauces": "None",
        "prep_time_minutes": 30,
        "pellets_used_lb": 3,
        "results_text": "Prep notes",
    }
    with TestClient(create_app(Settings(), sessions)) as client:
        first = client.post("/api/cooks", json=payload)
        second = client.post("/api/cooks", json={"state": "planned"})
        plans = client.get("/api/cooks?state=planned")
        next_cook = client.get("/api/cooks/next")
        unlinked = client.patch(f"/api/cooks/{first.json()['id']}", json={"meat_id": None})
        deleted = client.delete(f"/api/cooks/{first.json()['id']}")
        new_next = client.get("/api/cooks/next")

    assert first.status_code == 201
    assert first.json()["started_at"] is None
    assert first.json()["state"] == first.json()["status"] == "planned"
    assert first.json()["seasonings"] == "Salt and pepper"
    assert [item["id"] for item in plans.json()] == [second.json()["id"], first.json()["id"]]
    assert next_cook.json()["id"] == first.json()["id"]
    assert unlinked.json()["meat_id"] is None
    assert deleted.status_code == 204
    assert new_next.json()["id"] == second.json()["id"]
    with sessions() as session:
        assert session.get(Cook, second.json()["id"]).equipment_id is not None


def test_next_planned_cook_returns_404_when_empty(sessions: sessionmaker[Session]) -> None:
    with TestClient(create_app(Settings(), sessions)) as client:
        response = client.get("/api/cooks/next")

    assert response.status_code == 404
    assert response.json() == {"detail": "No planned cook"}


def test_cook_spices_create_replace_preserve_validate_and_delete(
    sessions: sessionmaker[Session],
) -> None:
    with sessions() as session:
        salt = Spice(brand="Brand B", name="Salt", is_custom=False)
        pepper = Spice(brand="Brand A", name="Pepper", is_custom=False)
        session.add_all([salt, pepper])
        session.commit()
        salt_id, pepper_id = salt.id, pepper.id

    with TestClient(create_app(Settings(), sessions)) as client:
        created = client.post(
            "/api/cooks",
            json={"state": "planned", "spice_ids": [salt_id, pepper_id, salt_id]},
        )
        cook_id = created.json()["id"]
        replaced = client.patch(f"/api/cooks/{cook_id}", json={"spice_ids": [salt_id]})
        preserved = client.patch(f"/api/cooks/{cook_id}", json={"seasonings": "extra heavy"})
        unknown_create = client.post(
            "/api/cooks", json={"state": "planned", "spice_ids": [9999]}
        )
        unknown_update = client.patch(f"/api/cooks/{cook_id}", json={"spice_ids": [9999]})
        blocked = client.delete(f"/api/spices/{salt_id}")
        deleted = client.delete(f"/api/cooks/{cook_id}")
        allowed = client.delete(f"/api/spices/{salt_id}")

    assert created.status_code == 201
    assert created.json()["spices"] == [
        {
            "id": pepper_id,
            "name": "Pepper",
            "brand": "Brand A",
            "category": "Brand A",
            "is_custom": False,
            "photo_url": None,
        },
        {
            "id": salt_id,
            "name": "Salt",
            "brand": "Brand B",
            "category": "Brand B",
            "is_custom": False,
            "photo_url": None,
        },
    ]
    assert replaced.json()["spices"] == [
        {
            "id": salt_id,
            "name": "Salt",
            "brand": "Brand B",
            "category": "Brand B",
            "is_custom": False,
            "photo_url": None,
        }
    ]
    assert preserved.json()["spices"] == replaced.json()["spices"]
    assert preserved.json()["seasonings"] == "extra heavy"
    assert unknown_create.status_code == 422
    assert unknown_create.json() == {"detail": "Spice not found"}
    assert unknown_update.status_code == 422
    assert blocked.status_code == 409
    assert blocked.json() == {"detail": "Spice is referenced by a cook"}
    assert deleted.status_code == 204
    assert allowed.status_code == 204
    with sessions() as session:
        assert session.execute(select(cook_spices)).all() == []
