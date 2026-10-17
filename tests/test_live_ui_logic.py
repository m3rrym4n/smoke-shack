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
