from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path


def chart_logic(function: str, arguments: list[object]) -> object:
    module = Path("app/static/js/chart-logic.js").resolve().as_uri()
    script = (
        f'import {{ {function} }} from "{module}"; '
        f"console.log(JSON.stringify({function}(...{json.dumps(arguments)})))"
    )
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def hour_ticks(started_at: str, elapsed: int) -> object:
    module = Path("app/static/js/chart-logic.js").resolve().as_uri()
    arguments = json.dumps([started_at, elapsed, "America/Los_Angeles"])
    script = (
        f'import {{ hourTicks }} from "{module}"; '
        f"console.log(JSON.stringify(hourTicks(...{arguments})))"
    )
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def chart_markup(started_at: str, elapsed: int, cook: dict[str, object] | None = None) -> str:
    module = Path("app/static/js/components/chart.js").resolve().as_uri()
    arguments = json.dumps(
        [
            [
                {"elapsed_seconds": 0, "pit_temp": 150},
                {"elapsed_seconds": elapsed, "pit_temp": 225},
            ],
            [],
            {"started_at": started_at, **(cook or {})},
        ]
    )
    script = (
        f'import {{ chartMarkup }} from "{module}"; '
        f"console.log(chartMarkup(...{arguments}))"
    )
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def chart_markup_with_events(events: list[dict[str, object]], elapsed: int = 120) -> str:
    module = Path("app/static/js/components/chart.js").resolve().as_uri()
    samples = [
        {"elapsed_seconds": 0, "pit_temp": 150},
        {"elapsed_seconds": elapsed, "pit_temp": 225},
    ]
    arguments = json.dumps(
        [samples, events, {"started_at": "2026-10-25T22:00:00Z"}]
    )
    script = f'import {{ chartMarkup }} from "{module}"; console.log(chartMarkup(...{arguments}))'
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def target_label_positions(reached_elapsed: int, total_elapsed: int) -> tuple[float, float]:
    module = Path("app/static/js/components/chart.js").resolve().as_uri()
    samples = [
        {"elapsed_seconds": 0, "pit_temp": 225, "probe1": 180, "probe1_target": 205},
        {
            "elapsed_seconds": reached_elapsed - 1,
            "pit_temp": 225,
            "probe1": 204,
            "probe1_target": 205,
        },
        {"elapsed_seconds": reached_elapsed, "pit_temp": 225, "probe1": 205, "probe1_target": 205},
        {"elapsed_seconds": total_elapsed, "pit_temp": 75, "probe1": 205, "probe1_target": 205},
    ]
    arguments = json.dumps([samples, [], {"started_at": "2026-10-25T22:00:00Z"}])
    script = f'import {{ chartMarkup }} from "{module}"; console.log(chartMarkup(...{arguments}))'
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        check=True,
        capture_output=True,
        text=True,
    )
    done = re.search(r'<text class="target-label[^"]*"[^>]* y="([\d.]+)"', result.stdout)
    reached = re.search(r'<text class="target-marker-label"[^>]* y="([\d.]+)"', result.stdout)
    assert done is not None
    assert reached is not None
    return float(done.group(1)), float(reached.group(1))


def probe_markup(
    samples: list[dict[str, object]], active: bool = False, probe: int = 1
) -> str:
    module = Path("app/static/js/views/live.js").resolve().as_uri()
    arguments = json.dumps(
        [f"Probe {probe}", probe, samples, {"started_at": "2026-10-25T22:00:00Z"}, active]
    )
    script = f'import {{ probeBoard }} from "{module}"; console.log(probeBoard(...{arguments}))'
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def probe_cards_markup(
    channels: list[dict[str, object]], samples: list[dict[str, object]], active: bool = True
) -> str:
    module = Path("app/static/js/views/live.js").resolve().as_uri()
    arguments = json.dumps([channels, samples, {}, active])
    script = f'import {{ probeCards }} from "{module}"; console.log(probeCards(...{arguments}))'
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def hero_markup(samples: list[dict[str, object]], active: bool) -> str:
    module = Path("app/static/js/views/live.js").resolve().as_uri()
    cook = {
        "id": 6,
        "started_at": "2026-10-25T22:00:00Z",
        "ended_at": None if active else "2026-10-26T02:00:00Z",
        "status": "cook" if active else "complete",
        "startup_duration_seconds": 60,
        "cook_duration_seconds": 120,
        "cooldown_duration_seconds": 60,
    }
    arguments = json.dumps([cook, samples, active, True, None, {}])
    script = (
        "globalThis.window = {innerWidth: 1024, localStorage: {getItem() { return null; }}}; "
        f'const {{ heroMarkup }} = await import("{module}"); '
        f"console.log(heroMarkup(...{arguments}))"
    )
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def test_hour_ticks_use_local_clock_hours() -> None:
    assert hour_ticks("2026-10-25T10:01:00-07:00", 2 * 3600 + 34 * 60) == [
        {"elapsed": 3540, "label": "11 AM"},
        {"elapsed": 7140, "label": "12 PM"},
    ]


def test_hour_ticks_exclude_start_on_whole_hour() -> None:
    assert hour_ticks("2026-10-25T10:00:00-07:00", 2 * 3600) == [
        {"elapsed": 3600, "label": "11 AM"}
    ]


def test_hour_ticks_are_empty_when_no_hour_is_inside_range() -> None:
    assert hour_ticks("2026-10-25T10:01:00-07:00", 30 * 60) == []


def test_hour_ticks_are_empty_for_invalid_start() -> None:
    assert hour_ticks("not-a-date", 3 * 3600) == []


def test_hour_ticks_use_every_second_hour_for_long_cook() -> None:
    ticks = hour_ticks("2026-10-25T10:01:00-07:00", 15 * 3600)
    assert [tick["label"] for tick in ticks] == [
        "11 AM", "1 PM", "3 PM", "5 PM", "7 PM", "9 PM", "11 PM", "1 AM"
    ]
    assert [tick["elapsed"] for tick in ticks] == [
        3540, 10740, 17940, 25140, 32340, 39540, 46740, 53940
    ]


def test_hour_markers_render_as_short_bottom_axis_ticks() -> None:
    markup = chart_markup("2026-10-25T10:30:00Z", 3 * 3600)
    ticks = re.findall(r'<line class="chart-hour-tick"[^>]+>', markup)

    assert len(ticks) == 3
    assert all('y1="270" y2="278"' in tick for tick in ticks)
    assert 'class="chart-hour"' not in markup
    assert markup.count('class="chart-hour-label"') == len(ticks)


def test_finished_chart_ends_ticks_at_cooldown_start_without_total_label() -> None:
    markup = chart_markup(
        "2026-10-25T10:08:00Z",
        4200,
        {
            "status": "closed",
            "cook_ended_at": "2026-10-25T11:08:00Z",
            "startup_duration_seconds": 600,
            "cook_duration_seconds": 3000,
            "cooldown_duration_seconds": 600,
        },
    )

    assert 'class="chart-axis-end"' not in markup
    assert "chart-cooldown-label" in markup
    assert ">11:08 AM</text>" in markup
    assert ">12 PM</text>" not in markup


def test_hour_tick_too_close_to_cooldown_tick_is_dropped() -> None:
    markup = chart_markup(
        "2026-10-25T10:00:00Z",
        7200,
        {
            "status": "closed",
            "cook_ended_at": "2026-10-25T11:04:00Z",
            "startup_duration_seconds": 600,
            "cook_duration_seconds": 3240,
            "cooldown_duration_seconds": 3360,
        },
    )

    assert ">11 AM</text>" not in markup
    assert ">11:04 AM</text>" in markup


def test_chart_start_label_is_left_aligned_clock_time_only() -> None:
    markup = chart_markup("2026-10-25T10:08:00Z", 3600)

    assert 'class="chart-axis chart-axis-start"' in markup
    assert ">10:08 AM</text>" in markup
    assert "0m ·" not in markup


def test_active_chart_has_hour_ticks_and_no_cooldown_tick() -> None:
    markup = chart_markup(
        "2026-10-25T10:08:00-07:00",
        3 * 3600,
        {"status": "cook", "startup_duration_seconds": 600},
    )

    assert 'class="chart-cooldown-tick"' not in markup
    assert 'class="chart-hour-tick"' in markup


def test_event_pin_legend_lists_user_events_in_pin_order() -> None:
    markup = chart_markup_with_events([
        {"id": 10, "source": "user", "elapsed_seconds": 10, "title": "Spritzed"},
        {"id": 11, "source": "user", "elapsed_seconds": 20, "title": "Wrapped"},
        {"id": 12, "source": "user", "elapsed_seconds": 30, "title": "Sauced"},
    ])

    legend = re.search(r'<div class="event-pin-legend">(.*?)</div>\s*</section>', markup, re.S)
    assert legend is not None
    entries = re.findall(
        r'event-pin-legend-number">(\d+)</span><span>(.*?)</span>', legend.group(1)
    )
    assert entries == [
        ("1", "Spritzed"),
        ("2", "Wrapped"),
        ("3", "Sauced"),
    ]


def test_event_pin_legend_excludes_non_user_and_out_of_range_events() -> None:
    markup = chart_markup_with_events([
        {"id": 10, "source": "auto", "elapsed_seconds": 10, "title": "Fire lit"},
        {"id": 11, "source": "user", "elapsed_seconds": -1, "title": "Too early"},
        {"id": 12, "source": "user", "elapsed_seconds": 121, "title": "Too late"},
        {"id": 13, "source": "user", "elapsed_seconds": 30, "title": "Wrapped"},
    ])

    assert markup.count('class="event-pin-label"') == 1
    assert markup.count('class="event-pin-legend-entry"') == 1
    assert 'event-pin-label" x="' in markup
    assert '>1</text>' in markup
    assert 'event-pin-legend-number">1</span><span>Wrapped</span>' in markup
    assert "Fire lit" not in markup
    assert "Too early" not in markup
    assert "Too late" not in markup


def test_event_pin_legend_escapes_event_title() -> None:
    markup = chart_markup_with_events([
        {"id": 10, "source": "user", "elapsed_seconds": 10, "title": "Wrap < rest & eat"},
    ])

    assert "Wrap &lt; rest &amp; eat" in markup
    assert "Wrap < rest & eat" not in markup


def test_event_pin_legend_is_omitted_without_pinned_events() -> None:
    markup = chart_markup_with_events([])

    assert "event-pin-legend" not in markup


def test_event_pin_legend_is_present_by_default() -> None:
    markup = chart_markup_with_events([
        {"id": 10, "source": "user", "elapsed_seconds": 10, "title": "Wrapped"},
    ])

    assert 'class="event-pin-label"' in markup
    assert 'class="event-pin-legend"' in markup


def test_cooldown_label_near_right_edge_is_end_aligned() -> None:
    markup = chart_markup(
        "2026-10-25T10:00:00Z",
        3660,
        {
            "status": "closed",
            "cook_ended_at": "2026-10-25T11:00:00Z",
            "startup_duration_seconds": 600,
            "cook_duration_seconds": 3000,
            "cooldown_duration_seconds": 60,
        },
    )

    assert "chart-cooldown-label chart-hour-label-end" in markup


def test_final_target_ignores_trailing_zeroes() -> None:
    samples = [
        {"probe1_target": 203, "probe2_target": None},
        {"probe1_target": 0, "probe2_target": 0},
    ]
    assert chart_logic("finalTarget", [samples]) == {"probe": 1, "value": 203}


def test_final_target_returns_null_without_positive_target() -> None:
    samples = [
        {"probe1_target": 0},
        {"probe2_target": None},
        {"probe1_target": -10, "probe2_target": "not a number"},
    ]
    assert chart_logic("finalTarget", [samples]) is None


def test_final_target_uses_larger_target_in_last_matching_sample() -> None:
    samples = [{"probe1_target": 203, "probe2_target": 205}]
    assert chart_logic("finalTarget", [samples]) == {"probe": 2, "value": 205}


def test_reached_target_finds_first_crossing_and_ignores_nulls() -> None:
    samples = [
        {"elapsed_seconds": 10, "probe1": None},
        {"elapsed_seconds": 20, "probe1": 202},
        {"elapsed_seconds": 30, "probe1": 204},
        {"elapsed_seconds": 40, "probe1": 205},
    ]
    assert chart_logic("reachedTarget", [samples, {"probe": 1, "value": 203}]) == {
        "elapsed": 30,
        "temp": 204,
    }


def test_reached_target_returns_null_when_probe_never_crosses() -> None:
    samples = [{"elapsed_seconds": 10, "probe2": 164}]
    assert chart_logic("reachedTarget", [samples, {"probe": 2, "value": 165}]) is None


def test_reached_target_returns_null_without_a_target() -> None:
    assert chart_logic("reachedTarget", [[{"elapsed_seconds": 10, "probe1": 203}], None]) is None


def test_chart_keeps_positive_target_after_trailing_zeroes() -> None:
    module = Path("app/static/js/components/chart.js").resolve().as_uri()
    samples = [
        {"elapsed_seconds": 0, "probe1": 180, "probe1_target": 203},
        {"elapsed_seconds": 60, "probe1": 204, "probe1_target": 203},
        {"elapsed_seconds": 120, "probe1": 190, "probe1_target": 0},
    ]
    arguments = json.dumps([samples, [], {"started_at": "2026-10-25T22:00:00Z"}])
    script = f'import {{ chartMarkup }} from "{module}"; console.log(chartMarkup(...{arguments}))'
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "done at 203°" in result.stdout
    assert "target-marker" in result.stdout


def test_masterbuilt_chart_draws_four_colored_targets_with_stacked_labels() -> None:
    module = Path("app/static/js/components/chart.js").resolve().as_uri()
    targets = [220, 220, 221, 222]
    channels = [
        {
            "key": f"probe{number}",
            "label": f"Probe {number}",
            "role": "meat",
            "value": 180 + number,
            "target": target,
        }
        for number, target in enumerate(targets, start=1)
    ]
    samples = [{"elapsed_seconds": 0, "pit_temp": 250, "channels": channels}]
    arguments = json.dumps([samples, [], {"started_at": "2026-10-25T22:00:00Z"}])
    script = f'import {{ chartMarkup }} from "{module}"; console.log(chartMarkup(...{arguments}))'
    markup = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        check=True,
        capture_output=True,
        text=True,
    ).stdout

    assert markup.count('class="target-line probe-') == 4
    assert markup.count('class="target-key"') == 1
    for number, target in enumerate(targets, start=1):
        assert f'class="target-line probe-{number}-target"' in markup
        assert f"P{number} done at {target}° (not reached)" in markup
    label_ys = [
        float(value)
        for value in re.findall(r'class="target-label[^"]*"[^>]* y="([\d.]+)"', markup)
    ]
    assert len(label_ys) == 4
    assert all(
        abs(left - right) >= 22 for left, right in zip(label_ys, label_ys[1:], strict=False)
    )


def test_target_labels_are_spaced_when_target_is_reached_near_end() -> None:
    done_y, reached_y = target_label_positions(96, 100)
    assert abs(done_y - reached_y) >= 20


def test_target_labels_are_spaced_when_target_is_reached_mid_cook() -> None:
    done_y, reached_y = target_label_positions(50, 100)
    assert abs(done_y - reached_y) >= 20


def test_finished_cook_renders_both_probe_cards_as_unplugged() -> None:
    samples = [
        {"elapsed_seconds": 0, "probe1": 180, "probe1_target": 203, "probe2": 170},
        {"elapsed_seconds": 60, "probe1": 204, "probe1_target": 203, "probe2": 190},
    ]
    markup = probe_markup(samples, probe=1) + probe_markup(samples, probe=2)
    assert markup.count("sold out") == 2
    assert "probe-temp" not in markup
    assert "target" not in markup
    assert "peak" not in markup
    assert "reached at" not in markup
    assert "probe-progress" not in markup


def test_finished_cook_pit_gauge_reads_zero_and_keeps_setpoint() -> None:
    markup = hero_markup([{"pit_temp": 124, "setpoint": 225}], active=False)
    assert '<text class="gauge-temp" x="200" y="205">0°</text>' in markup
    assert ">124°</text>" not in markup
    assert "SETPOINT 225" in markup


def test_active_probe_card_with_zero_target_hides_progress() -> None:
    markup = probe_markup([{"probe1": 180, "probe1_target": 0}], active=True)
    assert "no target set" in markup
    assert "probe-progress" not in markup
    assert "%" not in markup
    assert "aiming for 0" not in markup


def test_active_probe_card_shows_live_temperature_and_target() -> None:
    markup = probe_markup([{"probe1": 180, "probe1_target": 203}], active=True)
    assert '<div class="probe-temp">180°</div>' in markup
    assert "aiming for 203°" in markup
    assert "probe-progress" in markup


def test_masterbuilt_probe_cards_follow_channels_and_readings() -> None:
    channels = [
        {"key": "pit", "label": "Pit", "role": "pit"},
        *[
            {"key": f"probe{number}", "label": f"Probe {number}", "role": "meat"}
            for number in range(1, 5)
        ],
    ]
    samples = [{
        "channels": [
            {**channel, "value": value, "target": None}
            for channel, value in zip(channels, [300, 155, None, 165, None], strict=True)
        ]
    }]

    markup = probe_cards_markup(channels, samples)

    assert markup.count('class="board probe-board') == 4
    assert "Probe 1" in markup and "Probe 4" in markup
    assert '<div class="probe-temp">155°</div>' in markup
    assert '<div class="probe-temp">165°</div>' in markup
    assert markup.count("sold out") == 2


def test_probe_cards_are_empty_without_meat_channels() -> None:
    channels = [{"key": "pit", "label": "Pit", "role": "pit"}]
    assert probe_cards_markup(channels, [{"channels": channels}]).strip() == ""


def test_probe_card_count_changes_with_connected_grill_channels() -> None:
    gmg = [
        {"key": f"probe{number}", "label": f"Probe {number}", "role": "meat"}
        for number in range(1, 3)
    ]
    masterbuilt = [
        {"key": f"probe{number}", "label": f"Probe {number}", "role": "meat"}
        for number in range(1, 5)
    ]

    assert probe_cards_markup(gmg, []).count('class="board probe-board') == 2
    assert probe_cards_markup(masterbuilt, []).count('class="board probe-board') == 4


def test_chart_shows_all_recorded_probe_channels() -> None:
    module = Path("app/static/js/components/chart.js").resolve().as_uri()
    channels = [
        {"key": f"probe{number}", "label": f"Probe {number}", "role": "meat", "value": 150 + number}
        for number in range(1, 5)
    ]
    samples = [{"elapsed_seconds": 0, "pit_temp": 225, "channels": channels}]
    arguments = json.dumps([samples, [], {"started_at": "2026-10-25T22:00:00Z"}])
    script = f'import {{ chartMarkup }} from "{module}"; console.log(chartMarkup(...{arguments}))'
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script], check=True,
        capture_output=True, text=True,
    ).stdout

    assert result.count('class="probe-line probe-') == 4
    assert "Probe 3" in result and "Probe 4" in result
