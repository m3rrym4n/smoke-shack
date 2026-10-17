from __future__ import annotations

import json
import subprocess
from pathlib import Path


def run_logic(expression: str) -> object:
    module = Path("app/static/js/order-pad-logic.js").resolve().as_uri()
    script = (
        f'import {{ availableMeat, meatOptionLabel, validatePelletsUsed }} from "{module}"; '
        f"{expression}"
    )
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_available_meat_excludes_other_cooks_but_keeps_current_purchase() -> None:
    expression = (
        "console.log(JSON.stringify(availableMeat([{id:1},{id:2},{id:3}], "
        "[{id:10,meat_id:1},{id:11,meat_id:2}], 10).map(item => item.id)))"
    )
    assert run_logic(expression) == [1, 3]


def test_meat_option_label_contains_purchase_details() -> None:
    expression = (
        'console.log(JSON.stringify(meatOptionLabel({type:"Pork butt",pounds:4.2,'
        'store:"Costco",purchased_on:"2026-10-12"})))'
    )
    assert run_logic(expression) == "Pork butt, 4.2 lb, Costco, Oct 12"


def test_pellets_used_validation_allows_blank_and_non_negative_values() -> None:
    expression = (
        'console.log(JSON.stringify([validatePelletsUsed(""), '
        'validatePelletsUsed("1.5"), validatePelletsUsed("-1")]))'
    )
    assert run_logic(expression) == ["", "", "Pellets used must be zero or greater."]
