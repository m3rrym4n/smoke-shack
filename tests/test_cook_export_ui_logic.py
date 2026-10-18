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


def test_pellet_line_includes_vendor_product_and_suffix() -> None:
    pellet = {"vendor": "Bear Mountain", "product_name": "Hickory"}
    assert run(f"logic.pelletLine({json.dumps(pellet)})") == (
        "Bear Mountain Hickory Pellets"
    )
    assert run("logic.pelletLine(null)") == ""


def test_weight_text_only_formats_positive_numbers() -> None:
    assert run("logic.weightText(8)") == "8 lb"
    assert run('logic.weightText("4.5")') == "4.5 lb"
    assert run("logic.weightText(null)") == ""


def test_papers_are_shown_only_for_nonempty_content() -> None:
    notes = [{"body": "  "}, {"body": "Wrap at the stall"}]
    assert run(f"logic.shownPapers({json.dumps(notes)}, '  ')") == {
        "notes": True,
        "results": False,
    }
    assert run("logic.shownPapers([], 'Tender and juicy')") == {
        "notes": False,
        "results": True,
    }
    assert run("logic.shownPapers([], null)") == {"notes": False, "results": False}


def test_export_photo_defaults_to_most_recent_photo() -> None:
    photos = [{"id": 4}, {"id": 9}, {"id": 6}]
    assert run(f"logic.exportPhotoSelection({json.dumps(photos)}, null)") == "9"


def test_export_photo_uses_remembered_choice_while_it_exists() -> None:
    photos = [{"id": 4}, {"id": 9}]
    assert run(f"logic.exportPhotoSelection({json.dumps(photos)}, '4')") == "4"
    assert run(f"logic.exportPhotoSelection({json.dumps(photos)}, 'none')") == "none"


def test_export_photo_falls_back_when_remembered_photo_was_removed() -> None:
    photos = [{"id": 4}, {"id": 9}]
    assert run(f"logic.exportPhotoSelection({json.dumps(photos)}, '7')") == "9"
