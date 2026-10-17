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

const autoIcons = { fire_lit: "♨", setpoint_changed: "↗", phase_changed: "→", data_gap: "!", probe_connected: "+", probe_disconnected: "−", warning: "!" };

export function cookLogMarkup(events, editable = false) {
  let userNumber = 0;
  const rows = events.map((event) => {
    const user = event.source === "user";
    if (user) userNumber += 1;
    const when = timestamp(event.ts);
    const pin = user ? userNumber : escapeHtml(autoIcons[event.kind] || "·");
    const edit = user && editable ? `<button class="ib event-edit" type="button" data-event-id="${event.id}" aria-label="Edit ${escapeHtml(event.title)}">✎</button>` : "";
    return `<article class="ev${user ? " user-event" : ""}"><span class="pin${user ? "" : " auto"}" aria-hidden="true">${pin}</span><div class="event-copy"><h3>${escapeHtml(event.title)}</h3>${event.description ? `<p>${escapeHtml(event.description)}</p>` : ""}<div class="mut event-meta">${when.date} · ${when.time} · ${elapsed(event.elapsed_seconds)}${user ? "" : " · auto"}</div></div>${edit}</article>`;
  }).join("");
  return `<section class="board cook-log"><h2 class="hd">Cook Log</h2>${rows || '<p class="mut">Nothing chalked in the log yet.</p>'}</section>`;
}
