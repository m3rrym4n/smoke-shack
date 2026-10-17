from __future__ import annotations

import json
import subprocess
from pathlib import Path


def run_logic(expression: str) -> object:
    module = Path("app/static/js/notes-logic.js").resolve().as_uri()
    script = f'import * as logic from "{module}"; {expression}'
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_note_validation_requires_text_and_a_cook_for_cook_scope() -> None:
    expression = (
        'console.log(JSON.stringify(logic.validateNote({title: " ", body: "", '
        'scope: "this_cook", cook_id: null})))'
    )
    assert run_logic(expression) == {
        "title": "Give the note a title.",
        "body": "Write something on the note.",
        "cook_id": "Choose a cook for this note.",
    }


def test_note_payload_trims_text_and_keeps_cook_link() -> None:
    values = (
        '{title: "  Wrap  ", body: "  Use butcher paper  ", '
        'scope: "this_cook", cook_id: "12"}'
    )
    assert run_logic(f"console.log(JSON.stringify(logic.notePayload({values})))") == {
        "title": "Wrap",
        "body": "Use butcher paper",
        "scope": "this_cook",
        "cook_id": 12,
    }


def test_non_cook_note_payload_clears_stale_cook() -> None:
    values = '{title: "Auger", body: "Clean monthly", scope: "gear", cook_id: "12"}'
    assert run_logic(f"console.log(JSON.stringify(logic.notePayload({values})))")["cook_id"] is None


def test_cook_options_order_and_labels() -> None:
    expression = """
      const rows = [
        {id:1,state:"closed",started_at:"2026-10-15T12:00:00Z"},
        {id:4,state:"planned",created_at:"2026-10-18T12:00:00Z",meat:{type:"Brisket"}},
        {id:3,state:"cook",started_at:"2026-10-17T12:00:00Z",ended_at:null,
         meat:{type:"Pork shoulder picnic"}},
        {id:2,state:"closed",started_at:"2026-10-16T12:00:00Z",meat:{type:"Ribs"}},
      ];
      const ordered = logic.orderNoteCookOptions(rows);
      console.log(JSON.stringify({
        ids: ordered.map(row => row.id),
        labels: ordered.map(row => logic.cookOptionLabel(row, "en-US")),
      }));
    """
    assert run_logic(expression) == {
        "ids": [4, 3, 2, 1],
        "labels": [
            "Cook #4 - Oct 18 - Brisket (Planned)",
            "Cook #3 - Oct 17 - Pork shoulder picnic (In progress)",
            "Cook #2 - Oct 16 - Ribs",
            "Cook #1 - Oct 15",
        ],
    }


def test_default_selection_prefers_live_then_planned_then_none() -> None:
    expression = """
      const closed = {id:1,state:"closed",started_at:"2026-10-15T12:00:00Z"};
      const planned = {id:2,state:"planned",created_at:"2026-10-16T12:00:00Z"};
      const live = {id:3,state:"startup",started_at:"2026-10-17T12:00:00Z",ended_at:null};
      console.log(JSON.stringify([
        logic.defaultNoteCookId([closed, planned, live]),
        logic.defaultNoteCookId([closed, planned]),
        logic.defaultNoteCookId([closed]),
        logic.defaultNoteCookId([]),
      ]));
    """
    assert run_logic(expression) == [3, 2, None, None]


def test_this_cook_target_prefers_live_then_most_recent_closed() -> None:
    expression = """
      const rows = [
        {id:1,state:"closed",started_at:"2026-10-15T12:00:00Z"},
        {id:4,state:"planned",created_at:"2026-10-18T12:00:00Z"},
        {id:3,state:"cooldown",started_at:"2026-10-17T12:00:00Z",ended_at:null},
        {id:2,state:"closed",started_at:"2026-10-16T12:00:00Z"},
      ];
      console.log(JSON.stringify({
        live: logic.thisCookTarget(rows)?.id,
        fallback: logic.thisCookTarget(rows.filter(row => row.id !== 3))?.id,
        liveLabel: logic.thisCookChipLabel(logic.thisCookTarget(rows)),
        fallbackLabel: logic.thisCookChipLabel(
          logic.thisCookTarget(rows.filter(row => row.id !== 3))),
        empty: logic.thisCookTarget([]),
        emptyLabel: logic.thisCookChipLabel(logic.thisCookTarget([])),
      }));
    """
    assert run_logic(expression) == {
        "live": 3,
        "fallback": 2,
        "liveLabel": "Cook #3, in progress",
        "fallbackLabel": "Cook #2",
        "empty": None,
        "emptyLabel": "This cook",
    }
