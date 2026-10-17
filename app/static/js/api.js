async function requestJson(path, options = {}) {
  const response = await fetch(path, options);
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const payload = await response.json();
      if (Array.isArray(payload.detail)) {
        detail = payload.detail.map((item) => item.msg?.replace(/^Value error, /, "") || "Check this field.").join(" ");
      } else {
        detail = payload.detail ?? detail;
      }
    } catch {
      // The response was not JSON; retain the HTTP status description.
    }
    throw new Error(detail);
  }
  if (response.status === 204) return null;
  return response.json();
}

export function getJson(path) {
  return requestJson(path);
}

export function sendJson(method, path, body) {
  return requestJson(path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

export function getStatus() {
  return getJson("/status");
}

export function getCook(cookId) {
  return getJson(`/api/cooks/${cookId}`);
}

export function getCookSamples(cookId) {
  return getJson(`/api/cooks/${cookId}/samples`);
}

export function getCookEvents(cookId) {
  return getJson(`/api/cooks/${cookId}/events`);
}

export function getRecentCooks(limit = 1, offset = 0) {
  const params = new URLSearchParams({ limit, offset, state: "closed" });
  return getJson(`/api/cooks?${params}`);
}

export function getMeat() {
  return getJson("/api/meat");
}

export function getCooksForMeat(meatId) {
  const params = new URLSearchParams({ meat_id: meatId, limit: 1 });
  return getJson(`/api/cooks?${params}`);
}

export function createMeat(body) {
  return sendJson("POST", "/api/meat", body);
}

export function updateMeat(meatId, body) {
  return sendJson("PATCH", `/api/meat/${meatId}`, body);
}

export function deleteMeat(meatId) {
  return sendJson("DELETE", `/api/meat/${meatId}`);
}

export function getPellets() {
  return getJson("/api/pellets");
}

export function getCookStats(params = new URLSearchParams()) {
  const query = params.toString();
  return getJson(`/api/stats/cooks${query ? `?${query}` : ""}`);
}

export function getCookStatsMeatTypes() {
  return getJson("/api/stats/meat-types");
}

export function getCooksForPellet(pelletId) {
  const params = new URLSearchParams({ pellet_id: pelletId, limit: 1 });
  return getJson(`/api/cooks?${params}`);
}

export function createPellet(body) {
  return sendJson("POST", "/api/pellets", body);
}

export function updatePellet(pelletId, body) {
  return sendJson("PATCH", `/api/pellets/${pelletId}`, body);
}

export function deletePellet(pelletId) {
  return sendJson("DELETE", `/api/pellets/${pelletId}`);
}

export function getNotes(scope = "all") {
  const query = scope === "all" ? "" : `?${new URLSearchParams({ scope })}`;
  return getJson(`/api/notes${query}`);
}

export function createNote(body) {
  return sendJson("POST", "/api/notes", body);
}

export function updateNote(noteId, body) {
  return sendJson("PATCH", `/api/notes/${noteId}`, body);
}

export function deleteNote(noteId) {
  return sendJson("DELETE", `/api/notes/${noteId}`);
}

export function createCookEvent(cookId, body) {
  return sendJson("POST", `/api/cooks/${cookId}/events`, body);
}

export function updateCookEvent(eventId, body) {
  return sendJson("PATCH", `/api/events/${eventId}`, body);
}

export function deleteCookEvent(eventId) {
  return sendJson("DELETE", `/api/events/${eventId}`);
}

export function updateCook(cookId, body) {
  return sendJson("PATCH", `/api/cooks/${cookId}`, body);
}
