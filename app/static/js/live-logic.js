export function clampPercent(value, target) {
  const reading = Number(value);
  const goal = Number(target);
  if (!Number.isFinite(reading) || !Number.isFinite(goal) || goal <= 0) return 0;
  return Math.max(0, Math.min(100, (reading / goal) * 100));
}

function secondsBetween(start, end) {
  if (!start || !end) return 0;
  return Math.max(0, Math.round((new Date(end) - new Date(start)) / 1000));
}

export function phaseDurations(cook, now = new Date()) {
  const current = now.toISOString();
  const startupEnd = cook.startup_ended_at || (cook.status === "startup" ? current : null);
  const cookEnd = cook.cook_ended_at || (cook.status === "cook" ? current : null);
  const cooldownEnd = cook.cooldown_ended_at || (cook.status === "cooldown" ? current : null);
  const startup = cook.startup_duration_seconds ?? secondsBetween(cook.started_at, startupEnd);
  const cooking = cook.cook_duration_seconds ?? secondsBetween(cook.startup_ended_at, cookEnd);
  const cooldown = cook.cooldown_duration_seconds ?? secondsBetween(cook.cook_ended_at, cooldownEnd);
  return { startup, cook: cooking, cooldown, total: startup + cooking + cooldown };
}

export function phasePercentages(durations) {
  const total = Math.max(1, durations.total);
  return {
    startup: (durations.startup / total) * 100,
    cook: (durations.cook / total) * 100,
    cooldown: (durations.cooldown / total) * 100,
  };
}
