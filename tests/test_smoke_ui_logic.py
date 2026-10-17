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
        logic.smokeIntensity("cook", "Running"),
        logic.smokeIntensity("cook", "Heating"),
        logic.smokeIntensity("cooldown", "Cool Down"),
        logic.smokeIntensity("cook", "Off"),
        logic.smokeIntensity("closed", "Running"),
      ]));
    """
    assert run_logic(expression) == [1, 1, 1, 0.22, 0, 0]


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
      const values = [0.5,0.5,0.5,0.5,0.5,0.5]; let index = 0;
      const particle = logic.spawnParticle({x:100,y:200}, () => values[index++]);
      const moving = logic.updateParticle(particle, 1, true);
      const fading = logic.updateParticle(moving, 1.5, false);
      const removed = logic.updateParticle(fading, 1.5, false);
      console.log(JSON.stringify({spawn:{x:particle.x,y:particle.y}, moving:{x:moving.x,
        y:moving.y,radius:moving.radius,opacity:moving.opacity,remove:moving.remove},
        fading:{opacity:fading.opacity,remove:fading.remove},removed:removed.remove}));
    """
    result = run_logic(expression)
    assert result["spawn"] == {"x": 100, "y": 200}
    assert result["moving"]["y"] < 200
    assert result["moving"]["radius"] > 15
    assert result["moving"]["opacity"] > result["fading"]["opacity"] > 0
    assert result["moving"]["remove"] is False
    assert result["fading"]["remove"] is False
    assert result["removed"] is True


def test_cleanup_runs_once_in_reverse_order_and_late_tasks_immediately() -> None:
    expression = """
      const calls = []; const bag = logic.createCleanupBag();
      bag.add(() => calls.push("first")); bag.add(() => calls.push("second"));
      bag.cleanup(); bag.cleanup(); bag.add(() => calls.push("late"));
      console.log(JSON.stringify(calls));
    """
    assert run_logic(expression) == ["second", "first", "late"]
