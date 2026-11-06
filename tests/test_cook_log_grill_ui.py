from __future__ import annotations

import json
import subprocess
from pathlib import Path


def render_row(cook: dict[str, object]) -> str:
    module = Path("app/static/js/views/cooks.js").resolve().as_uri()
    script = (
        f'import {{ cookRowMarkup }} from "{module}"; '
        f'console.log(cookRowMarkup({json.dumps(cook)}, new Date("2026-10-17T00:00:00Z")));'
    )
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def cook(**values: object) -> dict[str, object]:
    return {
        "id": 1,
        "state": "closed",
        "started_at": "2026-10-16T12:00:00Z",
        "ended_at": "2026-10-16T13:00:00Z",
        "meat": {"type": "Brisket"},
        "effective_setpoint": 275,
        "grill_duration_seconds": 3600,
        **values,
    }


def test_cook_rows_show_manufacturer_and_model_for_different_grills() -> None:
    assert "Green Mountain Grills Daniel Boone" in render_row(
        cook(grill_manufacturer="Green Mountain Grills", grill_model="Daniel Boone")
    )
    assert "Masterbuilt Gravity Series 800" in render_row(
        cook(grill_manufacturer="Masterbuilt", grill_model="Gravity Series 800")
    )


def test_cook_log_has_grill_as_its_first_header() -> None:
    source = Path("app/static/js/views/cooks.js").read_text()

    assert '<div class="cook-columns mut"><span>GRILL</span><span>Date &amp; meat</span>' in source


def test_cook_row_without_equipment_has_an_empty_grill_cell() -> None:
    markup = render_row(cook(grill_manufacturer=None, grill_model=None))

    assert '<span class="cook-grill"></span>' in markup
    assert "Brisket" in markup
    assert "275°" in markup
