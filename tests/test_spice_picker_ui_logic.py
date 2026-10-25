from __future__ import annotations

import json
import subprocess
from pathlib import Path

MODULE = Path("app/static/js/spice-picker-logic.js").resolve().as_uri()


def run(expression: str) -> object:
    script = (
        f'import * as logic from {json.dumps(MODULE)}; '
        f"console.log(JSON.stringify({expression}));"
    )
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_picker_add_remove_and_prevent_duplicates() -> None:
    assert run("logic.addSpice(logic.addSpice([2], 4), 4)") == [2, 4]
    assert run("logic.removeSpice([2, 4], 2)") == [4]


def test_picker_searches_brand_name_and_size() -> None:
    spices = [
        {"id": 1, "brand": "Meat Church", "name": "Holy Cow", "size_oz": 12},
        {"id": 2, "brand": "Custom", "name": "Custom blend", "size_oz": None},
    ]
    encoded = json.dumps(spices)
    assert run(f"logic.filterSpiceChoices({encoded}, 'CHURCH').map(x => x.id)") == [1]
    assert run(f"logic.filterSpiceChoices({encoded}, 'blend').map(x => x.id)") == [2]
    assert run(f"logic.filterSpiceChoices({encoded}, '12').map(x => x.id)") == [1]


def test_create_and_update_payloads_include_unique_spice_ids() -> None:
    create = run("logic.withSpiceIds({state:'planned', seasonings:'extra'}, [3, 1, 3])")
    update = run("logic.withSpiceIds({seasonings:null}, [])")
    assert create == {"state": "planned", "seasonings": "extra", "spice_ids": [3, 1]}
    assert update == {"seasonings": None, "spice_ids": []}


def test_display_text_places_rubs_before_free_text() -> None:
    cook = {
        "spices": [{"category": "Meat Church", "name": "The Holy Gospel BBQ Rub"}],
        "seasonings": "extra pepper",
    }
    assert run(f"logic.seasoningText({json.dumps(cook)})") == (
        "Meat Church The Holy Gospel BBQ Rub · extra pepper"
    )
