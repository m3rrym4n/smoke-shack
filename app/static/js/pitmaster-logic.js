const present = (value) => value !== undefined && value !== null && String(value).trim() !== "";

export function mergeMeatTypeOptions(stats = [], meat = [], selected = "") {
  const byName = new Map();

  stats.forEach((item) => {
    const name = String(item.meat_type ?? "").trim();
    if (!name) return;
    const key = name.toLocaleLowerCase();
    const existing = byName.get(key);
    const count = Number(item.count) || 0;
    if (existing) {
      existing.count += count;
    } else {
      byName.set(key, { value: name, count });
    }
  });

  meat.forEach((item) => {
    const name = String(item.type ?? "").trim();
    if (name && !byName.has(name.toLocaleLowerCase())) {
      byName.set(name.toLocaleLowerCase(), { value: name, count: 0 });
    }
  });

  const selectedName = String(selected ?? "").trim();
  if (selectedName) {
    const key = selectedName.toLocaleLowerCase();
    const existing = byName.get(key);
    if (existing) {
      existing.value = selectedName;
    } else {
      byName.set(key, { value: selectedName, count: 0 });
    }
  }

  return [...byName.values()]
    .sort((left, right) => left.value.localeCompare(right.value, undefined, { sensitivity: "base" }))
    .map((item) => ({
      value: item.value,
      label: `${item.value} (${item.count ? item.count : "no cooks yet"})`,
      count: item.count,
    }));
}

export function buildMeatOptions(groups = [], stats = [], meat = [], selected = {}) {
  const groupIds = new Set(groups.map((group) => String(group.id)));
  const groupedCounts = new Map(groups.map((group) => [String(group.id), 0]));
  stats.forEach((item) => {
    const groupId = item.group_id === null || item.group_id === undefined ? "" : String(item.group_id);
    if (groupedCounts.has(groupId)) {
      groupedCounts.set(groupId, groupedCounts.get(groupId) + (Number(item.count) || 0));
    }
  });
  const groupOptions = groups
    .map((group) => ({
      kind: "group", value: String(group.id), label: `${group.name} (${groupedCounts.get(String(group.id)) || 0})`,
      name: group.name, count: groupedCounts.get(String(group.id)) || 0,
    }))
    .sort((left, right) => left.name.localeCompare(right.name, undefined, { sensitivity: "base" }));

  const ungroupedStats = stats.filter((item) => !groupIds.has(String(item.group_id ?? "")));
  const groupedTypes = new Set(groups.flatMap((group) => group.types || []).map((name) => String(name).trim().toLocaleLowerCase()));
  const ungroupedMeat = meat.filter((item) => !groupedTypes.has(String(item.type ?? "").trim().toLocaleLowerCase()));
  const selectedType = String(selected.meat || "").trim();
  const selectedUngroupedType = groupedTypes.has(selectedType.toLocaleLowerCase()) ? "" : selectedType;
  const typeOptions = mergeMeatTypeOptions(ungroupedStats, ungroupedMeat, selectedUngroupedType)
    .map((item) => ({ ...item, kind: "type", name: item.value }));
  return [...groupOptions, ...typeOptions];
}

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
    meatGroup: params.get("meat_group") || "",
    poundsMin: params.get("pounds_min") || "",
    poundsMax: params.get("pounds_max") || "",
    setpoint: params.get("setpoint") || "",
    tolerance: params.get("tolerance") || "10",
    rotisserie: params.get("rotisserie") === "true" ? "true" : "false",
    pelletId: params.get("pellet_id") || "",
  };
}

export function filtersToHash(filters) {
  const params = new URLSearchParams();
  const fields = [
    ["meat", filters.meatGroup ? "" : filters.meat], ["meat_group", filters.meatGroup],
    ["pounds_min", filters.poundsMin],
    ["pounds_max", filters.poundsMax], ["setpoint", filters.setpoint],
    ["tolerance", filters.setpoint ? filters.tolerance : ""],
    ["rotisserie", filters.rotisserie === "true" ? "true" : "false"],
    ["pellet_id", filters.pelletId],
  ];
  fields.forEach(([key, value]) => { if (present(value)) params.set(key, value); });
  const query = params.toString();
  return `#pitmaster${query ? `?${query}` : ""}`;
}

export function statsQuery(filters) {
  const params = new URLSearchParams();
  if (present(filters.meatGroup)) params.set("meat_group", filters.meatGroup);
  else if (present(filters.meat)) params.set("meat_type", filters.meat);
  if (present(filters.poundsMin)) params.set("pounds_min", filters.poundsMin);
  if (present(filters.poundsMax)) params.set("pounds_max", filters.poundsMax);
  if (present(filters.setpoint)) {
    params.set("setpoint", filters.setpoint);
    params.set("setpoint_tolerance", present(filters.tolerance) ? filters.tolerance : "10");
  }
  params.set("rotisserie", filters.rotisserie === "true" ? "true" : "false");
  if (present(filters.pelletId)) params.set("pellet_id", filters.pelletId);
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
  const meatSubject = filters.meatGroupName || filters.meat;
  if (!count && present(meatSubject)) return `No cooks logged yet for ${meatSubject}.`;
  if (!count) return "No cooks match that order yet. Give the pitmaster something to work with.";
  const subject = [weightPhrase(filters), meatSubject].filter(Boolean).join(" ") || "matching cook";
  const details = [];
  if (present(filters.setpoint)) details.push(`at ${filters.setpoint}°F`);
  if (filters.rotisserie === "true") details.push("on the rotisserie");
  if (filters.rotisserie === "false") details.push("without the rotisserie");
  const cookTime = stats.cook_seconds || {};
  const showRange = count > 1 && present(cookTime.min) && present(cookTime.max)
    && Number(cookTime.min) !== Number(cookTime.max);
  const range = showRange
    ? ` (range ${formatDurationWords(cookTime.min)} to ${formatDurationWords(cookTime.max)})`
    : "";
  return `Based on ${count} ${count === 1 ? "cook" : "cooks"}: a ${subject}${details.length ? ` ${details.join(" ")}` : ""} averages ${formatDurationWords(cookTime.avg)}${range}.`;
}

export function buildLowConfidenceNote(stats) {
  const count = Number(stats?.count) || 0;
  if (count < 1 || count > 2) return "";
  return `Only ${count} matching ${count === 1 ? "cook" : "cooks"} so far. Treat this as a rough guide.`;
}

export function cookTimePerPound(cooks = []) {
  const values = cooks
    .map((cook) => Number(cook.cook_seconds) / Number(cook.pounds))
    .filter((value) => Number.isFinite(value) && value >= 0);
  if (!values.length) return null;
  return Math.round(values.reduce((total, value) => total + value, 0) / values.length);
}
