function clean(value) {
  return String(value ?? "").trim();
}

export function pelletLine(pellet) {
  const name = [clean(pellet?.vendor), clean(pellet?.product_name)].filter(Boolean).join(" ");
  return name ? `${name} Pellets` : "";
}

export function weightText(pounds) {
  const value = Number(pounds);
  return Number.isFinite(value) && value > 0 ? `${value} lb` : "";
}

export function shownPapers(notes, resultsText) {
  return {
    notes: Array.isArray(notes) && notes.some((note) => clean(note?.body)),
    results: Boolean(clean(resultsText)),
  };
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
