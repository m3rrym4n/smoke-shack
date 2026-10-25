import { createMeat, deleteMeat, getCooksForMeat, getMeat, updateMeat } from "../api.js";
import { confirmDelete, formatDate, formatMoney, renderApiError } from "../components/ui.js";
import { cookedFilterValue, totalCost, validateMeat } from "../meat-logic.js";

const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (character) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
})[character]);

function today() {
  const now = new Date();
  const offset = now.getTimezoneOffset() * 60000;
  return new Date(now - offset).toISOString().slice(0, 10);
}

function fields(item = {}) {
  return `<div class="meat-form-grid">
    <label class="fl"><span class="lb">Type</span><input class="ci" name="type" required value="${escapeHtml(item.type)}" placeholder="Pork butt"></label>
    <label class="fl"><span class="lb">Pounds</span><input class="ci" name="pounds" type="number" min="0.01" step="0.01" inputmode="decimal" required value="${escapeHtml(item.pounds)}"></label>
    <label class="fl"><span class="lb">Price per pound</span><input class="ci" name="price_per_pound" type="number" min="0.01" step="0.01" inputmode="decimal" required value="${escapeHtml(item.price_per_pound)}"></label>
    <label class="fl"><span class="lb">Store</span><input class="ci" name="store" value="${escapeHtml(item.store)}" placeholder="Local butcher"></label>
    <label class="fl"><span class="lb">Purchased</span><input class="ci" name="purchased_on" type="date" required value="${escapeHtml(item.purchased_on || today())}"></label>
  </div>`;
}

function formValues(form) {
  const data = new FormData(form);
  return {
    type: String(data.get("type") || "").trim(),
    pounds: String(data.get("pounds") || ""),
    price_per_pound: String(data.get("price_per_pound") || ""),
    store: String(data.get("store") || "").trim() || null,
    purchased_on: String(data.get("purchased_on") || ""),
  };
}

function payload(values) {
  return { ...values, pounds: Number(values.pounds), price_per_pound: Number(values.price_per_pound) };
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
  return `<article class="meat-row${item.cooked ? " is-cooked" : ""}" data-id="${item.id}">
    <div class="meat-summary">
      <div class="meat-title-line"><strong>${escapeHtml(item.type)}</strong><span class="cooked-badge"${item.cooked ? "" : " hidden"}>Cooked</span>${badge}</div>
      <div class="ld meat-details"><span>${item.pounds} lb · ${formatMoney(item.price_per_pound)}/lb · ${escapeHtml(item.store || "Store not noted")} · ${formatDate(item.purchased_on)}</span><i></i><b>${formatMoney(totalCost(item.pounds, item.price_per_pound))}</b></div>
      <div class="row-actions"><label class="cooked-control"><input class="cooked-toggle" type="checkbox"${item.cooked ? " checked" : ""}><span>Cooked</span></label><button class="cc edit-meat" type="button">Edit</button><button class="cc delete-meat" type="button">Delete</button></div>
      <p class="toggle-message form-message" role="status"></p>
      <div class="delete-confirm" hidden></div>
    </div>
    <form class="stp edit-form" hidden>${fields(item)}<div class="form-actions"><button class="pbtn save-meat" type="submit">Save cut</button><button class="cc cancel-edit" type="button">Cancel</button></div><p class="form-message" role="status"></p></form>
  </article>`;
}

export function mountMeatView(container) {
  let disposed = false;
  let activeFilter = "all";
  container.innerHTML = `<section class="board meat-board"><h1 class="hd">The Butcher Case</h1><div class="meat-filters" aria-label="Filter meat"><button class="cc active" type="button" data-filter="all" aria-pressed="true">All</button><button class="cc" type="button" data-filter="uncooked" aria-pressed="false">Uncooked</button><button class="cc" type="button" data-filter="cooked" aria-pressed="false">Cooked</button></div><p class="mut case-message" role="status">Checking the case…</p><div class="meat-list"></div><form class="stp add-meat"><h2>Add a cut</h2>${fields()}<div class="form-actions"><button class="pbtn save-meat" type="submit">Add to the case</button></div><p class="form-message" role="status"></p></form></section>`;
  const list = container.querySelector(".meat-list");
  const caseMessage = container.querySelector(".case-message");

  const updateEmptyMessage = () => {
    caseMessage.textContent = list.children.length ? "" : "Nothing in the case for this filter.";
  };

  const bindForm = (form, id = null) => form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const values = formValues(form);
    const message = form.querySelector(".form-message");
    message.textContent = "";
    message.classList.remove("error");
    if (showValidation(form, validateMeat(values))) return;
    const button = form.querySelector(".save-meat");
    button.disabled = true;
    try {
      if (id === null) await createMeat(payload(values));
      else await updateMeat(id, payload(values));
      await load();
    } catch (error) {
      renderApiError(form, error);
    } finally {
      if (!disposed && button.isConnected) button.disabled = false;
    }
  });

  const bindRows = () => list.querySelectorAll(".meat-row").forEach((row) => {
    const id = Number(row.dataset.id);
    const summary = row.querySelector(".meat-summary");
    const editForm = row.querySelector(".edit-form");
    const cookedToggle = row.querySelector(".cooked-toggle");
    cookedToggle.addEventListener("change", async () => {
      const cooked = cookedToggle.checked;
      const message = row.querySelector(".toggle-message");
      cookedToggle.disabled = true;
      message.textContent = "Saving…";
      message.classList.remove("error");
      try {
        const updated = await updateMeat(id, { cooked });
        if (disposed) return;
        cookedToggle.checked = updated.cooked;
        row.classList.toggle("is-cooked", updated.cooked);
        row.querySelector(".cooked-badge").hidden = !updated.cooked;
        message.textContent = updated.cooked ? "Marked cooked." : "Marked uncooked.";
        if (cookedFilterValue(activeFilter) !== null && cookedFilterValue(activeFilter) !== updated.cooked) {
          row.remove();
          updateEmptyMessage();
        }
      } catch (error) {
        cookedToggle.checked = !cooked;
        message.textContent = error.message;
        message.classList.add("error");
      } finally {
        if (!disposed && cookedToggle.isConnected) cookedToggle.disabled = false;
      }
    });
    row.querySelector(".edit-meat").addEventListener("click", () => {
      summary.hidden = true;
      editForm.hidden = false;
    });
    row.querySelector(".cancel-edit").addEventListener("click", () => {
      editForm.hidden = true;
      summary.hidden = false;
    });
    row.querySelector(".delete-meat").addEventListener("click", () => {
      const prompt = row.querySelector(".delete-confirm");
      confirmDelete(prompt, async () => {
        try {
          await deleteMeat(id);
          await load();
        } catch (error) {
          prompt.innerHTML = `<p class="form-message error" role="status">${escapeHtml(error.message)}</p><button class="cc close-error" type="button">Okay</button>`;
          prompt.querySelector(".close-error").addEventListener("click", () => { prompt.hidden = true; });
        }
      });
    });
    bindForm(editForm, id);
  });

  async function load() {
    caseMessage.textContent = "Loading the case…";
    try {
      const items = await getMeat(cookedFilterValue(activeFilter));
      const cooks = await Promise.all(items.map((item) => getCooksForMeat(item.id)));
      if (disposed) return;
      list.innerHTML = items.map((item, index) => purchaseRow(item, cooks[index][0])).join("");
      caseMessage.textContent = items.length ? "" : "Nothing in the case yet.";
      bindRows();
    } catch (error) {
      if (disposed) return;
      console.error("Could not load meat purchases", error);
      caseMessage.textContent = "Could not load the butcher case.";
    }
  }

  bindForm(container.querySelector(".add-meat"));
  container.querySelectorAll(".meat-filters button").forEach((button) => {
    button.addEventListener("click", () => {
      activeFilter = button.dataset.filter;
      container.querySelectorAll(".meat-filters button").forEach((candidate) => {
        const active = candidate === button;
        candidate.classList.toggle("active", active);
        candidate.setAttribute("aria-pressed", String(active));
      });
      load();
    });
  });
  load();
  return () => { disposed = true; };
}
