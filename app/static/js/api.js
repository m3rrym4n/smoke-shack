export function withBase(path) {
  const relative = String(path).replace(/^\/+/, "");
  if (typeof document === "undefined") return `/${relative}`;
  return new URL(relative, document.baseURI).href;
}

async function requestJson(path, options = {}) {
  const response = await fetch(withBase(path), options);
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
    const error = new Error(detail);
    error.status = response.status;
    throw error;
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

export function getGrills() {
  return getJson("/api/grills");
}

export function connectGrill(grillId) {
  return sendJson("POST", `/api/grills/${encodeURIComponent(grillId)}/connect`);
}

export function disconnectGrill(grillId) {
  return sendJson("POST", `/api/grills/${encodeURIComponent(grillId)}/disconnect`);
}

export function uploadEquipmentImage(equipmentId, kind, file) {
  const body = new FormData();
  body.append("file", file);
  return requestJson(`/api/equipment/${equipmentId}/${kind}`, { method: "POST", body });
}

export function deleteEquipmentImage(equipmentId, kind) {
  return requestJson(`/api/equipment/${equipmentId}/${kind}`, { method: "DELETE" });
}

export function restoreBackup(file) {
  const body = new FormData();
  body.append("file", file);
  return requestJson("/api/restore", { method: "POST", body });
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

export function getPlannedCooks(limit = 100, offset = 0) {
  const params = new URLSearchParams({ limit, offset, state: "planned" });
  return getJson(`/api/cooks?${params}`);
}

export async function getActiveCook() {
  const status = await getStatus();
  return status.active_cook ? getCook(status.active_cook.id) : null;
}

export async function getCookLogCooks(closedLimit = 50) {
  const [plans, active, closed] = await Promise.all([
    getPlannedCooks(), getActiveCook(), getRecentCooks(closedLimit),
  ]);
  return [...plans, ...(active ? [active] : []), ...closed];
}

export function createPlannedCook(body) {
  return sendJson("POST", "/api/cooks", { ...body, state: "planned" });
}

export function deleteCook(cookId) {
  return sendJson("DELETE", `/api/cooks/${cookId}`);
}

export function getCookPhotos(cookId) {
  return getJson(`/api/cooks/${cookId}/photos`);
}

export function uploadCookPhoto(cookId, file) {
  const body = new FormData();
  body.append("file", file);
  return requestJson(`/api/cooks/${cookId}/photos`, { method: "POST", body });
}

export function deleteCookPhoto(photoId) {
  return sendJson("DELETE", `/api/photos/${photoId}`);
}

export function getMeat(cooked = null) {
  if (cooked === null) return getJson("/api/meat");
  return getJson(`/api/meat?cooked=${cooked}`);
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

export function getPellets(upc = "", includeEmpty = false) {
  const params = new URLSearchParams();
  if (upc) params.set("upc", upc);
  if (includeEmpty) params.set("include_empty", "true");
  const query = params.toString();
  return getJson(`/api/pellets${query ? `?${query}` : ""}`);
}

export function getFuel(type = "", upc = "", includeEmpty = false) {
  const params = new URLSearchParams();
  if (type) params.set("type", type);
  if (upc) params.set("upc", upc);
  if (includeEmpty) params.set("include_empty", "true");
  const query = params.toString();
  return getJson(`/api/fuel${query ? `?${query}` : ""}`);
}

export function getCookStats(params = new URLSearchParams()) {
  const query = params.toString();
  return getJson(`/api/stats/cooks${query ? `?${query}` : ""}`);
}

export function getCookStatsMeatTypes() {
  return getJson("/api/stats/meat-types");
}

export function getMeatGroups() {
  return getJson("/api/meat-groups");
}

export function createMeatGroup(name) {
  return sendJson("POST", "/api/meat-groups", { name });
}

export function renameMeatGroup(groupId, name) {
  return sendJson("PATCH", `/api/meat-groups/${groupId}`, { name });
}

export function deleteMeatGroup(groupId) {
  return sendJson("DELETE", `/api/meat-groups/${groupId}`);
}

export function replaceMeatGroupTypes(groupId, types) {
  return sendJson("PUT", `/api/meat-groups/${groupId}/types`, { types });
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

export function createFuel(body) {
  return sendJson("POST", "/api/fuel", body);
}

export function updateFuel(fuelId, body) {
  return sendJson("PATCH", `/api/fuel/${fuelId}`, body);
}

export function deleteFuel(fuelId) {
  return sendJson("DELETE", `/api/fuel/${fuelId}`);
}

export function listSpices() {
  return getJson("/api/spices");
}

export function createSpice(body) {
  return sendJson("POST", "/api/spices", body);
}

export function updateSpice(spiceId, body) {
  return sendJson("PATCH", `/api/spices/${spiceId}`, body);
}

export function deleteSpice(spiceId) {
  return sendJson("DELETE", `/api/spices/${spiceId}`);
}

export function uploadPhoto(kind, id, blob) {
  const body = new FormData();
  body.append("file", blob, "photo.jpg");
  return requestJson(`/api/${kind}/${id}/photo`, { method: "POST", body });
}

export function deletePhoto(kind, id) {
  return requestJson(`/api/${kind}/${id}/photo`, { method: "DELETE" });
}

export function getNotes(scope = "all", cookId = null) {
  const params = new URLSearchParams();
  if (scope !== "all") params.set("scope", scope);
  if (cookId !== null) params.set("cook_id", cookId);
  const query = params.toString();
  return getJson(`/api/notes${query ? `?${query}` : ""}`);
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
