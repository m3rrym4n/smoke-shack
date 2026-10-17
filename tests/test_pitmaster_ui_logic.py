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


def test_hash_round_trip_and_api_query_use_exact_supported_names() -> None:
    filters = (
        '{meat:"Brisket",poundsMin:"8",poundsMax:"12",setpoint:"250",tolerance:"15",'
        'rotisserie:"true",pelletVendor:"Traeger",pelletProduct:"Hickory",store:"Market"}'
    )
    expression = (
        f"console.log(JSON.stringify(logic.filtersFromHash(logic.filtersToHash({filters}))))"
    )
    assert run_logic(expression) == {
        "meat": "Brisket", "poundsMin": "8", "poundsMax": "12", "setpoint": "250",
        "tolerance": "15", "rotisserie": "true", "pelletVendor": "Traeger",
        "pelletProduct": "Hickory", "store": "Market",
    }
    query = f"console.log(JSON.stringify(logic.statsQuery({filters}).toString()))"
    assert run_logic(query) == (
        "meat_type=Brisket&pounds_min=8&pounds_max=12&setpoint=250&"
        "setpoint_tolerance=15&rotisserie=true"
    )


def test_calculates_average_cook_time_per_pound() -> None:
    cooks = '[{cook_seconds:14400,pounds:4},{cook_seconds:21600,pounds:6}]'
    assert run_logic(f"console.log(JSON.stringify(logic.cookTimePerPound({cooks})))") == 3600
