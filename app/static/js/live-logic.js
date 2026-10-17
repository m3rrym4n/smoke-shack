export function clampPercent(value, target) {
  const reading = Number(value);
  const goal = Number(target);
  if (!Number.isFinite(reading) || !Number.isFinite(goal) || goal <= 0) return 0;
  return Math.max(0, Math.min(100, (reading / goal) * 100));
}

export const SHOWCASE_MAX_BYTES = 5 * 1024 * 1024;
const SHOWCASE_IMAGE_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);

export function validateShowcaseFile(file) {
  if (!SHOWCASE_IMAGE_TYPES.has(file?.type)) return "Choose a PNG, JPEG, or WebP image.";
  if (!Number.isFinite(file.size) || file.size <= 0) return "This image is empty.";
  if (file.size > SHOWCASE_MAX_BYTES) return "Image must be 5 MB or smaller.";
  return "";
}

export function showcasePlaceholder(imageUrl) {
  return imageUrl ? "image" : "placeholder";
}

export function showcaseLayoutClass(width) {
  return Number(width) <= 600 ? "showcase-mobile" : "showcase-wide";
}

export function clampStackPosition(value, fallback) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? Math.max(0, Math.min(100, parsed)) : fallback;
}

function secondsBetween(start, end) {
  if (!start || !end) return 0;
  return Math.max(0, Math.round((new Date(end) - new Date(start)) / 1000));
}

export function phaseDurations(cook, now = new Date()) {
  const current = now.toISOString();
  const startupEnd = cook.startup_ended_at || (cook.status === "startup" ? current : null);
  const cookEnd = cook.cook_ended_at || (cook.status === "cook" ? current : null);
  const cooldownEnd = cook.cooldown_ended_at || (cook.status === "cooldown" ? current : null);
  const startup = cook.startup_duration_seconds ?? secondsBetween(cook.started_at, startupEnd);
  const cooking = cook.cook_duration_seconds ?? secondsBetween(cook.startup_ended_at, cookEnd);
  const cooldown = cook.cooldown_duration_seconds ?? secondsBetween(cook.cook_ended_at, cooldownEnd);
  return { startup, cook: cooking, cooldown, total: startup + cooking + cooldown };
}

export function phasePercentages(durations) {
  const total = Math.max(1, durations.total);
  return {
    startup: (durations.startup / total) * 100,
    cook: (durations.cook / total) * 100,
    cooldown: (durations.cooldown / total) * 100,
  };
}

export const ORDER_PAD_BANNERS = {
  live: "Cook in progress",
  planned: "Next order, will be used when the grill starts",
  new: "New order for the next cook",
};

export function orderPlannedCooks(cooks) {
  return [...cooks].sort((left, right) => {
    const leftTime = Date.parse(left.created_at || "") || 0;
    const rightTime = Date.parse(right.created_at || "") || 0;
    return leftTime - rightTime || left.id - right.id;
  });
}

export function selectOrderPadMode(activeCook, plannedCooks, closedCook = null) {
  if (closedCook) {
    return { mode: "closed", cook: closedCook, banner: `Editing closed cook #${closedCook.id}: how it turned out` };
  }
  if (activeCook) return { mode: "live", cook: activeCook, banner: ORDER_PAD_BANNERS.live };
  const planned = orderPlannedCooks(plannedCooks);
  if (planned.length) return { mode: "planned", cook: planned[0], banner: ORDER_PAD_BANNERS.planned };
  return { mode: "new", cook: null, banner: ORDER_PAD_BANNERS.new };
}

export function closedCookReadOnlyFields() {
  return ["meat_id", "seasonings", "sauces", "prep_time_minutes", "pellet_id", "rotisserie"];
}

export function eligibleMeat(meat, cooks, cookId = null) {
  const usedElsewhere = new Set(cooks
    .filter((cook) => cook.id !== cookId && cook.meat_id != null)
    .map((cook) => cook.meat_id));
  return meat.filter((item) => !usedElsewhere.has(item.id));
}

export function orderPadSavedMessage(mode) {
  return mode === "new"
    ? "Saved. It will be picked up automatically when the grill starts."
    : "Order saved.";
}

export const PHOTO_MAX_BYTES = 15 * 1024 * 1024;
export const PHOTO_MAX_EDGE = 2000;
const PHOTO_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);

export function validatePhotoFile(file) {
  if (!PHOTO_TYPES.has(file?.type)) return "Choose a JPEG, PNG, or WebP photo.";
  if (!Number.isFinite(file.size) || file.size <= 0) return "This photo is empty.";
  return "";
}

export function downscaleSize(width, height, maxEdge = PHOTO_MAX_EDGE) {
  if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) {
    return { width: 0, height: 0 };
  }
  const scale = Math.min(1, maxEdge / Math.max(width, height));
  return { width: Math.round(width * scale), height: Math.round(height * scale) };
}

export function orderPhotos(photos) {
  return [...photos].sort((left, right) => Number(left.id) - Number(right.id));
}

export function photoErrorMessage(error) {
  const message = typeof error?.message === "string" ? error.message.trim() : "";
  return message || "Could not send this photo. Please try again.";
}
