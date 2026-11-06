import {
  createFuel, deleteFuel, getCooksForPellet, getFuel, updateFuel,
} from "../api.js";
import { confirmDelete, formatDate, formatMoney, renderApiError } from "../components/ui.js";
import { bindItemPhoto, itemPhotoMarkup } from "../components/item-photo.js";
import {
  bagCostDisplay, cleanUpc, groupPelletsByType, splitPellets, validatePellet, validateUpc,
} from "../pellets-logic.js";

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
    <label class="fl"><span class="lb">Type</span><select class="ci" name="type" required><option value="">Choose a type</option>${["pellets", "charcoal", "wood"].map((type) => `<option value="${type}"${item.type === type ? " selected" : ""}>${type[0].toUpperCase() + type.slice(1)}</option>`).join("")}</select></label>
    <label class="fl"><span class="lb">Vendor</span><input class="ci" name="vendor" required value="${escapeHtml(item.vendor)}" placeholder="Bear Mountain"></label>
    <label class="fl"><span class="lb">Product name</span><input class="ci" name="product_name" required value="${escapeHtml(item.product_name)}" placeholder="Hickory"></label>
    <label class="fl"><span class="lb">Price per pound <small>(optional)</small></span><input class="ci" name="price_per_pound" type="number" min="0" step="0.01" inputmode="decimal" value="${escapeHtml(item.price_per_pound)}"></label>
    <label class="fl"><span class="lb">UPC / barcode <small>(optional)</small></span><input class="ci pellet-upc" name="upc" inputmode="numeric" autocomplete="off" pattern="[0-9]*" minlength="8" maxlength="14" value="${escapeHtml(item.upc)}" placeholder="012345678905"></label>
    <label class="fl"><span class="lb">Bag size (lb) <small>(optional)</small></span><input class="ci" name="bag_size_lb" type="number" min="0.01" max="100" step="any" inputmode="decimal" value="${escapeHtml(item.bag_size_lb)}"></label>
    <label class="fl"><span class="lb">Purchased</span><input class="ci" name="purchased_on" type="date" required value="${escapeHtml(item.purchased_on || today())}"></label>
  </div>`;
}

function formValues(form) {
  const data = new FormData(form);
  return {
    type: String(data.get("type") || ""),
    vendor: String(data.get("vendor") || "").trim(),
    product_name: String(data.get("product_name") || "").trim(),
    price_per_pound: String(data.get("price_per_pound") || ""),
    upc: cleanUpc(data.get("upc")),
    bag_size_lb: String(data.get("bag_size_lb") || ""),
    purchased_on: String(data.get("purchased_on") || ""),
  };
}

function payload(values) {
  return {
    ...values,
    price_per_pound: values.price_per_pound === "" ? null : Number(values.price_per_pound),
    upc: values.upc || null,
    bag_size_lb: values.bag_size_lb === "" ? null : Number(values.bag_size_lb),
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

function purchaseRow(item, cook) {
  const badge = cook ? `<a class="used-badge" href="#cooks/${cook.id}">used in cook #${cook.id}</a>` : "";
  const upc = item.upc ? `<span class="pellet-upc-display">UPC ${escapeHtml(item.upc)}</span><i></i>` : "";
  const bagSize = item.bag_size_lb == null ? "" : `<span>${escapeHtml(item.bag_size_lb)} lb bag</span><i></i>`;
  const bagCost = bagCostDisplay(item);
  const emptyDate = item.is_empty ? `<span>Empty ${formatDate(item.emptied_on)}</span>` : "";
  const stockAction = item.is_empty
    ? '<button class="cc undo-empty" type="button">Undo</button>'
    : '<button class="cc mark-empty" type="button">Mark empty</button>';
  return `<article class="pellet-row${item.is_empty ? " is-empty" : ""}" data-id="${item.id}">
    <div class="pellet-summary">
      <div class="pellet-title-line"><strong>${escapeHtml(item.vendor)}</strong><span>${escapeHtml(item.product_name)}</span>${badge}</div>
      <div class="ld pellet-details"><span>${item.price_per_pound == null ? "—" : `${formatMoney(item.price_per_pound)}/lb`}</span><i></i>${bagSize}${bagCost ? `<span>${escapeHtml(bagCost)}</span><i></i>` : ""}${upc}<span>${formatDate(item.purchased_on)}</span>${emptyDate}</div>
      ${itemPhotoMarkup(item)}
      <div class="row-actions">${stockAction}<button class="cc edit-pellet" type="button">Edit</button><button class="cc delete-pellet" type="button">Delete</button></div>
      <div class="delete-confirm" hidden></div>
    </div>
    <form class="stp edit-form" hidden>${fields(item)}<div class="form-actions"><button class="pbtn save-pellet" type="submit">Save fuel</button><button class="cc cancel-edit" type="button">Cancel</button></div><p class="form-message" role="status"></p></form>
  </article>`;
}

export function mountPelletsView(container) {
  let disposed = false;
  container.innerHTML = `<section class="board pellet-board"><h1 class="hd">Fuel</h1><div class="pellet-lookup"><label class="fl"><span class="lb">Type</span><select class="ci" name="type_filter"><option value="">All types</option><option value="pellets">Pellets</option><option value="charcoal">Charcoal</option><option value="wood">Wood</option></select></label><label class="fl"><span class="lb">Find by UPC</span><input class="ci" name="upc_lookup" inputmode="numeric" autocomplete="off" pattern="[0-9]*" maxlength="14" placeholder="Type or paste a barcode"><small class="mut lookup-message" role="status"></small></label></div><p class="mut pantry-message" role="status">Checking the pantry…</p><div class="pellet-list"></div><form class="stp add-pellet"><h2>Add fuel</h2>${fields()}<div class="form-actions"><button class="pbtn save-pellet" type="submit">Stock the pantry</button></div><p class="form-message" role="status"></p></form></section>`;
  const list = container.querySelector(".pellet-list");
  const pantryMessage = container.querySelector(".pantry-message");
  const lookup = container.querySelector("[name=upc_lookup]");
  const typeFilter = container.querySelector("[name=type_filter]");
  const lookupMessage = container.querySelector(".lookup-message");
  let loadSequence = 0;

  const bindUpcCleaning = (root) => root.querySelectorAll(".pellet-upc").forEach((input) => {
    input.addEventListener("input", () => { input.value = cleanUpc(input.value); });
  });

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
      if (id === null) await createFuel(payload(values));
      else await updateFuel(id, payload(values));
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
    bindItemPhoto(row.querySelector("[data-photo]"), "fuel", id);
    row.querySelector(".mark-empty")?.addEventListener("click", async (event) => {
      event.currentTarget.disabled = true;
      try { await updateFuel(id, { emptied_on: today() }); await load(); }
      catch (error) { pantryMessage.textContent = error.message; event.currentTarget.disabled = false; }
    });
    row.querySelector(".undo-empty")?.addEventListener("click", async (event) => {
      event.currentTarget.disabled = true;
      try { await updateFuel(id, { emptied_on: null }); await load(); }
      catch (error) { pantryMessage.textContent = error.message; event.currentTarget.disabled = false; }
    });
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
          await deleteFuel(id);
          await load();
        } catch (error) {
          const text = error.message === "Fuel is referenced by a cook"
            ? "This fuel is used in a cook and cannot be deleted."
            : error.message;
          prompt.innerHTML = `<p class="form-message error" role="status">${escapeHtml(text)}</p><button class="cc close-error" type="button">Okay</button>`;
          prompt.querySelector(".close-error").addEventListener("click", () => { prompt.hidden = true; });
        }
      });
    });
    bindForm(editForm, id);
    bindUpcCleaning(editForm);
  });

  async function load(upc = cleanUpc(lookup.value)) {
    const sequence = ++loadSequence;
    pantryMessage.textContent = "Loading the pantry…";
    try {
      const items = await getFuel(typeFilter.value, upc, true);
      const cooks = await Promise.all(items.map((item) => getCooksForPellet(item.id)));
      if (disposed || sequence !== loadSequence) return;
      const cookById = new Map(items.map((item, index) => [item.id, cooks[index][0]]));
      const groups = splitPellets(items);
      const rows = (group) => group.map((item) => purchaseRow(item, cookById.get(item.id))).join("");
      const stockSections = groupPelletsByType(groups.inStock)
        .map((group) => `<section class="fuel-type"><h2>${group.label}</h2>${rows(group.items)}</section>`)
        .join("");
      list.innerHTML = `${stockSections}${groups.empty.length ? `<section class="empty-pellets"><h2>Empty bags</h2>${rows(groups.empty)}</section>` : ""}`;
      pantryMessage.textContent = items.length ? "" : (upc ? "No fuel matches that UPC." : "The pantry is bare.");
      bindRows();
    } catch (error) {
      if (disposed || sequence !== loadSequence) return;
      console.error("Could not load fuel purchases", error);
      pantryMessage.textContent = "Could not load the fuel pantry.";
    }
  }

  const addForm = container.querySelector(".add-pellet");
  bindForm(addForm);
  bindUpcCleaning(addForm);
  lookup.addEventListener("input", () => {
    lookup.value = cleanUpc(lookup.value);
    const error = validateUpc(lookup.value);
    lookupMessage.textContent = error;
    lookupMessage.classList.toggle("error", Boolean(error));
    if (!error) load(lookup.value);
  });
  typeFilter.addEventListener("change", () => load());
  load();
  return () => { disposed = true; };
}
