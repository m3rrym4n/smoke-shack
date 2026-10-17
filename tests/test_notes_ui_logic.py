from __future__ import annotations

import json
import subprocess
from pathlib import Path


def run_logic(expression: str) -> object:
    module = Path("app/static/js/notes-logic.js").resolve().as_uri()
    script = f'import {{ notePayload, validateNote }} from "{module}"; {expression}'
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_note_validation_requires_text_and_a_cook_for_cook_scope() -> None:
    expression = (
        'console.log(JSON.stringify(validateNote({title: " ", body: "", '
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
    assert run_logic(f"console.log(JSON.stringify(notePayload({values})))") == {
        "title": "Wrap",
        "body": "Use butcher paper",
        "scope": "this_cook",
        "cook_id": 12,
    }


def test_non_cook_note_payload_clears_stale_cook() -> None:
    values = '{title: "Auger", body: "Clean monthly", scope: "gear", cook_id: "12"}'
    assert run_logic(f"console.log(JSON.stringify(notePayload({values})))")["cook_id"] is None
