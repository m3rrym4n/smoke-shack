export const NOTE_SCOPES = ["this_cook", "pellets", "gear"];

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
