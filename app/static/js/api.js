async function requestJson(path, options = {}) {
  const response = await fetch(path, options);
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const payload = await response.json();
      detail = payload.detail ?? detail;
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
