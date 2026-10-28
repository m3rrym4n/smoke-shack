from __future__ import annotations

import json
import subprocess
from pathlib import Path


def markup(events: list[dict[str, object]], editable: bool = False) -> str:
    module = Path("app/static/js/components/cook-log.js").resolve().as_uri()
    script = (
        f'import {{ cookLogMarkup }} from "{module}"; '
        f"console.log(cookLogMarkup({json.dumps(events)}, {json.dumps(editable)}));"
    )
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def present(event: dict[str, object]) -> dict[str, object]:
    module = Path("app/static/js/components/cook-log.js").resolve().as_uri()
    script = (
        f'import {{ presentEvent }} from "{module}"; '
        f"console.log(JSON.stringify(presentEvent({json.dumps(event)})));"
    )
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)  # type: ignore[no-any-return]


def event(event_id: int, kind: str, title: str, source: str = "auto") -> dict[str, object]:
    return {
        "id": event_id,
        "kind": kind,
        "source": source,
        "title": title,
        "ts": "2026-01-01T00:05:00Z",
        "elapsed_seconds": event_id * 100,
        "data": {},
    }


def test_data_gap_events_are_hidden_from_live_and_detail_logs() -> None:
    events = [
        event(1, "fire_lit", "Fire lit"),
        event(2, "data_gap", "Home Assistant data gap"),
        event(3, "data_gap_summary", "Brief Home Assistant data gaps"),
        event(4, "wrapped", "Wrapped", "user"),
    ]

    for editable in (True, False):
        rendered = markup(events, editable)
        assert "Home Assistant data gap" not in rendered
        assert "Brief Home Assistant data gaps" not in rendered
        assert "Fire lit" in rendered
        assert "Wrapped" in rendered


def test_hidden_data_gaps_do_not_affect_user_event_numbering_or_order() -> None:
    rendered = markup(
        [
            event(1, "wrapped", "First user event", "user"),
            event(2, "data_gap", "Hidden gap"),
            event(3, "setpoint_changed", "Setpoint changed"),
            event(4, "spritzed", "Second user event", "user"),
        ]
    )

    assert rendered.index("First user event") < rendered.index("Setpoint changed")
    assert rendered.index("Setpoint changed") < rendered.index("Second user event")
    assert '<span class="pin" aria-hidden="true">1</span>' in rendered
    assert '<span class="pin" aria-hidden="true">2</span>' in rendered


def test_presents_stored_setpoint_event_from_data() -> None:
    event = {
        "kind": "setpoint_changed",
        "title": "Setpoint changed",
        "description": None,
        "data": {"from": 225, "to": 275},
    }
    assert present(event) == {
        **event,
        "title": "Setpoint changed to 275°F",
        "description": "from 225°F",
    }


def test_presents_stored_setpoint_event_from_details() -> None:
    event = {
        "kind": "setpoint_changed",
        "title": "Setpoint changed",
        "description": "from 225°F to 275°F",
        "data": {},
    }
    assert present(event)["title"] == "Setpoint changed to 275°F"


def test_setpoint_without_new_value_falls_back_to_stored_title() -> None:
    event = {
        "kind": "setpoint_changed",
        "title": "Stored setpoint event",
        "description": None,
        "data": {"from": 225},
    }
    assert present(event)["title"] == "Stored setpoint event"


def test_non_setpoint_event_is_untouched() -> None:
    event = {"kind": "fire_lit", "title": "Fire lit", "data": {"to": 275}}
    assert present(event) == event
