from __future__ import annotations

import json
import subprocess
from pathlib import Path


def collapse(events: list[dict[str, object]], threshold: int = 120) -> list[dict[str, object]]:
    module = Path("app/static/js/components/cook-log.js").resolve().as_uri()
    script = (
        f'import {{ collapseBriefDataGaps }} from "{module}"; '
        f"console.log(JSON.stringify(collapseBriefDataGaps({json.dumps(events)}, {threshold})));"
    )
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)  # type: ignore[no-any-return]


def gap(event_id: int, start: str, end: str) -> dict[str, object]:
    return {
        "id": event_id,
        "kind": "data_gap",
        "source": "auto",
        "title": "Home Assistant data gap",
        "ts": end,
        "elapsed_seconds": event_id * 100,
        "data": {"start": start, "end": end},
    }


def test_collapses_consecutive_brief_stored_gaps() -> None:
    rows = collapse(
        [
            gap(1, "2026-01-01T00:00:00Z", "2026-01-01T00:00:40Z"),
            gap(2, "2026-01-01T00:02:00Z", "2026-01-01T00:03:10Z"),
        ]
    )
    assert len(rows) == 1
    assert rows[0]["kind"] == "data_gap_summary"
    assert rows[0]["title"] == "2 brief data gaps (1m 50s total, longest 70s)"
    assert rows[0]["data"] == {"count": 2, "total_seconds": 110, "longest_seconds": 70}


def test_long_gap_breaks_brief_groups() -> None:
    brief_one = gap(1, "2026-01-01T00:00:00Z", "2026-01-01T00:00:40Z")
    long_gap = gap(2, "2026-01-01T00:01:00Z", "2026-01-01T00:03:00Z")
    brief_two = gap(3, "2026-01-01T00:04:00Z", "2026-01-01T00:05:00Z")
    rows = collapse([brief_one, long_gap, brief_two])
    assert [row["kind"] for row in rows] == ["data_gap_summary", "data_gap", "data_gap_summary"]


def test_empty_and_mixed_events_stay_in_order() -> None:
    assert collapse([]) == []
    fire = {"id": 8, "kind": "fire_lit", "title": "Fire lit"}
    user = {"id": 9, "kind": "wrapped", "source": "user", "title": "Wrapped"}
    brief = gap(10, "2026-01-01T00:05:00Z", "2026-01-01T00:05:30Z")
    rows = collapse([fire, brief, user])
    assert [row["id"] for row in rows] == [8, "brief-data-gaps-10", 9]
