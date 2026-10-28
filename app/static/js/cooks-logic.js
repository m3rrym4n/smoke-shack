const LIVE_STATES = new Set(["startup", "cook", "cooldown"]);

export function isLiveCook(cook) {
  return LIVE_STATES.has(cook.state) && !cook.ended_at;
}

export function cookTag(cook) {
  if (cook.exclude_from_stats) return "Test";
  if (cook.state === "planned") return "Planned";
  if (isLiveCook(cook)) return "In progress";
  if (cook.incomplete) return "Incomplete";
  return null;
}

export function elapsedSeconds(cook, now = new Date()) {
  if (!isLiveCook(cook) || !cook.started_at) return null;
  return Math.max(0, Math.floor((now.getTime() - new Date(cook.started_at).getTime()) / 1000));
}

export function formatDuration(seconds) {
  if (seconds === null || seconds === undefined || !Number.isFinite(Number(seconds))) return "—";
  const value = Math.max(0, Number(seconds));
  const hours = Math.floor(value / 3600);
  const minutes = Math.floor((value % 3600) / 60);
  return hours ? `${hours}h ${minutes}m` : `${minutes}m`;
}

function newestFirst(left, right) {
  return (Date.parse(right.started_at || "") || 0) - (Date.parse(left.started_at || "") || 0)
    || right.id - left.id;
}

export function orderCookLogRows(cooks) {
  const uniqueCooks = [...new Map(cooks.map((cook) => [cook.id, cook])).values()];
  const planned = uniqueCooks.filter((cook) => cook.state === "planned").sort((left, right) => {
    const difference = (Date.parse(left.created_at || "") || 0) - (Date.parse(right.created_at || "") || 0);
    return difference || left.id - right.id;
  });
  const live = uniqueCooks.filter(isLiveCook).sort(newestFirst);
  const closed = uniqueCooks.filter((cook) => cook.state !== "planned" && !isLiveCook(cook)).sort(newestFirst);
  return [...planned, ...live, ...closed];
}
