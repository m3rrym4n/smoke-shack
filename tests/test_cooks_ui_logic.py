from __future__ import annotations

import json
import subprocess
from pathlib import Path


def run_logic(expression: str) -> object:
    module = Path("app/static/js/cooks-logic.js").resolve().as_uri()
    script = f'import * as logic from "{module}"; {expression}'
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_orders_planned_live_and_closed_rows() -> None:
    expression = """
      const rows = [
        {id:1,state:"closed",started_at:"2026-10-16T10:00:00Z"},
        {id:5,state:"planned",created_at:"2026-10-17T02:00:00Z"},
        {id:3,state:"cook",started_at:"2026-10-17T12:00:00Z",ended_at:null},
        {id:2,state:"closed",started_at:"2026-10-16T12:00:00Z",incomplete:true},
        {id:4,state:"planned",created_at:"2026-10-17T01:00:00Z"},
      ];
      console.log(JSON.stringify(logic.orderCookLogRows(rows).map(row => row.id)));
    """
    assert run_logic(expression) == [4, 5, 3, 2, 1]


def test_tags_and_elapsed_time_formatting() -> None:
    expression = """
      const now = new Date("2026-10-17T13:31:00Z");
      const rows = [
        {id:1,state:"planned"},
        {id:2,state:"startup",started_at:"2026-10-17T12:00:00Z",ended_at:null},
        {id:3,state:"closed",incomplete:true},
        {id:4,state:"closed",incomplete:false},
      ];
      console.log(JSON.stringify({
        tags: rows.map(logic.cookTag),
        elapsed: logic.elapsedSeconds(rows[1], now),
        formatted: logic.formatDuration(logic.elapsedSeconds(rows[1], now)),
        short: logic.formatDuration(59),
      }));
    """
    assert run_logic(expression) == {
        "tags": ["Planned", "In progress", "Incomplete", None],
        "elapsed": 5460,
        "formatted": "1h 31m",
        "short": "0m",
    }


def test_empty_cook_log() -> None:
    assert run_logic("console.log(JSON.stringify(logic.orderCookLogRows([]))); ") == []
