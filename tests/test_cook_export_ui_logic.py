from __future__ import annotations

import json
import subprocess
from pathlib import Path

MODULE = Path("app/static/js/cook-export-logic.js").resolve().as_uri()


def run(expression: str) -> object:
    script = (
        f'import * as logic from {json.dumps(MODULE)}; '
        f"console.log(JSON.stringify({expression}));"
    )
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_export_filename_uses_cook_date_and_meat_slug() -> None:
    cook = {"started_at": "2026-10-16T16:57:03Z", "meat": {"type": "Pork Picnic Shoulder"}}
    assert run(f"logic.buildExportFilename({json.dumps(cook)})") == (
        "smoke-stack-2026-10-16-pork-picnic-shoulder.png"
    )


def test_export_sections_are_in_required_order_and_omit_empty_panes() -> None:
    assert run("logic.exportSectionKeys()") == ["special"]
    content = {
        "notes": [{"body": "Wrap it"}],
        "resultsText": "Tender",
        "photos": [{"url": "/photos/1"}],
        "samples": [{"pit_temp": 225}],
        "events": [{"kind": "wrapped"}],
    }
    assert run(f"logic.exportSectionKeys({json.dumps(content)})") == [
        "special",
        "notes",
        "results",
        "chart",
        "log",
    ]


def test_data_gap_events_alone_do_not_add_cook_log() -> None:
    content = {"events": [{"kind": "data_gap"}, {"kind": "data_gap_summary"}]}
    assert run(f"logic.exportSectionKeys({json.dumps(content)})") == ["special"]
