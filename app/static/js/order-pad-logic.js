export function availableMeat(meat, cooks, cookId) {
  const used = new Set(cooks.filter((cook) => cook.id !== cookId && cook.meat_id != null).map((cook) => cook.meat_id));
  return meat.filter((item) => !used.has(item.id));
}

export function meatOptionLabel(item) {
  const [year, month, day] = String(item.purchased_on).split("-").map(Number);
  const purchased = year && month && day
    ? new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", timeZone: "UTC" }).format(new Date(Date.UTC(year, month - 1, day)))
    : "No date";
  return `${item.type}, ${item.pounds} lb, ${item.store || "No store"}, ${purchased}`;
}

export function pelletOptionLabel(item) {
  return `${item.vendor}, ${item.product_name}`;
}

export function validatePelletsUsed(value) {
  if (value === "") return "";
  return Number.isFinite(Number(value)) && Number(value) >= 0 ? "" : "Pellets used must be zero or greater.";
}
