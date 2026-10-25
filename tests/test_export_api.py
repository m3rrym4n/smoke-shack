from __future__ import annotations

import csv
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from io import StringIO

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.api import create_app
from app.config import Settings
from app.models import Cook, Event, Meat, Note, Pellet, Photo, Profile, ProfileStep, Sample, Spice
from app.routes.export import COOK_HEADERS


def _rows(content: str) -> list[dict[str, str]]:
    return list(csv.DictReader(StringIO(content)))


def test_cooks_csv_headers_values_durations_filters_and_formula_escaping(
    sessions: sessionmaker[Session],
) -> None:
    started = datetime(2026, 10, 16, 16, 57, 3, tzinfo=UTC)
    with sessions() as session:
        meat = Meat(
            type="=Pork",
            pounds=Decimal("4.25"),
            price_per_pound=Decimal("3.20"),
            store="+Shop",
            purchased_on=date(2026, 10, 15),
        )
        pellet = Pellet(
            vendor="@Vendor",
            product_name="-Blend",
            price_per_pound=Decimal("1.40"),
            purchased_on=date(2026, 10, 1),
        )
        profile = Profile(name="=Profile", keep_warm=False)
        spice = Spice(brand="Meat Church", name="Holy Cow", is_custom=False)
        session.add_all([meat, pellet, profile, spice])
        session.flush()
        cook = Cook(
            started_at=started,
            startup_ended_at=started + timedelta(minutes=5),
            cook_ended_at=started + timedelta(minutes=65),
            cooldown_ended_at=started + timedelta(minutes=75),
            ended_at=started + timedelta(minutes=75),
            status="complete",
            meat_id=meat.id,
            pellet_id=pellet.id,
            profile_id=profile.id,
            rotisserie=True,
            seasonings="=SUM(A1)",
            sauces="+Sauce",
            prep_time_minutes=12,
            results_text="@great",
            pellets_used_lb=2.5,
            aggregate_setpoint=250,
            setpoint_override=275,
            time_to_done_seconds=3500,
            has_gap=True,
            incomplete=False,
        )
        session.add(cook)
        cook.spices = [spice]
        session.commit()
        meat_id = meat.id

    with TestClient(create_app(Settings(), sessions)) as client:
        response = client.get(f"/api/export/cooks.csv?meat_id={meat_id}&status=complete")
        empty = client.get("/api/export/cooks.csv?status=startup")

    assert response.status_code == 200
    assert "attachment" in response.headers["content-disposition"]
    row = _rows(response.text)[0]
    assert list(row) == COOK_HEADERS
    assert row["started_at"] == "2026-10-16T16:57:03Z"
    assert row["startup_duration_seconds"] == "300"
    assert row["cook_duration_seconds"] == "3600"
    assert row["cooldown_duration_seconds"] == "600"
    assert row["grill_duration_seconds"] == "4500"
    assert row["effective_setpoint"] == "275.0"
    assert row["spices"] == "Holy Cow"
    assert row["seasonings"] == "'=SUM(A1)"
    assert row["sauces"] == "'+Sauce"
    assert row["results_text"] == "'@great"
    assert row["meat_type"] == "'=Pork"
    assert row["meat_store"] == "'+Shop"
    assert row["pellet_vendor"] == "'@Vendor"
    assert row["pellet_product_name"] == "'-Blend"
    assert row["profile_name"] == "'=Profile"
    assert len(empty.text.splitlines()) == 1


def test_samples_csv_extra_probe_and_unknown_cook(sessions: sessionmaker[Session]) -> None:
    started = datetime(2026, 10, 16, 16, 57, 3, tzinfo=UTC)
    with sessions() as session:
        cook = Cook(started_at=started, status="cook")
        session.add(cook)
        session.flush()
        session.add_all(
            [
                Sample(
                    cook_id=cook.id,
                    ts=started + timedelta(seconds=10),
                    pit_temp=225,
                    setpoint=250,
                    probe1=100,
                    probe2=101,
                    probe1_target=195,
                    probe2_target=200,
                    extra_probes={"Ambient": 72.5},
                    fire_state="lit",
                    power_state="on",
                    hvac_mode="heat",
                ),
                Sample(cook_id=cook.id, ts=started + timedelta(seconds=20), extra_probes={}),
            ]
        )
        session.commit()
        cook_id = cook.id

    with TestClient(create_app(Settings(), sessions)) as client:
        response = client.get(f"/api/export/cooks/{cook_id}/samples.csv")
        missing = client.get("/api/export/cooks/999/samples.csv")

    rows = _rows(response.text)
    assert rows[0]["ts"] == "2026-10-16T16:57:13Z"
    assert rows[0]["elapsed_seconds"] == "10"
    assert rows[0]["Ambient"] == "72.5"
    assert rows[1]["Ambient"] == ""
    assert missing.status_code == 404
    assert missing.json() == {"detail": "Cook not found"}


def test_all_json_shape_excludes_samples_and_photo_binaries(
    sessions: sessionmaker[Session],
) -> None:
    started = datetime(2026, 10, 16, 16, 57, 3, tzinfo=UTC)
    with sessions() as session:
        meat = Meat(
            type="Ribs",
            pounds=Decimal("3"),
            price_per_pound=Decimal("4"),
            purchased_on=date(2026, 10, 16),
        )
        pellet = Pellet(
            vendor="Vendor",
            product_name="Blend",
            price_per_pound=Decimal("1"),
            purchased_on=date(2026, 10, 16),
        )
        profile = Profile(name="Ribs", keep_warm=False)
        session.add_all([meat, pellet, profile])
        session.flush()
        session.add(
            ProfileStep(
                profile_id=profile.id,
                position=1,
                grill_temp=250,
                stop_mode="time",
                duration_minutes=60,
                instructions="Smoke",
            )
        )
        cook = Cook(
            started_at=started,
            ended_at=started + timedelta(hours=1),
            status="complete",
            meat_id=meat.id,
            pellet_id=pellet.id,
            profile_id=profile.id,
        )
        session.add(cook)
        session.flush()
        event = Event(
            cook_id=cook.id,
            ts=started + timedelta(minutes=5),
            kind="wrapped",
            source="user",
            title="Wrap",
            data={},
        )
        session.add(event)
        session.flush()
        session.add_all(
            [
                Photo(
                    cook_id=cook.id, event_id=event.id, path="/private/photo.jpg", caption="Done"
                ),
                Sample(cook_id=cook.id, ts=started, extra_probes={}),
                Note(title="Note", body="Body", scope="this_cook", cook_id=cook.id),
            ]
        )
        session.commit()

    with TestClient(create_app(Settings(), sessions)) as client:
        response = client.get("/api/export/all.json")

    assert response.status_code == 200
    assert "smoke-stack-" in response.headers["content-disposition"]
    exported = response.json()
    assert set(exported) == {"cooks", "meat", "pellets", "profiles", "notes"}
    assert "samples" not in exported["cooks"][0]
    assert exported["cooks"][0]["events"][0]["elapsed_seconds"] == 300
    assert exported["cooks"][0]["photos"][0]["caption"] == "Done"
    assert "path" not in exported["cooks"][0]["photos"][0]
    assert exported["profiles"][0]["steps"][0]["instructions"] == "Smoke"


def test_planned_cook_is_only_in_full_export(sessions: sessionmaker[Session]) -> None:
    with sessions() as session:
        session.add(Cook(started_at=None, status="planned", seasonings="SPG"))
        session.commit()

    with TestClient(create_app(Settings(), sessions)) as client:
        csv_response = client.get("/api/export/cooks.csv")
        full_response = client.get("/api/export/all.json")

    assert _rows(csv_response.text) == []
    assert full_response.json()["cooks"][0]["state"] == "planned"
    assert full_response.json()["cooks"][0]["started_at"] is None
