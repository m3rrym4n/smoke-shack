import { createSpice, deleteSpice, listSpices, updateSpice } from "../api.js";
import { bindItemPhoto, itemPhotoMarkup } from "../components/item-photo.js";
import { confirmDelete, renderApiError } from "../components/ui.js";
import {
  filterSpices, formatSpicePrice, formatSpiceSize, groupSpices, isLockedSpice,
  validateSpice,
} from "../spices-logic.js";

const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (character) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
})[character]);

function fields(item = {}, brands = []) {
  return `<div class="spice-form-grid">
    <label class="fl"><span class="lb">Brand</span><input class="ci" name="brand" list="spice-brands" required value="${escapeHtml(item.brand)}" placeholder="Meat Church"></label>
    <label class="fl"><span class="lb">Rub name</span><input class="ci" name="name" required value="${escapeHtml(item.name)}" placeholder="Holy Cow"></label>
    <label class="fl"><span class="lb">Price</span><input class="ci" name="price" type="number" min="0" step="0.01" inputmode="decimal" value="${escapeHtml(item.price)}"></label>
    <label class="fl"><span class="lb">Size in oz</span><input class="ci" name="size_oz" type="number" min="0.1" step="0.1" inputmode="decimal" value="${escapeHtml(item.size_oz)}"></label>
    <label class="fl spice-notes"><span class="lb">Notes</span><textarea class="ci" name="notes" rows="3" placeholder="Flavor notes or homemade blend ingredients">${escapeHtml(item.notes)}</textarea></label>
  </div><datalist id="spice-brands">${brands.map((brand) => `<option value="${escapeHtml(brand)}"></option>`).join("")}</datalist>`;
}

function formValues(form) {
  const data = new FormData(form);
  return {
    brand: String(data.get("brand") || "").trim(),
    name: String(data.get("name") || "").trim(),
    price: String(data.get("price") || ""),
    size_oz: String(data.get("size_oz") || ""),
    notes: String(data.get("notes") || "").trim(),
  };
}

function payload(values) {
  return {
    ...values,
    price: values.price === "" ? null : Number(values.price),
    size_oz: values.size_oz === "" ? null : Number(values.size_oz),
    notes: values.notes || null,
  };
}

function showValidation(form, errors) {
  const first = Object.keys(errors)[0];
  if (!first) return false;
  const message = form.querySelector(".form-message");
  message.textContent = Object.values(errors).join(" ");
  message.classList.add("error");
  form.elements[first]?.focus();
  return true;
}

function spiceCard(item, brands) {
  const details = [formatSpicePrice(item.price), formatSpiceSize(item.size_oz)].filter(Boolean);
  const locked = isLockedSpice(item);
  const custom = item.is_custom ? '<span class="custom-spice-badge">Custom</span>' : "";
  const controls = locked ? "" : '<div class="row-actions"><button class="cc edit-spice" type="button">Edit</button><button class="cc delete-spice" type="button">Delete</button></div><div class="delete-confirm" hidden></div>';
  return `<article class="spice-card${item.is_custom ? " custom-spice" : ""}" data-id="${item.id}">
    <div class="spice-summary">
      <div class="spice-title"><strong>${escapeHtml(item.name)}</strong>${custom}</div>
      ${details.length ? `<p class="spice-details">${details.map(escapeHtml).join(" · ")}</p>` : ""}
      ${item.notes ? `<p class="spice-notes-text">${escapeHtml(item.notes)}</p>` : ""}
      ${itemPhotoMarkup(item)}${controls}
    </div>
    ${locked ? "" : `<form class="stp edit-form" hidden>${fields(item, brands)}<div class="form-actions"><button class="pbtn save-spice" type="submit">Save rub</button><button class="cc cancel-edit" type="button">Cancel</button></div><p class="form-message" role="status"></p></form>`}
  </article>`;
}

export function mountSpicesView(container) {
  let disposed = false;
  let items = [];
  container.innerHTML = `<section class="board spice-board"><h1 class="hd">The Spice Rack</h1>
    <label class="fl spice-filter"><span class="lb">Filter rubs</span><input class="ci" type="search" placeholder="Brand or rub name"></label>
    <p class="mut spice-message" role="status">Checking the rack…</p><div class="spice-groups"></div>
    <form class="stp add-spice"><h2>Add a rub</h2><div class="spice-add-fields"></div><p class="custom-hint">Use brand “Custom” for a reusable homemade blend and put the ingredients in notes.</p><div class="form-actions"><button class="pbtn save-spice" type="submit">Add to the rack</button></div><p class="form-message" role="status"></p></form></section>`;
  const groupsRoot = container.querySelector(".spice-groups");
  const message = container.querySelector(".spice-message");
  const addForm = container.querySelector(".add-spice");

  const brands = () => [...new Set(items.map((item) => item.brand))].sort((a, b) => a.localeCompare(b, undefined, { sensitivity: "base" }));

  const bindForm = (form, id = null) => form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const values = formValues(form);
    const formMessage = form.querySelector(".form-message");
    formMessage.textContent = "";
    formMessage.classList.remove("error");
    if (showValidation(form, validateSpice(values))) return;
    const button = form.querySelector(".save-spice");
    button.disabled = true;
    try {
      if (id === null) await createSpice(payload(values));
      else await updateSpice(id, payload(values));
      await load();
    } catch (error) {
      renderApiError(form, error);
    } finally {
      if (!disposed && button.isConnected) button.disabled = false;
    }
  });

  function render() {
    const visible = filterSpices(items, container.querySelector(".spice-filter input").value);
    const knownBrands = brands();
    groupsRoot.innerHTML = groupSpices(visible).map((group) => `<section class="spice-group"><h2>${escapeHtml(group.brand)}</h2><div class="spice-list">${group.items.map((item) => spiceCard(item, knownBrands)).join("")}</div></section>`).join("");
    message.textContent = items.length && !visible.length ? "No rubs match that filter." : "";
    groupsRoot.querySelectorAll(".spice-card").forEach((card) => {
      const id = Number(card.dataset.id);
      bindItemPhoto(card.querySelector("[data-photo]"), "spices", id);
      const edit = card.querySelector(".edit-spice");
      if (!edit) return;
      const summary = card.querySelector(".spice-summary");
      const editForm = card.querySelector(".edit-form");
      edit.addEventListener("click", () => { summary.hidden = true; editForm.hidden = false; });
      card.querySelector(".cancel-edit").addEventListener("click", () => { editForm.hidden = true; summary.hidden = false; });
      card.querySelector(".delete-spice").addEventListener("click", () => {
        const prompt = card.querySelector(".delete-confirm");
        confirmDelete(prompt, async () => {
          try { await deleteSpice(id); await load(); }
          catch (error) {
            const text = error.status === 409 && error.message === "Spice is referenced by a cook" ? "This rub is used by a cook and cannot be deleted." : error.message;
            prompt.innerHTML = '<p class="form-message error" role="status"></p><button class="cc close-error" type="button">Okay</button>';
            prompt.querySelector(".form-message").textContent = text;
            prompt.querySelector(".close-error").addEventListener("click", () => { prompt.hidden = true; });
          }
        });
      });
      bindForm(editForm, id);
    });
  }

  async function load() {
    message.textContent = "Loading the spice rack…";
    try {
      items = await listSpices();
      if (disposed) return;
      addForm.querySelector(".spice-add-fields").innerHTML = fields({}, brands());
      if (!addForm.dataset.bound) { bindForm(addForm); addForm.dataset.bound = "true"; }
      message.textContent = items.length ? "" : "The spice rack is bare.";
      render();
    } catch (error) {
      if (disposed) return;
      console.error("Could not load spices", error);
      message.textContent = "Could not load the spice rack.";
    }
  }

  container.querySelector(".spice-filter input").addEventListener("input", render);
  load();
  return () => { disposed = true; };
}
