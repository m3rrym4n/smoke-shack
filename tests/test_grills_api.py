from __future__ import annotations

from collections.abc import AsyncIterator

from conftest import add_channels
from fastapi.testclient import TestClient

from app.api import create_app
from app.config import Settings
from app.ha import HARegistrySnapshot, HAStatus
from app.service import GrillSnapshot


class RegistryHAClient:
    def __init__(self, snapshot: HARegistrySnapshot | None = None) -> None:
        self.status = HAStatus(configured=True)
        self.snapshot = snapshot

    async def snapshots(self) -> AsyncIterator[GrillSnapshot]:
        if False:
            yield GrillSnapshot()

    async def registry_snapshot(self) -> HARegistrySnapshot:
        if self.snapshot is None:
            raise RuntimeError("connection refused")
        return self.snapshot


def registry_snapshot(*, unavailable: bool = False) -> HARegistrySnapshot:
    state = "unavailable" if unavailable else "unknown"
    return HARegistrySnapshot(
        devices=(
            {
                "id": "masterbuilt-device",
                "name": "Masterbuilt Grill",
                "name_by_user": "Patio Grill",
                "manufacturer": "Masterbuilt",
                "model": "Gravity Series 800",
            },
            {
                "id": "unrelated-device",
                "name": "Kitchen Light",
                "manufacturer": "Acme",
                "model": "Bulb",
            },
            {
                "id": "gmg-device",
                "name": "Daniel Boone",
                "manufacturer": "Green Mountain Grills",
                "model": "Daniel Boone Prime",
            },
        ),
        entities=(
            {
                "entity_id": "sensor.mb_grill_temp_f",
                "device_id": "masterbuilt-device",
                "unique_id": "abc_grill_temp_f",
                "original_name": "Grill Temp F",
            },
            {
                "entity_id": "sensor.mb_probe1_temp_f",
                "device_id": "masterbuilt-device",
                "unique_id": "abc_probe1_temp_f",
                "original_name": "Probe1 Temp F",
            },
            {
                "entity_id": "light.kitchen",
                "device_id": "unrelated-device",
                "unique_id": "kitchen",
                "original_name": "Kitchen",
            },
            {
                "entity_id": "sensor.pit",
                "device_id": "gmg-device",
                "unique_id": "gmg_pit",
                "original_name": "Pit",
            },
            {
                "entity_id": "sensor.probe1",
                "device_id": "gmg-device",
                "unique_id": "gmg_probe1",
                "original_name": "Probe 1",
            },
            {
                "entity_id": "sensor.probe2",
                "device_id": "gmg-device",
                "unique_id": "gmg_probe2",
                "original_name": "Probe 2",
            },
        ),
        states=(
            {"entity_id": "sensor.mb_grill_temp_f", "state": state},
            {"entity_id": "sensor.mb_probe1_temp_f", "state": state},
            {"entity_id": "light.kitchen", "state": "on"},
            {"entity_id": "sensor.pit", "state": "225"},
            {"entity_id": "sensor.probe1", "state": "145"},
            {"entity_id": "sensor.probe2", "state": "unavailable"},
        ),
    )


def test_lists_profile_match_and_existing_equipment(sessions) -> None:
    add_channels(sessions)
    app = create_app(Settings(), sessions, RegistryHAClient(registry_snapshot()))

    with TestClient(app) as client:
        response = client.get("/api/grills")

    assert response.status_code == 200
    grills = response.json()
    assert len(grills) == 2
    assert grills[0] == {
        "id": "masterbuilt-device",
        "name": "Patio Grill",
        "maker": "Masterbuilt",
        "model": "Gravity Series 800",
        "profile_id": "masterbuilt-gravity-800",
        "device_status": "available",
        "equipment_id": None,
    }
    assert grills[1]["id"] == "gmg-device"
    assert grills[1]["profile_id"] is None
    assert grills[1]["equipment_id"] == 1
    assert grills[1]["device_status"] == "available"


def test_profile_device_is_not_available_when_all_main_entities_are_unavailable(
    sessions,
) -> None:
    app = create_app(
        Settings(), sessions, RegistryHAClient(registry_snapshot(unavailable=True))
    )

    with TestClient(app) as client:
        response = client.get("/api/grills")

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": "masterbuilt-device",
            "name": "Patio Grill",
            "maker": "Masterbuilt",
            "model": "Gravity Series 800",
            "profile_id": "masterbuilt-gravity-800",
            "device_status": "not_available",
            "equipment_id": None,
        }
    ]


def test_returns_503_when_home_assistant_is_unreachable(sessions) -> None:
    app = create_app(Settings(), sessions, RegistryHAClient())

    with TestClient(app) as client:
        response = client.get("/api/grills")

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Home Assistant is unavailable: connection refused"
    }
