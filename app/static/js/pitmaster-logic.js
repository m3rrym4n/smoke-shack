const present = (value) => value !== undefined && value !== null && String(value).trim() !== "";

export function formatDuration(seconds) {
  if (seconds === null || seconds === undefined || seconds === "") return "—";
  const value = Number(seconds);
  if (!Number.isFinite(value) || value < 0) return "—";
  const totalMinutes = Math.round(value / 60);
  return `${Math.floor(totalMinutes / 60)}:${String(totalMinutes % 60).padStart(2, "0")}`;
}

export function formatDurationWords(seconds) {
  if (seconds === null || seconds === undefined || seconds === "") return "an unknown time";
  const value = Number(seconds);
  if (!Number.isFinite(value) || value < 0) return "an unknown time";
  const totalMinutes = Math.round(value / 60);
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  if (!hours) return `${minutes}m`;
  return minutes ? `${hours}h ${minutes}m` : `${hours}h`;
}

export function filtersFromHash(hash) {
  const query = String(hash).split("?", 2)[1] || "";
  const params = new URLSearchParams(query);
  return {
    meat: params.get("meat") || "",
    poundsMin: params.get("pounds_min") || "",
    poundsMax: params.get("pounds_max") || "",
    setpoint: params.get("setpoint") || "",
    tolerance: params.get("tolerance") || "10",
    rotisserie: params.get("rotisserie") || "",
    pelletVendor: params.get("pellet_vendor") || "",
    pelletProduct: params.get("pellet_product") || "",
    store: params.get("store") || "",
  };
}

export function filtersToHash(filters) {
  const params = new URLSearchParams();
  const fields = [
    ["meat", filters.meat], ["pounds_min", filters.poundsMin],
    ["pounds_max", filters.poundsMax], ["setpoint", filters.setpoint],
    ["tolerance", filters.setpoint ? filters.tolerance : ""],
    ["rotisserie", filters.rotisserie], ["pellet_vendor", filters.pelletVendor],
    ["pellet_product", filters.pelletProduct], ["store", filters.store],
  ];
  fields.forEach(([key, value]) => { if (present(value)) params.set(key, value); });
  const query = params.toString();
  return `#pitmaster${query ? `?${query}` : ""}`;
}

export function statsQuery(filters) {
  const params = new URLSearchParams();
  if (present(filters.meat)) params.set("meat_type", filters.meat);
  if (present(filters.poundsMin)) params.set("pounds_min", filters.poundsMin);
  if (present(filters.poundsMax)) params.set("pounds_max", filters.poundsMax);
  if (present(filters.setpoint)) {
    params.set("setpoint", filters.setpoint);
    params.set("setpoint_tolerance", present(filters.tolerance) ? filters.tolerance : "10");
  }
  if (present(filters.rotisserie)) params.set("rotisserie", filters.rotisserie);
  return params;
}

function weightPhrase(filters) {
  if (present(filters.poundsMin) && filters.poundsMin === filters.poundsMax) return `${filters.poundsMin} lb`;
  if (present(filters.poundsMin) && present(filters.poundsMax)) return `${filters.poundsMin}–${filters.poundsMax} lb`;
  if (present(filters.poundsMin)) return `${filters.poundsMin}+ lb`;
  if (present(filters.poundsMax)) return `up to ${filters.poundsMax} lb`;
  return "";
}

export function buildAnswerSentence(filters, stats) {
  const count = Number(stats?.count) || 0;
  if (!count) return "No cooks match that order yet. Give the pitmaster something to work with.";
  const subject = [weightPhrase(filters), filters.meat].filter(Boolean).join(" ") || "matching cook";
  const details = [];
  if (present(filters.setpoint)) details.push(`at ${filters.setpoint}°F`);
  if (filters.rotisserie === "true") details.push("on the rotisserie");
  if (filters.rotisserie === "false") details.push("without the rotisserie");
  if (present(filters.pelletVendor) || present(filters.pelletProduct)) {
    details.push(`with ${[filters.pelletVendor, filters.pelletProduct].filter(Boolean).join(" ")} pellets`);
  }
  if (present(filters.store)) details.push(`from ${filters.store}`);
  return `Based on ${count} ${count === 1 ? "cook" : "cooks"}: a ${subject}${details.length ? ` ${details.join(" ")}` : ""} averages ${formatDurationWords(stats.cook_seconds?.avg)}.`;
}

export function cookTimePerPound(cooks = []) {
  const values = cooks
    .map((cook) => Number(cook.cook_seconds) / Number(cook.pounds))
    .filter((value) => Number.isFinite(value) && value >= 0);
  if (!values.length) return null;
  return Math.round(values.reduce((total, value) => total + value, 0) / values.length);
}
