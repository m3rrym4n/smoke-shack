from __future__ import annotations

import json
import subprocess
from pathlib import Path


def run_logic(expression: str) -> object:
    module = Path("app/static/js/meat-logic.js").resolve().as_uri()
    script = f'import {{ totalCost, validateMeat }} from "{module}"; {expression}'
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_total_cost_rounds_to_cents() -> None:
    assert run_logic("console.log(JSON.stringify(totalCost(4.25, 3.99)))") == 16.96


def test_meat_validation_accepts_positive_numbers() -> None:
    values = (
        '{type: "Pork butt", pounds: "4.5", price_per_pound: "3.99", '
        'purchased_on: "2026-10-17"}'
    )
    assert run_logic(f"console.log(JSON.stringify(validateMeat({values})))") == {}


def test_meat_validation_rejects_non_positive_numbers() -> None:
    values = '{type: "", pounds: "0", price_per_pound: "-1", purchased_on: ""}'
    errors = run_logic(f"console.log(JSON.stringify(validateMeat({values})))")
    assert errors == {
        "type": "Enter a cut or meat type.",
        "pounds": "Pounds must be greater than zero.",
        "price_per_pound": "Price per pound must be greater than zero.",
        "purchased_on": "Choose a purchase date.",
    }
