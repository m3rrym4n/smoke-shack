from __future__ import annotations

import json
import subprocess
from pathlib import Path


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
