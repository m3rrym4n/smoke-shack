import {
  createPellet, deletePellet, getCooksForPellet, getPellets, updatePellet,
} from "../api.js";
import { confirmDelete, formatDate, formatMoney, renderApiError } from "../components/ui.js";
import { validatePellet } from "../pellets-logic.js";

const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (character) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
})[character]);

function today() {
  const now = new Date();
  const offset = now.getTimezoneOffset() * 60000;
  return new Date(now - offset).toISOString().slice(0, 10);
}

function fields(item = {}) {
  return `<div class="pellet-form-grid">
    <label class="fl"><span class="lb">Vendor</span><input class="ci" name="vendor" required value="${escapeHtml(item.vendor)}" placeholder="Bear Mountain"></label>
    <label class="fl"><span class="lb">Product name</span><input class="ci" name="product_name" required value="${escapeHtml(item.product_name)}" placeholder="Hickory"></label>
    <label class="fl"><span class="lb">Price per pound</span><input class="ci" name="price_per_pound" type="number" min="0" step="0.01" inputmode="decimal" required value="${escapeHtml(item.price_per_pound)}"></label>
    <label class="fl"><span class="lb">Purchased</span><input class="ci" name="purchased_on" type="date" required value="${escapeHtml(item.purchased_on || today())}"></label>
  </div>`;
}

function formValues(form) {
  const data = new FormData(form);
  return {
    vendor: String(data.get("vendor") || "").trim(),
    product_name: String(data.get("product_name") || "").trim(),
    price_per_pound: String(data.get("price_per_pound") || ""),
    purchased_on: String(data.get("purchased_on") || ""),
  };
}

function payload(values) {
  return { ...values, price_per_pound: Number(values.price_per_pound) };
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

function purchaseRow(item, cook) {
  const badge = cook ? `<a class="used-badge" href="#cooks/${cook.id}">used in cook #${cook.id}</a>` : "";
  return `<article class="pellet-row" data-id="${item.id}">
    <div class="pellet-summary">
      <div class="pellet-title-line"><strong>${escapeHtml(item.vendor)}</strong><span>${escapeHtml(item.product_name)}</span>${badge}</div>
      <div class="ld pellet-details"><span>${formatMoney(item.price_per_pound)}/lb</span><i></i><span>${formatDate(item.purchased_on)}</span></div>
      <div class="row-actions"><button class="cc edit-pellet" type="button">Edit</button><button class="cc delete-pellet" type="button">Delete</button></div>
      <div class="delete-confirm" hidden></div>
    </div>
    <form class="stp edit-form" hidden>${fields(item)}<div class="form-actions"><button class="pbtn save-pellet" type="submit">Save pellets</button><button class="cc cancel-edit" type="button">Cancel</button></div><p class="form-message" role="status"></p></form>
  </article>`;
}

export function mountPelletsView(container) {
  let disposed = false;
  container.innerHTML = `<section class="board pellet-board"><h1 class="hd">The Pellet Pantry</h1><p class="mut pantry-message" role="status">Checking the pantry…</p><div class="pellet-list"></div><form class="stp add-pellet"><h2>Add pellets</h2>${fields()}<div class="form-actions"><button class="pbtn save-pellet" type="submit">Stock the pantry</button></div><p class="form-message" role="status"></p></form></section>`;
  const list = container.querySelector(".pellet-list");
  const pantryMessage = container.querySelector(".pantry-message");

  const bindForm = (form, id = null) => form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const values = formValues(form);
    const message = form.querySelector(".form-message");
    message.textContent = "";
    message.classList.remove("error");
    if (showValidation(form, validatePellet(values))) return;
    const button = form.querySelector(".save-pellet");
    button.disabled = true;
    try {
      if (id === null) await createPellet(payload(values));
      else await updatePellet(id, payload(values));
      await load();
    } catch (error) {
      renderApiError(form, error);
    } finally {
      if (!disposed && button.isConnected) button.disabled = false;
    }
  });

  const bindRows = () => list.querySelectorAll(".pellet-row").forEach((row) => {
    const id = Number(row.dataset.id);
    const summary = row.querySelector(".pellet-summary");
    const editForm = row.querySelector(".edit-form");
    row.querySelector(".edit-pellet").addEventListener("click", () => {
      summary.hidden = true;
      editForm.hidden = false;
    });
    row.querySelector(".cancel-edit").addEventListener("click", () => {
      editForm.hidden = true;
      summary.hidden = false;
    });
    row.querySelector(".delete-pellet").addEventListener("click", () => {
      const prompt = row.querySelector(".delete-confirm");
      confirmDelete(prompt, async () => {
        try {
          await deletePellet(id);
          await load();
        } catch (error) {
          const text = error.message === "Pellet is referenced by a cook"
            ? "These pellets are used in a cook and cannot be deleted."
            : error.message;
          prompt.innerHTML = `<p class="form-message error" role="status">${escapeHtml(text)}</p><button class="cc close-error" type="button">Okay</button>`;
          prompt.querySelector(".close-error").addEventListener("click", () => { prompt.hidden = true; });
        }
      });
    });
    bindForm(editForm, id);
  });

  async function load() {
    pantryMessage.textContent = "Loading the pantry…";
    try {
      const items = await getPellets();
      const cooks = await Promise.all(items.map((item) => getCooksForPellet(item.id)));
      if (disposed) return;
      list.innerHTML = items.map((item, index) => purchaseRow(item, cooks[index][0])).join("");
      pantryMessage.textContent = items.length ? "" : "The pantry is bare.";
      bindRows();
    } catch (error) {
      if (disposed) return;
      console.error("Could not load pellet purchases", error);
      pantryMessage.textContent = "Could not load the pellet pantry.";
    }
  }

  bindForm(container.querySelector(".add-pellet"));
  load();
  return () => { disposed = true; };
}
