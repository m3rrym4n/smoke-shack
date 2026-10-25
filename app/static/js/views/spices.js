import { getSpices } from "../api.js";
import { bindItemPhoto, itemPhotoMarkup } from "../components/item-photo.js";
import { formatMoney } from "../components/ui.js";

const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (character) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
})[character]);

function spiceCard(item) {
  const details = [
    item.size_oz ? `${item.size_oz} oz` : null,
    item.price != null ? formatMoney(item.price) : null,
  ].filter(Boolean).join(" · ");
  return `<article class="spice-card" data-id="${item.id}">
    <div class="spice-title"><strong>${escapeHtml(item.name)}</strong><span>${escapeHtml(item.brand)}</span></div>
    ${details ? `<p class="mut">${escapeHtml(details)}</p>` : ""}
    ${item.notes ? `<p>${escapeHtml(item.notes)}</p>` : ""}
    ${itemPhotoMarkup(item)}
  </article>`;
}

export function mountSpicesView(container) {
  let disposed = false;
  container.innerHTML = `<section class="board spice-board"><h1 class="hd">The Spice Rack</h1><p class="mut spice-message" role="status">Checking the rack…</p><div class="spice-list"></div></section>`;
  const list = container.querySelector(".spice-list");
  const message = container.querySelector(".spice-message");
  getSpices().then((items) => {
    if (disposed) return;
    list.innerHTML = items.map(spiceCard).join("");
    message.textContent = items.length ? "" : "The spice rack is bare.";
    list.querySelectorAll(".spice-card").forEach((card) => {
      bindItemPhoto(card.querySelector("[data-photo]"), "spices", Number(card.dataset.id));
    });
  }).catch((error) => {
    if (disposed) return;
    console.error("Could not load spices", error);
    message.textContent = "Could not load the spice rack.";
  });
  return () => { disposed = true; };
}
