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
    const heading = [grill.maker, grill.model].filter(Boolean).map(escapeHtml).join(" · ") || escapeHtml(grill.name);
    const imageControl = (kind, label) => {
      const url = grill[`${kind}_url`];
      const preview = url ? `<img src="${escapeHtml(url)}" alt="Current ${label.toLowerCase()}">` : "";
      return `<div class="grill-image-field" data-image-kind="${kind}"><span>${label}</span><div class="grill-image-preview">${preview}</div><label class="cc">Choose file<input type="file" accept="${kind === "logo" ? "image/png,image/jpeg,image/webp,.svg,image/svg+xml" : "image/png,image/jpeg,image/webp"}"></label><button class="cc upload-grill-image" type="button" disabled>Save</button><button class="cc remove-grill-image" type="button" ${url ? "" : "disabled"}>Remove</button><span class="grill-image-message" role="status"></span></div>`;
    };
    return `<article class="grill-card" data-grill-id="${escapeHtml(grill.id)}">
      <div class="grill-details">
        <h3>${heading}</h3>
        <dl>
          <div><dt>Device status</dt><dd>${deviceStatusLabel(grill.device_status)}</dd></div>
          <div><dt>Connection status</dt><dd>${connectionStatusLabel(grill.connection_status)}</dd></div>
        </dl>
      </div>
      <div class="grill-images" data-equipment-id="${grill.equipment_id ?? ""}">${imageControl("photo", "Photo")}${imageControl("logo", "Logo")}</div>
      <button class="pbtn grill-control" type="button" data-action="${connected ? "disconnect" : "connect"}">${connected ? "Disconnect" : "Connect"}</button>
      <p class="grill-message" role="status">${escapeHtml(messages[grill.id] || "")}</p>
    </article>`;
  }).join("");
}
