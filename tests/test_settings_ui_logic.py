from __future__ import annotations

import json
import subprocess
from pathlib import Path


def run_logic(expression: str) -> object:
    module = Path("app/static/js/settings-logic.js").resolve().as_uri()
    script = f'import * as logic from "{module}"; {expression}'
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_settings_is_in_navigation_and_router() -> None:
    page = Path("app/static/index.html").read_text()
    app = Path("app/static/js/app.js").read_text()
    assert '<a class="pbtn" href="#settings">Settings</a>' in page
    assert 'mountSettingsView(view)' in app


def test_grills_show_statuses_and_the_right_control() -> None:
    grills = json.dumps([
        {
            "id": "one", "name": "Patio Grill", "maker": "Masterbuilt",
            "model": "Gravity 800", "device_status": "available",
            "connection_status": "connected",
        },
        {
            "id": "two", "name": "Garage Grill", "maker": None,
            "model": None, "device_status": "not_available",
            "connection_status": "disconnected",
        },
    ])
    expression = f"console.log(JSON.stringify(logic.renderGrills({grills})))"
    markup = run_logic(expression)
    assert "Masterbuilt · Gravity 800" in markup
    assert "Patio Grill" not in markup
    assert '<p class="mut">' not in markup
    assert "Available" in markup
    assert "Connected" in markup
    assert 'data-action="disconnect">Disconnect</button>' in markup
    assert "Not available" in markup
    assert "Disconnected" in markup
    assert 'data-action="connect">Connect</button>' in markup
    assert "Garage Grill" in markup


def test_grill_picture_controls_show_existing_previews() -> None:
    grills = json.dumps([{
        "id": "one", "name": "Patio Grill", "maker": "Masterbuilt",
        "model": "Gravity Series 800", "device_status": "available",
        "connection_status": "connected", "equipment_id": 7,
        "photo_url": "/api/equipment/7/photo", "logo_url": "/api/equipment/7/logo",
    }])
    markup = run_logic(f"console.log(JSON.stringify(logic.renderGrills({grills})))")
    assert 'data-image-kind="photo"' in markup
    assert 'src="/api/equipment/7/photo"' in markup
    assert 'data-image-kind="logo"' in markup
    assert 'src="/api/equipment/7/logo"' in markup
    assert markup.count(">Remove</button>") == 2


def test_server_message_is_rendered_next_to_its_grill() -> None:
    grills = json.dumps([
        {
            "id": "one", "name": "Patio Grill", "maker": "Masterbuilt",
            "model": "Gravity 800", "device_status": "available",
            "connection_status": "connected",
        },
    ])
    messages = json.dumps({"one": "Cannot change the connected grill while a cook is in progress"})
    expression = f"console.log(JSON.stringify(logic.renderGrills({grills}, {messages})))"
    markup = run_logic(expression)
    assert "Cannot change the connected grill while a cook is in progress" in markup
    assert 'data-action="disconnect">Disconnect</button>' in markup


def test_settings_uses_api_helpers_and_handles_unreachable_home_assistant() -> None:
    api = Path("app/static/js/api.js").read_text()
    view = Path("app/static/js/views/settings.js").read_text()
    assert 'getJson("/api/grills")' in api
    assert '`/api/grills/${encodeURIComponent(grillId)}/connect`' in api
    assert '`/api/grills/${encodeURIComponent(grillId)}/disconnect`' in api
    assert "Home Assistant is not reachable" in view
    assert "error.status === 503" in view
    assert "messages[grillId] = error.message" in view
