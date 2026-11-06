import { eligibleMeat } from "./live-logic.js";

export const availableMeat = eligibleMeat;

export function meatOptionLabel(item) {
  const [year, month, day] = String(item.purchased_on).split("-").map(Number);
  const purchased = year && month && day
    ? new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", timeZone: "UTC" }).format(new Date(Date.UTC(year, month - 1, day)))
    : "No date";
  return `${item.type}, ${item.pounds} lb, ${item.store || "No store"}, ${purchased}`;
}

export function pelletOptionLabel(item) {
  const type = item.type ? item.type[0].toUpperCase() + item.type.slice(1) : "Pellets";
  return `${item.vendor}, ${item.product_name} (${type})`;
}

export function validatePelletsUsed(value) {
  if (value === "") return "";
  return Number.isFinite(Number(value)) && Number(value) >= 0 ? "" : "Fuel used must be zero or greater.";
}
