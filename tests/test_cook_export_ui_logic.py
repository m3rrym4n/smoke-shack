from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

MODULE = Path("app/static/js/cook-export-logic.js").resolve().as_uri()
EXPORT_MODULE = Path("app/static/js/components/cook-export.js").resolve().as_uri()


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


def share_card_chart_markup(events: list[dict[str, object]]) -> str:
    samples = [
        {"elapsed_seconds": 0, "pit_temp": 150},
        {"elapsed_seconds": 120, "pit_temp": 225},
    ]
    cook = {"started_at": "2026-10-25T22:00:00Z"}
    script = (
        f'import {{ shareCardChartMarkup }} from {json.dumps(EXPORT_MODULE)}; '
        f"console.log(shareCardChartMarkup({json.dumps(samples)}, "
        f"{json.dumps(events)}, {json.dumps(cook)}));"
    )
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def test_export_filename_uses_cook_date_and_meat_slug() -> None:
    cook = {"started_at": "2026-10-16T16:57:03Z", "meat": {"type": "Pork Picnic Shoulder"}}
    assert run(f"logic.buildExportFilename({json.dumps(cook)})") == (
        "smoke-stack-2026-10-16-pork-picnic-shoulder.png"
    )


@pytest.mark.parametrize(
    ("cook", "expected"),
    [
        ({"status": "startup"}, {"key": "startup", "label": "STARTUP"}),
        ({"status": "cook"}, {"key": "cooking", "label": "COOKING"}),
        ({"status": "cooldown"}, {"key": "complete", "label": "COMPLETE"}),
        ({"status": "closed"}, {"key": "complete", "label": "COMPLETE"}),
        (
            {"status": "closed", "incomplete": True},
            {"key": "complete", "label": "COMPLETE"},
        ),
        ({}, {"key": "complete", "label": "COMPLETE"}),
    ],
)
def test_cook_status_badge(cook: dict[str, object], expected: dict[str, str]) -> None:
    assert run(f"logic.cookStatusBadge({json.dumps(cook)})") == expected


def test_share_card_status_badge_markup_has_label_without_data_gap_text() -> None:
    markup = run('logic.cookStatusBadgeMarkup({status: "cook", has_gap: true})')
    assert "COOKING" in markup
    assert "DATA GAP" not in markup


def test_share_card_chart_includes_pin_legend() -> None:
    markup = share_card_chart_markup([
        {"id": 7, "source": "user", "elapsed_seconds": 30, "title": "Wrapped"},
    ])

    assert 'class="event-pin-legend"' in markup
    assert 'event-pin-legend-number">1</span><span>Wrapped</span>' in markup


def test_share_card_chart_omits_empty_pin_legend() -> None:
    assert "event-pin-legend" not in share_card_chart_markup([])


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
