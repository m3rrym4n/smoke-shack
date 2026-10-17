from __future__ import annotations

import json
import subprocess
from pathlib import Path


def run_logic(expression: str) -> object:
    module = Path("app/static/js/smoke-logic.js").resolve().as_uri()
    script = f'import * as logic from "{module}"; {expression}'
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_smoke_intensity_follows_cook_and_fire_state() -> None:
    expression = """
      console.log(JSON.stringify([
        logic.smokeIntensity("startup", "Startup"),
        logic.smokeIntensity("startup", "Ignition"),
        logic.smokeIntensity("cook", "Running"),
        logic.smokeIntensity("cook", "Heating"),
        logic.smokeIntensity("cooldown", "Cool Down"),
        logic.smokeIntensity("cook", "Off"),
        logic.smokeIntensity("closed", "Running"),
      ]));
    """
    assert run_logic(expression) == [0.9, 0.9, 0.58, 0.75, 0.12, 0, 0]


def test_demo_mode_only_matches_live_smoke_demo_query() -> None:
    expression = """
      console.log(JSON.stringify([
        logic.smokeDemoMode("#live?smoke=demo"),
        logic.smokeDemoMode("live?order=3&smoke=demo"),
        logic.smokeDemoMode("#cooks?smoke=demo"),
        logic.smokeDemoMode("#live?smoke=off"),
      ]));
    """
    assert run_logic(expression) == [True, True, False, False]


def test_value_noise_is_deterministic_smooth_and_seeded() -> None:
    expression = """
      const first = logic.valueNoise2D(3.25, 7.75, 42);
      console.log(JSON.stringify({
        first, repeat: logic.valueNoise2D(3.25, 7.75, 42),
        nearby: logic.valueNoise2D(3.251, 7.751, 42),
        seeded: logic.valueNoise2D(3.25, 7.75, 43),
      }));
    """
    result = run_logic(expression)
    assert result["first"] == result["repeat"]
    assert abs(result["first"] - result["nearby"]) < 0.01
    assert result["first"] != result["seeded"]
    assert -1 <= result["first"] <= 1


def test_should_animate_requires_every_runtime_condition() -> None:
    expression = """
      const base = {liveCook:true,intensity:1,reducedMotion:false,hidden:false,
                    enabled:true,anchor:{x:20,y:30}};
      console.log(JSON.stringify([
        logic.shouldAnimateSmoke(base),
        logic.shouldAnimateSmoke({...base,liveCook:false}),
        logic.shouldAnimateSmoke({...base,intensity:0}),
        logic.shouldAnimateSmoke({...base,reducedMotion:true}),
        logic.shouldAnimateSmoke({...base,hidden:true}),
        logic.shouldAnimateSmoke({...base,enabled:false}),
        logic.shouldAnimateSmoke({...base,anchor:null}),
      ]));
    """
    assert run_logic(expression) == [True, False, False, False, False, False, False]


def test_particle_spawn_update_fade_and_removal() -> None:
    expression = """
      const particle = logic.spawnParticle({x:100,y:200}, () => 0.5, 0.75);
      let moving = particle;
      for (let index = 0; index < 10; index++)
        moving = logic.updateParticle(moving, 0.1, {emitting:true,wind:2});
      let fading = moving;
      for (let index = 0; index < 15; index++)
        fading = logic.updateParticle(fading, 0.1, {emitting:false});
      let removed = fading;
      for (let index = 0; index < 18; index++)
        removed = logic.updateParticle(removed, 0.1, {emitting:false});
      const spawn = {x:particle.x,y:particle.y,radius:particle.radius};
      console.log(JSON.stringify({spawn, moving:{x:moving.x,
        y:moving.y,radius:moving.radius,opacity:moving.opacity,remove:moving.remove},
        fading:{opacity:fading.opacity,remove:fading.remove},removed:removed.remove}));
    """
    result = run_logic(expression)
    assert result["spawn"] == {"x": 100, "y": 200, "radius": 11}
    assert result["moving"]["y"] < 200
    assert result["moving"]["radius"] > result["spawn"]["radius"]
    assert result["moving"]["opacity"] > result["fading"]["opacity"] > 0
    assert result["moving"]["remove"] is False
    assert result["fading"]["remove"] is False
    assert result["removed"] is True


def test_particle_spawn_and_update_stay_in_bounded_ranges() -> None:
    expression = """
      const values = [0, .1, .2, .3, .4, .5, .6, .7, .8, .9, .99]; let index = 0;
      const random = () => values[index++ % values.length];
      const particle = logic.spawnParticle({x:80,y:120}, random, .58);
      const updated = logic.updateParticle(particle, 5, {emitting:true,wind:100});
      console.log(JSON.stringify({particle,updated,max:logic.MAX_SMOKE_PARTICLES}));
    """
    result = run_logic(expression)
    particle = result["particle"]
    assert 71.6 <= particle["x"] <= 88.4
    assert 118 <= particle["y"] <= 122
    assert 17_000 <= particle["life"] <= 24_000
    assert 7 <= particle["radius"] <= 15
    assert result["updated"]["age"] == 100
    assert 0 <= result["updated"]["opacity"] <= 1
    assert result["max"] == 140


def test_cleanup_runs_once_in_reverse_order_and_late_tasks_immediately() -> None:
    expression = """
      const calls = []; const bag = logic.createCleanupBag();
      bag.add(() => calls.push("first")); bag.add(() => calls.push("second"));
      bag.cleanup(); bag.cleanup(); bag.add(() => calls.push("late"));
      console.log(JSON.stringify(calls));
    """
    assert run_logic(expression) == ["second", "first", "late"]
