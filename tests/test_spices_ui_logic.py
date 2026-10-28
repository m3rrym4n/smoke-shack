from __future__ import annotations

import json
import subprocess
from pathlib import Path


def run_logic(expression: str) -> object:
    module = Path("app/static/js/spices-logic.js").resolve().as_uri()
    names = "filterSpices, formatSpicePrice, formatSpiceSize, groupSpices"
    script = f'import {{ {names} }} from "{module}"; {expression}'
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_spices_group_by_brand_and_order_case_insensitively() -> None:
    items = json.dumps([
        {"id": 3, "brand": "Zulu", "name": "Sweet"},
        {"id": 2, "brand": "alpha", "name": "Hot"},
        {"id": 1, "brand": "Alpha", "name": "Garlic"},
    ])
    expression = (f"console.log(JSON.stringify(groupSpices({items}).map(group => "
                  "[group.brand, group.items.map(item => item.name)])))")
    assert run_logic(expression) == [["Alpha", ["Garlic", "Hot"]], ["Zulu", ["Sweet"]]]


def test_spice_price_and_size_formatting_omit_missing_values() -> None:
    expression = ("console.log(JSON.stringify([formatSpicePrice(9.95), formatSpicePrice(null), "
                  "formatSpiceSize(12.5), formatSpiceSize(undefined)]))")
    assert run_logic(expression) == ["$9.95", "", "12.5 oz", ""]


def test_spice_filter_matches_brand_or_name_case_insensitively() -> None:
    items = json.dumps([
        {"id": 1, "brand": "Meat Church", "name": "Holy Cow"},
        {"id": 2, "brand": "Custom", "name": "House blend"},
    ])
    expression = (
        f"console.log(JSON.stringify([filterSpices({items}, 'CHURCH').map(x => x.id), "
        f"filterSpices({items}, 'house').map(x => x.id), "
        f"filterSpices({items}, '').length]))"
    )
    assert run_logic(expression) == [[1], [2], 2]
