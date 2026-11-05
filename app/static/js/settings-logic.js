const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (character) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
})[character]);

export function deviceStatusLabel(status) {
  return status === "available" ? "Available" : "Not available";
}

export function connectionStatusLabel(status) {
  return status === "connected" ? "Connected" : "Disconnected";
}

export function renderGrills(grills, messages = {}) {
  if (!grills.length) return '<p class="settings-empty">No grills found.</p>';
  return grills.map((grill) => {
    const connected = grill.connection_status === "connected";
    const details = [grill.maker, grill.model].filter(Boolean).map(escapeHtml).join(" · ") || "Maker and model unknown";
    return `<article class="grill-card" data-grill-id="${escapeHtml(grill.id)}">
      <div class="grill-details">
        <h3>${escapeHtml(grill.name)}</h3>
        <p class="mut">${details}</p>
        <dl>
          <div><dt>Device status</dt><dd>${deviceStatusLabel(grill.device_status)}</dd></div>
          <div><dt>Connection status</dt><dd>${connectionStatusLabel(grill.connection_status)}</dd></div>
        </dl>
      </div>
      <button class="pbtn grill-control" type="button" data-action="${connected ? "disconnect" : "connect"}">${connected ? "Disconnect" : "Connect"}</button>
      <p class="grill-message" role="status">${escapeHtml(messages[grill.id] || "")}</p>
    </article>`;
  }).join("");
}
