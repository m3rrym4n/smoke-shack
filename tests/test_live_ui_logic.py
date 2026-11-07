from __future__ import annotations

import json
import subprocess
from pathlib import Path


def run_logic(expression: str) -> object:
    module = Path("app/static/js/live-logic.js").resolve().as_uri()
    script = f'import * as logic from "{module}"; {expression}'
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_order_pad_mode_priority_and_banners() -> None:
    expression = """
      const active = {id: 9};
      const plans = [{id: 3, created_at: "2026-10-17T02:00:00Z"},
                     {id: 2, created_at: "2026-10-17T01:00:00Z"}];
      const values = [
        logic.selectOrderPadMode(active, plans),
        logic.selectOrderPadMode(null, plans),
        logic.selectOrderPadMode(null, []),
        logic.selectOrderPadMode(active, plans, {id: 7}),
      ].map(item => ({mode: item.mode, id: item.cook?.id ?? null, banner: item.banner}));
      console.log(JSON.stringify(values));
    """
    assert run_logic(expression) == [
        {"mode": "live", "id": 9, "banner": "Cook in progress"},
        {
            "mode": "planned",
            "id": 2,
            "banner": "Next order, will be used when the grill starts",
        },
        {"mode": "new", "id": None, "banner": "New order for the next cook"},
        {
            "mode": "closed",
            "id": 7,
            "banner": "Editing closed cook #7: how it turned out",
        },
    ]


def test_closed_fields_meat_eligibility_and_saved_message() -> None:
    expression = """
      console.log(JSON.stringify({
        fields: logic.closedCookReadOnlyFields(),
        meat: logic.eligibleMeat([{id:1},{id:2},{id:3}],
          [{id:10,meat_id:1,state:"closed"},{id:11,meat_id:2,state:"closed"}], 10)
          .map(item => item.id),
        messages: [logic.orderPadSavedMessage("new"), logic.orderPadSavedMessage("planned")],
      }));
    """
    assert run_logic(expression) == {
        "fields": [
            "meat_id",
            "seasonings",
            "sauces",
            "prep_time_minutes",
            "pellet_id",
            "rotisserie",
        ],
        "meat": [1, 3],
        "messages": [
            "Saved. It will be picked up automatically when the grill starts.",
            "Order saved.",
        ],
    }


def test_planned_orders_are_oldest_first() -> None:
    expression = """
      const plans = [{id:8,created_at:"2026-10-17T03:00:00Z"},
                     {id:4,created_at:"2026-10-17T01:00:00Z"},
                     {id:6,created_at:"2026-10-17T02:00:00Z"}];
      console.log(JSON.stringify(logic.orderPlannedCooks(plans).map(item => item.id)));
    """
    assert run_logic(expression) == [4, 6, 8]


def test_photo_validation_and_error_messages() -> None:
    expression = """
      console.log(JSON.stringify({
        valid: logic.validatePhotoFile({type:"image/jpeg",size:10}),
        type: logic.validatePhotoFile({type:"image/gif",size:10}),
        empty: logic.validatePhotoFile({type:"image/png",size:0}),
        api: logic.photoErrorMessage(new Error("Photo exceeds 15 MB limit")),
        fallback: logic.photoErrorMessage({}),
      }));
    """
    assert run_logic(expression) == {
        "valid": "",
        "type": "Choose a JPEG, PNG, or WebP photo.",
        "empty": "This photo is empty.",
        "api": "Photo exceeds 15 MB limit",
        "fallback": "Could not send this photo. Please try again.",
    }


def test_photo_downscale_size_preserves_aspect_ratio_and_avoids_upscaling() -> None:
    expression = """
      console.log(JSON.stringify([
        logic.downscaleSize(4000, 3000),
        logic.downscaleSize(1200, 800),
        logic.downscaleSize(1000, 3000),
      ]));
    """
    assert run_logic(expression) == [
        {"width": 2000, "height": 1500},
        {"width": 1200, "height": 800},
        {"width": 667, "height": 2000},
    ]


def test_photos_are_ordered_oldest_first_without_mutating_input() -> None:
    expression = """
      const photos = [{id:9},{id:2},{id:5}];
      const ordered = logic.orderPhotos(photos);
      console.log(JSON.stringify({ordered: ordered.map(item => item.id),
                                  original: photos.map(item => item.id)}));
    """
    assert run_logic(expression) == {"ordered": [2, 5, 9], "original": [9, 2, 5]}


def test_showcase_file_validation() -> None:
    expression = """
      console.log(JSON.stringify([
        logic.validateShowcaseFile({type:"image/png",size:123}, "photo"),
        logic.validateShowcaseFile({type:"image/svg+xml",size:123}, "logo"),
        logic.validateShowcaseFile({type:"image/svg+xml",size:123}, "photo"),
        logic.validateShowcaseFile({type:"image/gif",size:123}, "logo"),
        logic.validateShowcaseFile({type:"image/jpeg",size:0}),
        logic.validateShowcaseFile({type:"image/webp",size:5*1024*1024+1}),
      ]));
    """
    assert run_logic(expression) == [
        "",
        "",
        "Choose a PNG, JPEG, or WebP image.",
        "Choose a PNG, JPEG, WebP, or SVG image.",
        "This image is empty.",
        "Image must be 5 MB or smaller.",
    ]


def test_logo_picker_accepts_svg_but_photo_picker_does_not() -> None:
    settings = Path("app/static/js/settings-logic.js").read_text()
    assert '"image/png,image/jpeg,image/webp,.svg,image/svg+xml"' in settings
    assert '"image/png,image/jpeg,image/webp"' in settings


def test_gauge_logo_geometry_and_placeholder() -> None:
    module = Path("app/static/js/components/gauge.js").resolve().as_uri()
    script = f"""
      const gauge = await import({json.dumps(module)});
      console.log(JSON.stringify({{
        standard: gauge.gaugeLogoGeometry(400, 400),
        wide: gauge.gaugeLogoGeometry(1000, 400),
        placeholder: gauge.gaugeLogoMarkup(null),
        image: gauge.gaugeLogoMarkup("/api/showcase/logo"),
        svg: gauge.gaugeSvg(225, 250),
      }}));
    """
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        check=True,
        capture_output=True,
        text=True,
    )
    rendered = json.loads(result.stdout)
    assert rendered["standard"] == {"x": 140, "y": 272, "width": 120, "height": 56}
    assert rendered["wide"] == {"x": 350, "y": 272, "width": 300, "height": 56}
    assert ">logo</text>" in rendered["placeholder"]
    assert "GREEN MOUNTAIN GRILLS" not in rendered["placeholder"]
    assert "<image" not in rendered["placeholder"]
    assert ">logo</text>" not in rendered["image"]
    assert 'preserveAspectRatio="xMidYMid meet"' in rendered["image"]
    assert "SMOKE-STACK" not in rendered["svg"]


def test_showcase_layout_and_stack_clamping() -> None:
    expression = """
      console.log(JSON.stringify({
        layouts: [logic.showcaseLayoutClass(320), logic.showcaseLayoutClass(601)],
        positions: [logic.clampStackPosition(-8, 50), logic.clampStackPosition(38, 50),
                    logic.clampStackPosition(108, 5), logic.clampStackPosition("bad", 5)],
      }));
    """
    assert run_logic(expression) == {
        "layouts": ["showcase-mobile", "showcase-wide"],
        "positions": [0, 38, 100, 5],
    }


def test_showcase_title_and_maker_rendering_rules() -> None:
    expression = """
      console.log(JSON.stringify([
        logic.showcaseNameLines({grill_title:"Daniel Boone",
          grill_maker:"Green Mountain Grills", grill_name:"Friendly"}),
        logic.showcaseNameLines({grill_title:"Daniel Boone", grill_maker:null}),
        logic.showcaseNameLines({grill_name:"Friendly"}),
        logic.showcaseNameLines({}),
      ]));
    """
    assert run_logic(expression) == [
        {"title": "Daniel Boone", "maker": "Green Mountain Grills"},
        {"title": "Daniel Boone", "maker": ""},
        {"title": "Friendly", "maker": ""},
        {"title": "", "maker": ""},
    ]

    component = Path("app/static/js/components/showcase.js").read_text()
    assert "title.textContent = name.title" in component
    assert "maker.textContent = name.maker" in component
    assert "Change pictures" not in component
    assert "showcase-editor" not in component


def test_historical_grill_picker_lists_existing_grills() -> None:
    module = Path("app/static/js/views/live.js").resolve().as_uri()
    script = f'''import {{ grillPickerMarkup }} from {json.dumps(module)};
      console.log(JSON.stringify({{
        choices: grillPickerMarkup([
          {{equipment_id: 1, maker: "Masterbuilt", model: "Gravity Series 800"}},
          {{equipment_id: 2, maker: "Green Mountain Grills", model: "Daniel Boone"}},
        ]),
        none: grillPickerMarkup([]),
        undiscovered: grillPickerMarkup([{{equipment_id: null, name: "Unknown"}}]),
      }}));'''
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        check=True,
        capture_output=True,
        text=True,
    )
    rendered = json.loads(result.stdout)
    assert "Choose grill" in rendered["choices"]
    assert "Masterbuilt Gravity Series 800" in rendered["choices"]
    assert "Green Mountain Grills Daniel Boone" in rendered["choices"]
    assert rendered["none"] == ""
    assert rendered["undiscovered"] == ""


def test_showcase_anchor_persistence_clamps_and_defaults() -> None:
    expression = """
      const values = new Map();
      const storage = {
        getItem: key => values.get(key) ?? null,
        setItem: (key, value) => values.set(key, value),
      };
      const defaults = logic.readStackPosition(storage, "anchor");
      const saved = logic.writeStackPosition(storage, "anchor", {x: -12, y: 140});
      const restored = logic.readStackPosition(storage, "anchor");
      values.set("anchor", "not json");
      const malformed = logic.readStackPosition(storage, "anchor");
      console.log(JSON.stringify({defaults, saved, restored, malformed}));
    """
    assert run_logic(expression) == {
        "defaults": {"x": 50, "y": 5},
        "saved": {"x": 0, "y": 100},
        "restored": {"x": 0, "y": 100},
        "malformed": {"x": 50, "y": 5},
    }
