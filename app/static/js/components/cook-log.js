const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (character) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
})[character]);

function elapsed(seconds) {
  if (seconds === null || seconds === undefined || !Number.isFinite(Number(seconds))) return "—";
  const value = Math.max(0, Number(seconds));
  const hours = Math.floor(value / 3600);
  const minutes = Math.floor((value % 3600) / 60);
  return hours ? `${hours}h ${minutes}m` : `${minutes}m`;
}

function timestamp(value) {
  const date = new Date(value);
  return {
    date: new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" }).format(date),
    time: new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit" }).format(date),
  };
}

const autoIcons = { fire_lit: "♨", setpoint_changed: "↗", phase_changed: "→", data_gap: "!", data_gap_summary: "!", probe_connected: "+", probe_disconnected: "−", warning: "!" };

function gapSeconds(event) {
  const start = Date.parse(event.data?.start || "");
  const end = Date.parse(event.data?.end || "");
  return Number.isFinite(start) && Number.isFinite(end) ? Math.max(0, Math.round((end - start) / 1000)) : null;
}

function shortDuration(seconds) {
  const minutes = Math.floor(seconds / 60);
  const remaining = seconds % 60;
  if (minutes && remaining) return `${minutes}m ${remaining}s`;
  return minutes ? `${minutes}m` : `${remaining}s`;
}

function wholeTemperature(value) {
  if (value === null || value === undefined || value === "") return null;
  const temperature = Number(value);
  return Number.isFinite(temperature) ? Math.round(temperature) : null;
}

export function presentEvent(event) {
  if (event.kind !== "setpoint_changed") return event;
  let newSetpoint = wholeTemperature(event.data?.to);
  if (newSetpoint === null && event.description) {
    const match = event.description.match(/\bto\s+(-?\d+(?:\.\d+)?)\s*°?\s*F\b/i);
    newSetpoint = match ? wholeTemperature(match[1]) : null;
  }
  const oldSetpoint = wholeTemperature(event.data?.from);
  return {
    ...event,
    title: newSetpoint === null ? event.title : `Setpoint changed to ${newSetpoint}°F`,
    description: event.description || (oldSetpoint === null ? null : `from ${oldSetpoint}°F`),
  };
}

export function collapseBriefDataGaps(events, thresholdSeconds = 120) {
  const collapsed = [];
  let group = [];
  const flush = () => {
    if (!group.length) return;
    const durations = group.map(gapSeconds);
    const total = durations.reduce((sum, value) => sum + value, 0);
    const first = group[0];
    collapsed.push({
      ...first,
      id: `brief-data-gaps-${first.id}`,
      ts: first.ts,
      elapsed_seconds: first.elapsed_seconds,
      kind: "data_gap_summary",
      title: `${group.length} brief data ${group.length === 1 ? "gap" : "gaps"} (${shortDuration(total)} total, longest ${Math.max(...durations)}s)`,
      description: null,
      data: { count: group.length, total_seconds: total, longest_seconds: Math.max(...durations) },
    });
    group = [];
  };
  events.forEach((event) => {
    const duration = event.kind === "data_gap" ? gapSeconds(event) : null;
    if (duration !== null && duration < thresholdSeconds) group.push(event);
    else { flush(); collapsed.push(event); }
  });
  flush();
  return collapsed;
}

export function cookLogMarkup(events, editable = false, dataGapEventMinSeconds = 120) {
  let userNumber = 0;
  const rows = collapseBriefDataGaps(events, dataGapEventMinSeconds).map((storedEvent) => {
    const event = presentEvent(storedEvent);
    const user = event.source === "user";
    if (user) userNumber += 1;
    const when = timestamp(event.ts);
    const pin = user ? userNumber : escapeHtml(autoIcons[event.kind] || "·");
    const edit = user && editable ? `<button class="ib event-edit" type="button" data-event-id="${event.id}" aria-label="Edit ${escapeHtml(event.title)}">✎</button>` : "";
    const detailClass = event.kind === "setpoint_changed" ? ' class="mut"' : "";
    return `<article class="ev${user ? " user-event" : ""}"><span class="pin${user ? "" : " auto"}" aria-hidden="true">${pin}</span><div class="event-copy"><h3>${escapeHtml(event.title)}</h3>${event.description ? `<p${detailClass}>${escapeHtml(event.description)}</p>` : ""}<div class="mut event-meta">${when.date} · ${when.time} · ${elapsed(event.elapsed_seconds)}${user ? "" : " · auto"}</div></div>${edit}</article>`;
  }).join("");
  return `<section class="board cook-log"><h2 class="hd">Cook Log</h2>${rows || '<p class="mut">Nothing chalked in the log yet.</p>'}</section>`;
}
