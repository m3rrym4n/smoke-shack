from __future__ import annotations

import json
import subprocess
from pathlib import Path


def run_logic(expression: str) -> object:
    module = Path("app/static/js/pellets-logic.js").resolve().as_uri()
    script = f'import {{ validatePellet }} from "{module}"; {expression}'
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_pellet_validation_accepts_complete_purchase() -> None:
    values = (
        '{vendor: "Bear Mountain", product_name: "Hickory", '
        'price_per_pound: "0.65", purchased_on: "2026-10-17"}'
    )
    assert run_logic(f"console.log(JSON.stringify(validatePellet({values})))") == {}


def test_pellet_validation_accepts_free_pellets() -> None:
    values = (
        '{vendor: "Neighbor", product_name: "Competition blend", '
        'price_per_pound: "0", purchased_on: "2026-10-17"}'
    )
    assert run_logic(f"console.log(JSON.stringify(validatePellet({values})))") == {}


def test_pellet_validation_rejects_missing_and_invalid_values() -> None:
    values = '{vendor: "", product_name: " ", price_per_pound: "-1", purchased_on: ""}'
    errors = run_logic(f"console.log(JSON.stringify(validatePellet({values})))")
    assert errors == {
        "vendor": "Enter a pellet vendor.",
        "product_name": "Enter a product name.",
        "price_per_pound": "Price per pound cannot be negative.",
        "purchased_on": "Choose a purchase date.",
    }
