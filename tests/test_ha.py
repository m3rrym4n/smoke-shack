from __future__ import annotations

from typing import Any

from app.config import EntityConfig
from app.ha import HomeAssistantClient


def test_snapshot_reads_climate_attributes_and_real_probe_connections() -> None:
    entities = EntityConfig(
        pit_climate="climate.green_mountain_grill",
        pit_temp="sensor.green_mountain_grill_temperature",
        probe1_temp="sensor.green_mountain_grill_probe_1_temperature",
        probe2_temp="sensor.green_mountain_grill_probe_2_temperature",
        probe1_connection="binary_sensor.green_mountain_grill_probe_1_connection",
        probe2_connection="binary_sensor.green_mountain_grill_probe_2_connection",
        probe1_climate="climate.green_mountain_grill_probe_1",
        probe2_climate="climate.green_mountain_grill_probe_2",
        fire_state="sensor.green_mountain_grill_fire_state",
        power_state="sensor.green_mountain_grill_power_state",
        warning="sensor.green_mountain_grill_warning",
    )
    states: dict[str, dict[str, Any]] = {
        entities.pit_climate: {"state": "heat", "attributes": {"temperature": 275}},
        entities.pit_temp: {"state": "250"},
        entities.probe1_temp: {"state": "160"},
        entities.probe2_temp: {"state": "unknown"},
        entities.probe1_connection: {"state": "on"},
        entities.probe2_connection: {"state": "off"},
        entities.probe1_climate: {"state": "heat", "attributes": {"temperature": 203}},
        entities.probe2_climate: {"state": "off", "attributes": {"temperature": 165}},
        entities.fire_state: {"state": "Running"},
        entities.power_state: {"state": "On"},
        entities.warning: {"state": "None"},
    }

    snapshot = HomeAssistantClient("http://ha", "token", entities)._snapshot(states)

    assert snapshot.setpoint == 275
    assert snapshot.probe1_target == 203
    assert snapshot.probe2_target == 165
    assert snapshot.probe1_connected
    assert not snapshot.probe2_connected
    assert snapshot.probe2 is None
