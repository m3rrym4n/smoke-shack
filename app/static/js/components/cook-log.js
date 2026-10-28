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

const autoIcons = { fire_lit: "♨", setpoint_changed: "↗", phase_changed: "→", probe_connected: "+", probe_disconnected: "−", warning: "!" };

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

export function cookLogMarkup(events, editable = false) {
  let userNumber = 0;
  const rows = events.filter((event) => !["data_gap", "data_gap_summary"].includes(event.kind)).map((storedEvent) => {
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
