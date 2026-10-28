from __future__ import annotations

import json
import subprocess
from pathlib import Path


def run_logic(expression: str) -> object:
    module = Path("app/static/js/pantry-logic.js").resolve().as_uri()
    script = (
        f'import {{ legacyPantryRedirect, parsePantryRoute }} from "{module}"; '
        f"{expression}"
    )
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_pantry_routes_select_the_expected_tab() -> None:
    expression = (
        'console.log(JSON.stringify(["#pantry", "#pantry/pellets", '
        '"#pantry/meat", "#pantry/spices"].map(parsePantryRoute)))'
    )
    assert run_logic(expression) == [
        {"name": "pantry", "nav": "pantry", "pantryTab": "pellets"},
        {"name": "pantry", "nav": "pantry", "pantryTab": "pellets"},
        {"name": "pantry", "nav": "pantry", "pantryTab": "meat"},
        {"name": "pantry", "nav": "pantry", "pantryTab": "spices"},
    ]


def test_invalid_pantry_routes_do_not_parse() -> None:
    expression = (
        'console.log(JSON.stringify(["#pantry/unknown", "#pantry/meat/more", '
        '"#notes"].map(parsePantryRoute)))'
    )
    assert run_logic(expression) == [None, None, None]


def test_legacy_inventory_routes_redirect_to_pantry() -> None:
    expression = (
        'console.log(JSON.stringify(["#pellets", "#meat", "#notes"]'
        ".map(legacyPantryRedirect)))"
    )
    assert run_logic(expression) == ["#pantry/pellets", "#pantry/meat", None]
