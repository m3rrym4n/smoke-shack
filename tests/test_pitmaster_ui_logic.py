from __future__ import annotations

import json
import subprocess
from pathlib import Path


def run_logic(expression: str) -> object:
    module = Path("app/static/js/pitmaster-logic.js").resolve().as_uri()
    script = f'import * as logic from "{module}"; {expression}'
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_formats_durations_as_hours_and_minutes() -> None:
    assert run_logic("console.log(JSON.stringify(logic.formatDuration(19200)))") == "5:20"
    assert run_logic("console.log(JSON.stringify(logic.formatDuration(null)))") == "—"


def test_builds_plain_language_answer_from_set_filters() -> None:
    filters = '{meat:"Pork butt",poundsMin:"4",poundsMax:"4",setpoint:"275",rotisserie:"false"}'
    stats = '{count:3,cook_seconds:{avg:19200}}'
    expression = f"console.log(JSON.stringify(logic.buildAnswerSentence({filters},{stats})))"
    assert run_logic(expression) == (
        "Based on 3 cooks: a 4 lb Pork butt at 275°F without the rotisserie averages 5h 20m."
    )


def test_builds_no_match_signage_answer() -> None:
    expression = 'console.log(JSON.stringify(logic.buildAnswerSentence({}, {count:0})))'
    assert run_logic(expression) == (
        "No cooks match that order yet. Give the pitmaster something to work with."
    )


def test_builds_no_cooks_answer_for_selected_meat() -> None:
    expression = (
        'console.log(JSON.stringify(logic.buildAnswerSentence({meat:"Pork picnic shoulder"}, '
        '{count:0})))'
    )
    assert run_logic(expression) == "No cooks logged yet for Pork picnic shoulder."


def test_merges_meat_types_from_cooks_and_butcher_case() -> None:
    stats = '[{meat_type:"Brisket",count:2},{meat_type:"pork BUTT",count:3}]'
    meat = '[{type:"Pork butt"},{type:"Chicken"}]'
    expression = f"console.log(JSON.stringify(logic.mergeMeatTypeOptions({stats},{meat},'')))"
    assert run_logic(expression) == [
        {"value": "Brisket", "label": "Brisket (2)", "count": 2},
        {"value": "Chicken", "label": "Chicken (no cooks yet)", "count": 0},
        {"value": "pork BUTT", "label": "pork BUTT (3)", "count": 3},
    ]


def test_builds_groups_first_with_combined_counts_and_only_ungrouped_types() -> None:
    groups = '[{id:7,name:"Pork shoulder",types:["pork butt","pork picnic"]}]'
    stats = (
        '[{meat_type:"Pork Butt",count:2,group_id:7},'
        '{meat_type:"Pork Picnic",count:3,group_id:7},'
        '{meat_type:"Brisket",count:1,group_id:null}]'
    )
    meat = '[{type:"Pork Butt"},{type:"Turkey"}]'
    expression = (
        f"console.log(JSON.stringify(logic.buildMeatOptions({groups},{stats},{meat},{{}})))"
    )
    assert run_logic(expression) == [
        {
            "kind": "group", "value": "7", "label": "Pork shoulder (5)",
            "name": "Pork shoulder", "count": 5,
        },
        {"kind": "type", "value": "Brisket", "label": "Brisket (1)", "count": 1, "name": "Brisket"},
        {
            "kind": "type", "value": "Turkey", "label": "Turkey (no cooks yet)",
            "count": 0, "name": "Turkey",
        },
    ]


def test_merges_meat_types_with_an_empty_butcher_case() -> None:
    expression = (
        'console.log(JSON.stringify(logic.mergeMeatTypeOptions('
        '[{meat_type:"Ribs",count:4}],[],"")))'
    )
    assert run_logic(expression) == [
        {"value": "Ribs", "label": "Ribs (4)", "count": 4},
    ]


def test_merges_meat_types_with_empty_stats() -> None:
    expression = (
        'console.log(JSON.stringify(logic.mergeMeatTypeOptions('
        '[],[{type:"Turkey"}],"")))'
    )
    assert run_logic(expression) == [
        {"value": "Turkey", "label": "Turkey (no cooks yet)", "count": 0},
    ]


def test_merge_keeps_unknown_selected_meat_type() -> None:
    expression = (
        'console.log(JSON.stringify(logic.mergeMeatTypeOptions([],[],"Venison")))'
    )
    assert run_logic(expression) == [
        {"value": "Venison", "label": "Venison (no cooks yet)", "count": 0},
    ]


def test_merge_keeps_selected_value_when_capitalization_differs() -> None:
    expression = (
        'console.log(JSON.stringify(logic.mergeMeatTypeOptions('
        '[{meat_type:"PORK BUTT",count:2}],[],"Pork butt")))'
    )
    assert run_logic(expression) == [
        {"value": "Pork butt", "label": "Pork butt (2)", "count": 2},
    ]


def test_hash_round_trip_and_api_query_use_exact_supported_names() -> None:
    filters = (
        '{meat:"Brisket",poundsMin:"8",poundsMax:"12",setpoint:"250",tolerance:"15",'
        'rotisserie:"true",pelletId:"42"}'
    )
    expression = (
        f"console.log(JSON.stringify(logic.filtersFromHash(logic.filtersToHash({filters}))))"
    )
    assert run_logic(expression) == {
        "meat": "Brisket", "poundsMin": "8", "poundsMax": "12", "setpoint": "250",
        "tolerance": "15", "rotisserie": "true", "pelletId": "42", "meatGroup": "",
    }
    query = f"console.log(JSON.stringify(logic.statsQuery({filters}).toString()))"
    assert run_logic(query) == (
        "meat_type=Brisket&pounds_min=8&pounds_max=12&setpoint=250&"
        "setpoint_tolerance=15&rotisserie=true&pellet_id=42"
    )


def test_group_hash_round_trip_and_stats_query_never_send_both_meat_filters() -> None:
    filters = '{meat:"Brisket",meatGroup:"7",rotisserie:"false"}'
    expression = (
        f"console.log(JSON.stringify(logic.filtersFromHash(logic.filtersToHash({filters}))))"
    )
    assert run_logic(expression) == {
        "meat": "", "meatGroup": "7", "poundsMin": "", "poundsMax": "",
        "setpoint": "", "tolerance": "10", "rotisserie": "false", "pelletId": "",
    }
    query = f"console.log(JSON.stringify(logic.statsQuery({filters}).toString()))"
    assert run_logic(query) == "meat_group=7&rotisserie=false"


def test_group_name_is_the_answer_subject() -> None:
    filters = (
        '{meatGroup:"7",meatGroupName:"Pork shoulder",poundsMin:"5",'
        'poundsMax:"8",rotisserie:"false"}'
    )
    stats = '{count:2,cook_seconds:{avg:18000}}'
    expression = f"console.log(JSON.stringify(logic.buildAnswerSentence({filters},{stats})))"
    assert run_logic(expression) == (
        "Based on 2 cooks: a 5–8 lb Pork shoulder without the rotisserie averages 5h."
    )


def test_rotisserie_defaults_to_no_for_empty_and_old_hashes() -> None:
    expression = (
        'console.log(JSON.stringify(['
        'logic.filtersFromHash("#pitmaster").rotisserie,'
        'logic.filtersFromHash("#pitmaster?meat=Ribs").rotisserie,'
        'logic.filtersToHash({})]))'
    )
    assert run_logic(expression) == ["false", "false", "#pitmaster?rotisserie=false"]


def test_pitmaster_form_uses_one_pellet_select_and_no_store() -> None:
    source = Path("app/static/js/views/pitmaster.js").read_text()
    assert 'name="pellet_id"' in source
    assert "Any pellets" in source
    assert 'name="pellet_vendor"' not in source
    assert 'name="pellet_product"' not in source
    assert 'name="store"' not in source


def test_calculates_average_cook_time_per_pound() -> None:
    cooks = '[{cook_seconds:14400,pounds:4},{cook_seconds:21600,pounds:6}]'
    assert run_logic(f"console.log(JSON.stringify(logic.cookTimePerPound({cooks})))") == 3600
