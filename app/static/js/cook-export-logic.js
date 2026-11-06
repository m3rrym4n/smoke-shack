function clean(value) {
  return String(value ?? "").trim();
}

export function cookStatusBadge(cook) {
  if (cook?.status === "startup") return { key: "startup", label: "STARTUP" };
  if (cook?.status === "cook") return { key: "cooking", label: "COOKING" };
  return { key: "complete", label: "COMPLETE" };
}

export function cookStatusBadgeMarkup(cook) {
  const badge = cookStatusBadge(cook);
  return `<span class="cook-status-badge ${badge.key}">${badge.label}</span>`;
}

export function pelletLine(pellet) {
  const name = [clean(pellet?.vendor), clean(pellet?.product_name)].filter(Boolean).join(" ");
  const type = clean(pellet?.type || "pellets");
  return name ? `${name} (${type[0].toUpperCase() + type.slice(1)})` : "";
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

export const NO_PHOTO = "none";

export function exportPhotoSelection(photos, remembered) {
  const available = Array.isArray(photos) ? photos : [];
  const rememberedValue = remembered == null ? "" : String(remembered);
  if (rememberedValue === NO_PHOTO) return NO_PHOTO;
  if (available.some((photo) => String(photo.id) === rememberedValue)) {
    return rememberedValue;
  }
  if (!available.length) return NO_PHOTO;
  return String(available.reduce((latest, photo) => (
    Number(photo.id) > Number(latest.id) ? photo : latest
  )).id);
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
