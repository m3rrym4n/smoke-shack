from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path


def chart_logic(function: str, arguments: list[object]) -> object:
    module = Path("app/static/js/chart-logic.js").resolve().as_uri()
    script = (
        f'import {{ {function} }} from "{module}"; '
        f"console.log(JSON.stringify({function}(...{json.dumps(arguments)})))"
    )
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def hour_ticks(started_at: str, elapsed: int) -> object:
    module = Path("app/static/js/chart-logic.js").resolve().as_uri()
    arguments = json.dumps([started_at, elapsed, "America/Los_Angeles"])
    script = (
        f'import {{ hourTicks }} from "{module}"; '
        f"console.log(JSON.stringify(hourTicks(...{arguments})))"
    )
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def chart_markup(started_at: str, elapsed: int) -> str:
    module = Path("app/static/js/components/chart.js").resolve().as_uri()
    arguments = json.dumps(
        [
            [
                {"elapsed_seconds": 0, "pit_temp": 150},
                {"elapsed_seconds": elapsed, "pit_temp": 225},
            ],
            [],
            {"started_at": started_at},
        ]
    )
    script = (
        f'import {{ chartMarkup }} from "{module}"; '
        f"console.log(chartMarkup(...{arguments}))"
    )
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def test_hour_ticks_use_local_clock_hours() -> None:
    assert hour_ticks("2026-10-25T10:01:00-07:00", 2 * 3600 + 34 * 60) == [
        {"elapsed": 3540, "label": "11 AM"},
        {"elapsed": 7140, "label": "12 PM"},
    ]


def test_hour_ticks_exclude_start_on_whole_hour() -> None:
    assert hour_ticks("2026-10-25T10:00:00-07:00", 2 * 3600) == [
        {"elapsed": 3600, "label": "11 AM"}
    ]


def test_hour_ticks_are_empty_when_no_hour_is_inside_range() -> None:
    assert hour_ticks("2026-10-25T10:01:00-07:00", 30 * 60) == []


def test_hour_ticks_are_empty_for_invalid_start() -> None:
    assert hour_ticks("not-a-date", 3 * 3600) == []


def test_hour_ticks_use_every_second_hour_for_long_cook() -> None:
    ticks = hour_ticks("2026-10-25T10:01:00-07:00", 15 * 3600)
    assert [tick["label"] for tick in ticks] == [
        "11 AM", "1 PM", "3 PM", "5 PM", "7 PM", "9 PM", "11 PM", "1 AM"
    ]
    assert [tick["elapsed"] for tick in ticks] == [
        3540, 10740, 17940, 25140, 32340, 39540, 46740, 53940
    ]


def test_hour_markers_render_as_short_bottom_axis_ticks() -> None:
    markup = chart_markup("2026-10-25T10:30:00Z", 3 * 3600)
    ticks = re.findall(r'<line class="chart-hour-tick"[^>]+>', markup)

    assert len(ticks) == 3
    assert all('y1="270" y2="278"' in tick for tick in ticks)
    assert 'class="chart-hour"' not in markup
    assert markup.count('class="chart-hour-label"') == len(ticks)


def test_final_target_ignores_trailing_zeroes() -> None:
    samples = [
        {"probe1_target": 203, "probe2_target": None},
        {"probe1_target": 0, "probe2_target": 0},
    ]
    assert chart_logic("finalTarget", [samples]) == {"probe": 1, "value": 203}


def test_final_target_returns_null_without_positive_target() -> None:
    samples = [
        {"probe1_target": 0},
        {"probe2_target": None},
        {"probe1_target": -10, "probe2_target": "not a number"},
    ]
    assert chart_logic("finalTarget", [samples]) is None


def test_final_target_uses_larger_target_in_last_matching_sample() -> None:
    samples = [{"probe1_target": 203, "probe2_target": 205}]
    assert chart_logic("finalTarget", [samples]) == {"probe": 2, "value": 205}


def test_reached_target_finds_first_crossing_and_ignores_nulls() -> None:
    samples = [
        {"elapsed_seconds": 10, "probe1": None},
        {"elapsed_seconds": 20, "probe1": 202},
        {"elapsed_seconds": 30, "probe1": 204},
        {"elapsed_seconds": 40, "probe1": 205},
    ]
    assert chart_logic("reachedTarget", [samples, {"probe": 1, "value": 203}]) == {
        "elapsed": 30,
        "temp": 204,
    }


def test_reached_target_returns_null_when_probe_never_crosses() -> None:
    samples = [{"elapsed_seconds": 10, "probe2": 164}]
    assert chart_logic("reachedTarget", [samples, {"probe": 2, "value": 165}]) is None


def test_reached_target_returns_null_without_a_target() -> None:
    assert chart_logic("reachedTarget", [[{"elapsed_seconds": 10, "probe1": 203}], None]) is None


def test_chart_keeps_positive_target_after_trailing_zeroes() -> None:
    module = Path("app/static/js/components/chart.js").resolve().as_uri()
    samples = [
        {"elapsed_seconds": 0, "probe1": 180, "probe1_target": 203},
        {"elapsed_seconds": 60, "probe1": 204, "probe1_target": 203},
        {"elapsed_seconds": 120, "probe1": 190, "probe1_target": 0},
    ]
    arguments = json.dumps([samples, [], {"started_at": "2026-10-25T22:00:00Z"}])
    script = f'import {{ chartMarkup }} from "{module}"; console.log(chartMarkup(...{arguments}))'
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "done at 203°" in result.stdout
    assert "target-marker" in result.stdout
