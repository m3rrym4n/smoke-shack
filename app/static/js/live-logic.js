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

export const ORDER_PAD_BANNERS = {
  live: "Cook in progress",
  planned: "Next order, will be used when the grill starts",
  new: "New order for the next cook",
};

export function orderPlannedCooks(cooks) {
  return [...cooks].sort((left, right) => {
    const leftTime = Date.parse(left.created_at || "") || 0;
    const rightTime = Date.parse(right.created_at || "") || 0;
    return leftTime - rightTime || left.id - right.id;
  });
}

export function selectOrderPadMode(activeCook, plannedCooks, closedCook = null) {
  if (closedCook) {
    return { mode: "closed", cook: closedCook, banner: `Editing closed cook #${closedCook.id}: how it turned out` };
  }
  if (activeCook) return { mode: "live", cook: activeCook, banner: ORDER_PAD_BANNERS.live };
  const planned = orderPlannedCooks(plannedCooks);
  if (planned.length) return { mode: "planned", cook: planned[0], banner: ORDER_PAD_BANNERS.planned };
  return { mode: "new", cook: null, banner: ORDER_PAD_BANNERS.new };
}

export function closedCookReadOnlyFields() {
  return ["meat_id", "seasonings", "sauces", "prep_time_minutes", "pellet_id", "rotisserie"];
}

export function eligibleMeat(meat, cooks, cookId = null) {
  const usedElsewhere = new Set(cooks
    .filter((cook) => cook.id !== cookId && cook.meat_id != null)
    .map((cook) => cook.meat_id));
  return meat.filter((item) => !usedElsewhere.has(item.id));
}

export function orderPadSavedMessage(mode) {
  return mode === "new"
    ? "Saved. It will be picked up automatically when the grill starts."
    : "Order saved.";
}
