const text = (value) => String(value ?? "").trim();

export function spiceBrand(spice) {
  return text(spice?.brand || spice?.category);
}

export function spiceLabel(spice) {
  return [spiceBrand(spice), text(spice?.name)].filter(Boolean).join(" ");
}

export function addSpice(selectedIds, spiceId) {
  const id = Number(spiceId);
  return Number.isInteger(id) && !selectedIds.includes(id) ? [...selectedIds, id] : [...selectedIds];
}

export function removeSpice(selectedIds, spiceId) {
  const id = Number(spiceId);
  return selectedIds.filter((selectedId) => selectedId !== id);
}

export function filterSpiceChoices(spices, query) {
  const needle = text(query).toLocaleLowerCase();
  if (!needle) return [...spices];
  return spices.filter((spice) => [spiceBrand(spice), spice.name, spice.size_oz]
    .some((value) => text(value).toLocaleLowerCase().includes(needle)));
}

export function withSpiceIds(fields, selectedIds) {
  return { ...fields, spice_ids: [...new Set(selectedIds.map(Number).filter(Number.isInteger))] };
}

export function seasoningText(cook) {
  return [
    ...(cook?.spices || []).map(spiceLabel).filter(Boolean),
    text(cook?.seasonings),
  ].filter(Boolean).join(" · ");
}
