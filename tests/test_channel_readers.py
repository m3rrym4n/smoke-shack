from __future__ import annotations

import csv
from dataclasses import replace
from io import StringIO

from conftest import FakeClock, add_channels
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.api import create_app
from app.config import Settings
from app.models import Cook, Sample
from app.service import CookService, GrillSnapshot


def test_gravity_channels_drive_api_stats_and_csv(
    sessions: sessionmaker[Session],
    clock: FakeClock,
    masterbuilt_gravity_800_snapshot: GrillSnapshot,
) -> None:
    add_channels(sessions, ("pit", "probe1", "probe2", "probe3", "probe4"))
    first = replace(
        masterbuilt_gravity_800_snapshot,
        probe1_target=None,
        probe2_target=None,
        extra_probes={"probe3": 165, "probe4": 170},
        extra_probe_targets={"probe3": 205, "probe4": 210},
    )
    service = CookService(sessions, clock)
    cook = service.process(first)
    assert cook is not None

    clock.advance(minutes=1)
    service.process(replace(first, extra_probes={"probe3": 205, "probe4": 171}))

    # Prove readers prefer channel_readings over the dual-write compatibility columns.
    with sessions() as session:
        samples = list(session.scalars(select(Sample).order_by(Sample.ts)))
        samples[-1].pit_temp = -1
        samples[-1].probe1 = -2
        samples[-1].extra_probes = {"wrong": -3}
        session.commit()
        cook_id = cook.id

    with TestClient(create_app(Settings(), sessions)) as client:
        sample_response = client.get(f"/api/cooks/{cook_id}/samples")
        cook_response = client.get(f"/api/cooks/{cook_id}")
        csv_response = client.get(f"/api/export/cooks/{cook_id}/samples.csv")

    assert sample_response.status_code == 200
    latest = sample_response.json()[-1]
    assert latest["pit_temp"] == 300
    assert latest["probe1"] == 155
    assert latest["extra_probes"] == {"probe3": 205, "probe4": 171}
    assert latest["channels"] == [
        {"key": "pit", "label": "Pit", "role": "pit", "value": 300, "target": 300},
        {
            "key": "probe1",
            "label": "Probe1",
            "role": "meat",
            "value": 155,
            "target": None,
        },
        {
            "key": "probe2",
            "label": "Probe2",
            "role": "meat",
            "value": 160,
            "target": None,
        },
        {
            "key": "probe3",
            "label": "Probe3",
            "role": "meat",
            "value": 205,
            "target": 205,
        },
        {
            "key": "probe4",
            "label": "Probe4",
            "role": "meat",
            "value": 171,
            "target": 210,
        },
    ]
    assert cook_response.json()["channels"] == latest["channels"]

    rows = list(csv.DictReader(StringIO(csv_response.text)))
    assert list(rows[-1])[-2:] == ["probe3", "probe4"]
    assert rows[-1]["pit_temp"] == "300.0"
    assert rows[-1]["probe3"] == "205.0"

    with sessions() as session:
        saved = session.get(Cook, cook_id)
        assert saved is not None
        assert saved.time_to_done_seconds == 60


def test_legacy_only_sample_keeps_compatibility_shape(
    sessions: sessionmaker[Session], clock: FakeClock
) -> None:
    with sessions() as session:
        cook = Cook(started_at=clock.now(), status="cook")
        session.add(cook)
        session.flush()
        session.add(
            Sample(
                cook_id=cook.id,
                ts=clock.now(),
                pit_temp=225,
                setpoint=250,
                probe1=180,
                probe1_target=203,
                extra_probes={"sensor.ambient": 72},
            )
        )
        session.commit()
        cook_id = cook.id

    with TestClient(create_app(Settings(), sessions)) as client:
        sample = client.get(f"/api/cooks/{cook_id}/samples").json()[0]

    assert sample["pit_temp"] == 225
    assert sample["setpoint"] == 250
    assert sample["probe1"] == 180
    assert sample["probe1_target"] == 203
    assert sample["extra_probes"] == {"sensor.ambient": 72}
    assert sample["channels"] == []
