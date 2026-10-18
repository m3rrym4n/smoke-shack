const EXPORT_PANES = [
  ["special", ".special-board"],
  ["notes", ".cook-notes"],
  ["results", ".cook-results"],
  ["chart", ".chart-board"],
  ["log", ".cook-log"],
];

function hasVisibleEvent(events) {
  return events.some((event) => !["data_gap", "data_gap_summary"].includes(event.kind));
}

export function exportSectionKeys({ notes = [], resultsText = null, photos = [], samples = [], events = [] } = {}) {
  return [
    "special",
    ...(notes.length ? ["notes"] : []),
    ...(String(resultsText || "").trim() || photos.length ? ["results"] : []),
    ...(samples.length ? ["chart"] : []),
    ...(hasVisibleEvent(events) ? ["log"] : []),
  ];
}

function slug(value) {
  return String(value || "cook")
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "") || "cook";
}

export function buildExportFilename(cook, today = new Date()) {
  const sourceDate = cook?.started_at || cook?.created_at;
  const date = /^\d{4}-\d{2}-\d{2}/.exec(String(sourceDate || ""))?.[0]
    || today.toISOString().slice(0, 10);
  return `smoke-stack-${date}-${slug(cook?.meat?.type)}.png`;
}

export function exportPaneSelectors(keys) {
  const included = new Set(keys);
  return EXPORT_PANES.filter(([key]) => included.has(key)).map(([, selector]) => selector);
}
