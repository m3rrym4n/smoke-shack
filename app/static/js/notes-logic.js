import { cookTag, isLiveCook, orderCookLogRows } from "./cooks-logic.js";

export const NOTE_SCOPES = ["this_cook", "pellets", "gear"];

export function orderNoteCookOptions(cooks) {
  return orderCookLogRows(cooks);
}

export function cookOptionLabel(cook, locale = undefined) {
  const dateValue = cook.started_at || cook.created_at;
  const date = dateValue
    ? new Intl.DateTimeFormat(locale, { month: "short", day: "numeric" }).format(new Date(dateValue))
    : "date unknown";
  const details = [`Cook #${cook.id}`, date];
  if (cook.meat?.type) details.push(cook.meat.type);
  const tag = cookTag(cook);
  return `${details.join(" - ")}${tag ? ` (${tag})` : ""}`;
}

export function defaultNoteCookId(cooks) {
  const ordered = orderNoteCookOptions(cooks);
  return ordered.find(isLiveCook)?.id
    ?? ordered.find((cook) => cook.state === "planned")?.id
    ?? null;
}

export function thisCookTarget(cooks) {
  const ordered = orderNoteCookOptions(cooks);
  return ordered.find(isLiveCook)
    ?? ordered.find((cook) => cook.state !== "planned")
    ?? null;
}

export function thisCookChipLabel(cook) {
  if (!cook) return "This cook";
  return `Cook #${cook.id}${isLiveCook(cook) ? ", in progress" : ""}`;
}

export function validateNote(values) {
  const errors = {};
  if (!String(values.title || "").trim()) errors.title = "Give the note a title.";
  if (!String(values.body || "").trim()) errors.body = "Write something on the note.";
  if (!NOTE_SCOPES.includes(values.scope)) errors.scope = "Choose a note scope.";
  const cookId = Number(values.cook_id);
  if (values.scope === "this_cook" && (!Number.isInteger(cookId) || cookId < 1)) {
    errors.cook_id = "Choose a cook for this note.";
  }
  return errors;
}

export function notePayload(values) {
  return {
    title: String(values.title || "").trim(),
    body: String(values.body || "").trim(),
    scope: values.scope,
    cook_id: values.scope === "this_cook" ? Number(values.cook_id) : null,
  };
}
