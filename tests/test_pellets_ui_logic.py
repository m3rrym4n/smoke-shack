from __future__ import annotations

import json
import subprocess
from pathlib import Path


def run_logic(expression: str, imports: str = "validatePellet") -> object:
    module = Path("app/static/js/pellets-logic.js").resolve().as_uri()
    script = f'import {{ {imports} }} from "{module}"; {expression}'
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_pellet_validation_accepts_complete_purchase() -> None:
    values = (
        '{type: "pellets", vendor: "Bear Mountain", product_name: "Hickory", '
        'price_per_pound: "0.65", purchased_on: "2026-10-17"}'
    )
    assert run_logic(f"console.log(JSON.stringify(validatePellet({values})))") == {}


def test_pellet_validation_accepts_free_pellets() -> None:
    values = (
        '{type: "wood", vendor: "Neighbor", product_name: "Competition blend", '
        'price_per_pound: "0", purchased_on: "2026-10-17"}'
    )
    assert run_logic(f"console.log(JSON.stringify(validatePellet({values})))") == {}


def test_pellet_validation_rejects_missing_and_invalid_values() -> None:
    values = '{type: "", vendor: "", product_name: " ", price_per_pound: "-1", purchased_on: ""}'
    errors = run_logic(f"console.log(JSON.stringify(validatePellet({values})))")
    assert errors == {
        "type": "Choose a fuel type.",
        "vendor": "Enter a fuel vendor.",
        "product_name": "Enter a product name.",
        "price_per_pound": "Price per pound cannot be negative.",
        "purchased_on": "Choose a purchase date.",
    }


def test_upc_cleaning_validation_and_leading_zeros() -> None:
    expression = (
        "console.log(JSON.stringify([cleanUpc('0 12345-67890 5'), "
        "validateUpc('0000-0000'), validateUpc('1234567'), validateUpc('1234567A')]))"
    )
    assert run_logic(expression, "cleanUpc, validateUpc") == [
        "012345678905",
        "",
        "UPC must be 8 to 14 digits.",
        "UPC must be 8 to 14 digits.",
    ]


def test_optional_bag_size_validation() -> None:
    expression = (
        "console.log(JSON.stringify("
        "['', '2.5', '100', '0', '100.01'].map(validateBagSize)))"
    )
    assert run_logic(expression, "validateBagSize") == [
        "",
        "",
        "",
        "Bag size must be greater than 0 and no more than 100 lb.",
        "Bag size must be greater than 0 and no more than 100 lb.",
    ]


def test_bag_cost_display_uses_api_value_only_when_pricing_is_complete() -> None:
    expression = (
        "console.log(JSON.stringify([bagCostDisplay("
        "{bag_size_lb:20,price_per_pound:1.23,bag_cost:24.6}),bagCostDisplay("
        "{bag_size_lb:null,price_per_pound:1.23,bag_cost:null})]))"
    )
    assert run_logic(expression, "bagCostDisplay") == ["$24.60/bag", ""]


def test_split_pellets_separates_stock_and_empty_bags() -> None:
    expression = (
        "const result=splitPellets([{id:1,is_empty:false},{id:2,is_empty:true},"
        "{id:3,is_empty:false}]);console.log(JSON.stringify(result))"
    )
    assert run_logic(expression, "splitPellets") == {
        "inStock": [{"id": 1, "is_empty": False}, {"id": 3, "is_empty": False}],
        "empty": [{"id": 2, "is_empty": True}],
    }


def test_pantry_loads_empty_bags_and_order_pad_uses_default_filter() -> None:
    pantry = Path("app/static/js/views/pellets.js").read_text()
    live = Path("app/static/js/views/live.js").read_text()
    assert "getFuel(typeFilter.value, upc, true)" in pantry
    assert "getFuel()" in live


def test_fuel_page_has_required_type_forms_filter_and_all_types() -> None:
    pantry = Path("app/static/js/views/pellets.js").read_text()
    assert '<h1 class="hd">Fuel</h1>' in pantry
    assert 'name="type" required' in pantry
    assert 'name="type_filter"' in pantry
    assert '["pellets", "charcoal", "wood"]' in pantry
    assert "item.type[0].toUpperCase()" in pantry
    assert "Mark empty" in pantry
    assert "Undo" in pantry
    assert "Empty bags" in pantry
