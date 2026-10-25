from __future__ import annotations

import json
import subprocess
from pathlib import Path


def render_history_editor() -> str:
    module = Path("app/static/js/components/live-forms.js").resolve().as_uri()
    cook = {
        "id": 12,
        "state": "closed",
        "meat_id": 1,
        "pellet_id": 2,
        "seasonings": "Salt",
        "spices": [{"id": 7, "brand": "Meat Church", "name": "Holy Cow", "size_oz": 12}],
        "sauces": "Vinegar",
        "prep_time_minutes": 20,
        "pellets_used_lb": 1.5,
        "rotisserie": True,
        "results_text": "Tender",
    }
    meat = [{"id": 1, "type": "Pork butt", "pounds": 8}]
    pellets = [{"id": 2, "vendor": "Bear Mountain", "product_name": "Hickory"}]
    photos = [{"id": 41, "url": "/api/photos/41/file"}]
    spices = json.dumps(cook["spices"])
    script = (
        f"import {{ orderPadMarkup }} from {json.dumps(module)}; "
        f"console.log(orderPadMarkup({json.dumps(cook)}, {json.dumps(meat)}, "
        f"{json.dumps(pellets)}, [{json.dumps(cook)}], "
        f'{{mode:"history", banner:"Editing cook #12", photos:{json.dumps(photos)}, '
        f"spices:{spices}}}));"
    )
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def test_history_editor_reuses_full_order_pad_and_existing_photos() -> None:
    markup = render_history_editor()

    assert "ORDER PAD" in markup
    assert "Editing cook #12" in markup
    assert 'href="#cooks/12"' in markup
    assert 'name="seasonings" value="Salt"' in markup
    assert "Choose rubs" in markup
    assert 'name="results_text"' in markup
    assert 'name="pellets_used_lb"' in markup
    assert 'name="photos" type="file"' in markup
    assert 'data-photo-id="41"' in markup
    assert 'name="meat_id" disabled' not in markup
    assert 'name="seasonings" disabled' not in markup
    assert 'name="rotisserie" value="true" checked disabled' not in markup


def test_cook_detail_routes_to_history_editor_and_returns_after_save() -> None:
    app_source = Path("app/static/js/app.js").read_text()
    view_source = Path("app/static/js/views/live.js").read_text()

    assert r"/^cooks\/(\d+)\/edit$/" in app_source
    assert 'href="#cooks/${cook.id}/edit">Edit</a>' in view_source
    assert 'mode: "history"' in view_source
    assert "window.location.hash = `cooks/${updated.id}`" in view_source
    assert "getCookLogCooks(10000)" in view_source
    assert "getCookPhotos(requestedCook.id)" in view_source
