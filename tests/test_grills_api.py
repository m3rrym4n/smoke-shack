from __future__ import annotations

from collections.abc import AsyncIterator

from conftest import add_channels
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api import create_app
from app.config import Settings
from app.ha import HARegistrySnapshot, HAStatus
from app.models import ChannelReading, Cook, Equipment, Sample
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
            *tuple(
                {
                    "entity_id": f"sensor.mb_probe{number}_temp_f",
                    "device_id": "masterbuilt-device",
                    "unique_id": f"abc_probe{number}_temp_f",
                    "original_name": f"Probe{number} Temp F",
                }
                for number in range(2, 5)
            ),
            {
                "entity_id": "number.mb_target_temp_f",
                "device_id": "masterbuilt-device",
                "unique_id": "abc_target_temp_f",
                "original_name": "Target Temp F",
            },
            *tuple(
                {
                    "entity_id": f"sensor.mb_probe{number}_target_f",
                    "device_id": "masterbuilt-device",
                    "unique_id": f"abc_probe{number}_target_f",
                    "original_name": f"Probe{number} Target F",
                }
                for number in range(1, 5)
            ),
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
            *tuple(
                {"entity_id": f"sensor.mb_probe{number}_temp_f", "state": state}
                for number in range(2, 5)
            ),
            {"entity_id": "number.mb_target_temp_f", "state": state},
            *tuple(
                {"entity_id": f"sensor.mb_probe{number}_target_f", "state": state}
                for number in range(1, 5)
            ),
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
        "connection_status": "disconnected",
    }
    assert grills[1]["id"] == "gmg-device"
    assert grills[1]["profile_id"] is None
    assert grills[1]["equipment_id"] == 1
    assert grills[1]["device_status"] == "available"
    assert grills[1]["connection_status"] == "connected"


def test_profile_device_is_not_available_when_all_main_entities_are_unavailable(
    sessions,
) -> None:
    app = create_app(Settings(), sessions, RegistryHAClient(registry_snapshot(unavailable=True)))

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
            "connection_status": "disconnected",
        }
    ]


def test_returns_503_when_home_assistant_is_unreachable(sessions) -> None:
    app = create_app(Settings(), sessions, RegistryHAClient())

    with TestClient(app) as client:
        response = client.get("/api/grills")

    assert response.status_code == 503
    assert response.json() == {"detail": "Home Assistant is unavailable: connection refused"}


def test_connect_creates_profile_equipment_and_switches_atomically(sessions) -> None:
    add_channels(sessions)
    app = create_app(Settings(), sessions, RegistryHAClient(registry_snapshot(unavailable=True)))

    with TestClient(app) as client:
        response = client.post("/api/grills/masterbuilt-device/connect")

    assert response.status_code == 200, response.text
    assert response.json()["connection_status"] == "connected"
    with sessions() as session:
        equipment = session.scalars(select(Equipment).order_by(Equipment.id)).all()
        assert [item.connected for item in equipment] == [False, True]
        assert equipment[1].nickname == "Patio Grill"
        assert (equipment[1].maker, equipment[1].model, equipment[1].fuel_type) == (
            "Masterbuilt",
            "Gravity 800",
            "charcoal",
        )
        assert [channel.key for channel in equipment[1].channels] == [
            "pit",
            "probe1",
            "probe2",
            "probe3",
            "probe4",
        ]

    cook = app.state.cook_service.process(
        GrillSnapshot(
            pit_temp=275,
            setpoint=300,
            probe1=155,
            probe2=160,
            extra_probes={"probe3": 165, "probe4": 170},
            fire_state="Running",
            power_state="On",
            hvac_mode="heat",
        )
    )
    assert cook is not None and cook.equipment_id == 2
    with sessions() as session:
        assert len(session.scalars(select(ChannelReading)).all()) == 5


def test_connect_and_disconnect_are_blocked_during_active_cook(sessions) -> None:
    add_channels(sessions)
    with sessions() as session:
        session.add(Cook(status="cook", equipment_id=1))
        session.commit()
    app = create_app(Settings(), sessions, RegistryHAClient(registry_snapshot()))

    with TestClient(app) as client:
        connect = client.post("/api/grills/masterbuilt-device/connect")
        disconnect = client.post("/api/grills/gmg-device/disconnect")

    assert connect.status_code == disconnect.status_code == 409
    with sessions() as session:
        assert session.get(Equipment, 1).connected is True
        assert session.scalar(select(Equipment.id).where(Equipment.id != 1)) is None


def test_disconnected_equipment_does_not_start_or_record(sessions) -> None:
    with sessions() as session:
        session.get(Equipment, 1).connected = False
        session.commit()
    app = create_app(Settings(), sessions, RegistryHAClient(registry_snapshot()))

    result = app.state.cook_service.process(
        GrillSnapshot(hvac_mode="heat", fire_state="Running", power_state="On")
    )

    assert result is None
    with sessions() as session:
        assert session.scalar(select(Cook.id)) is None
        assert session.scalar(select(Sample.id)) is None
