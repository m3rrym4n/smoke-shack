import { createCookEvent, createPlannedCook, deleteCook, deleteCookEvent, deletePhoto, updateCook, updateCookEvent, uploadCookPhoto } from "../api.js";
import { availableMeat, meatOptionLabel, pelletOptionLabel, validatePelletsUsed } from "../order-pad-logic.js";
import { closedCookReadOnlyFields, orderPadSavedMessage, orderPlannedCooks } from "../live-logic.js";
import { confirmDelete } from "./ui.js";

const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (character) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
})[character]);

const kinds = ["stall", "wrapped", "spritzed", "sauced", "flipped", "rested", "custom"];
const labels = { stall: "Stall", wrapped: "Wrapped", spritzed: "Spritzed", sauced: "Sauced", flipped: "Flipped", rested: "Rested", custom: "Custom" };

function localDateTime(value) {
  const date = new Date(value);
  const offset = date.getTimezoneOffset() * 60000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 16);
}

export function pinBoardMarkup() {
  return `<section class="board pin-board">
    <h2 class="hd">Pin an event</h2>
    <form id="event-form" novalidate>
      <div class="event-kinds" role="group" aria-label="Event type">${kinds.map((kind) => `<button class="cc${kind === "stall" ? " on" : ""}" type="button" data-kind="${kind}">${labels[kind]}</button>`).join("")}</div>
      <input name="kind" type="hidden" value="stall">
      <label class="fl"><span class="lb">Title</span><input class="ci" name="title" required maxlength="200" value="Stall"></label>
      <fieldset class="when-field"><legend class="lb">When</legend><div class="seg"><button class="on" type="button" data-when="now">Right now</button><button type="button" data-when="pick">Pick date &amp; time</button></div><input class="ci" name="ts" type="datetime-local" hidden></fieldset>
      <label class="fl"><span class="lb">What happened</span><textarea class="ci" name="description" rows="4"></textarea></label>
      <p class="form-message" role="status" aria-live="polite"></p>
      <div class="form-actions"><button class="pbtn save-event" type="submit">Pin it</button><button class="cc cancel-event" type="button" hidden>Cancel edit</button><button class="cc delete-event" type="button" hidden>Delete</button></div>
    </form>
  </section>`;
}

function options(rows, selected, label) {
  return rows.map((row) => `<option value="${row.id}"${row.id === selected ? " selected" : ""}>${escapeHtml(label(row))}</option>`).join("");
}

function money(value) {
  return value == null ? "—" : `$${Number(value).toFixed(2)}`;
}

export function orderPadMarkup(cook, meat, pellets, cooks = [], config = {}) {
  const { mode = "live", banner = "Cook in progress", planned = [], photos = [] } = config;
  const model = cook || { id: null, meat_id: null, pellet_id: null, rotisserie: false };
  const choices = availableMeat(meat, cooks, model.id);
  const meatEmpty = choices.length === 0;
  const pelletEmpty = pellets.length === 0;
  const locked = new Set(mode === "closed" ? closedCookReadOnlyFields() : []);
  const disabled = (name) => locked.has(name) ? " disabled" : "";
  const otherPlans = orderPlannedCooks(planned).filter((item) => item.id !== model.id);
  const actions = mode === "closed"
    ? '<a class="paper-link" href="#live">Back to the next order</a>'
    : `${mode === "live" || mode === "planned" ? '<a class="paper-button" href="#live?new=1">New order for the next cook</a>' : ""}<a class="paper-link" href="#live?closed=1">Write up the last cook</a>`;
  return `<section class="order-pad">
    <span class="tape" aria-hidden="true"></span><div class="order-heading"><h2>ORDER PAD</h2><span>${model.id ? `No. ${String(model.id).padStart(4, "0")}` : "New ticket"}</span></div>
    <p class="order-mode">${escapeHtml(banner)}</p><div class="order-actions">${actions}</div>
    <form id="order-form" novalidate>
      <label class="paper-field"><span>Meat</span><select name="meat_id"${disabled("meat_id")}><option value="">Not selected</option>${options(choices, model.meat_id, meatOptionLabel)}<option value="add">${meatEmpty ? "Nothing in the case yet, add some" : "+ Add new..."}</option></select></label>
      <label class="paper-field"><span>Weight</span><input name="weight" readonly value="${escapeHtml(model.meat?.pounds ? `${model.meat.pounds} lb` : "—")}"></label>
      <div class="paper-field"><span>Meat cost</span><output name="meat_cost">${money(model.cost?.meat_cost)}</output></div>
      <label class="paper-field"><span>Seasonings</span><input name="seasonings"${disabled("seasonings")} value="${escapeHtml(model.seasonings)}"></label>
      <label class="paper-field"><span>Sauces</span><input name="sauces"${disabled("sauces")} value="${escapeHtml(model.sauces)}"></label>
      <label class="paper-field"><span>Prep time</span><span class="input-suffix"><input name="prep_time_minutes" type="number" min="0" step="1"${disabled("prep_time_minutes")} value="${model.prep_time_minutes ?? ""}"><b>minutes</b></span></label>
      <label class="paper-field"><span>Pellets</span><select name="pellet_id"${disabled("pellet_id")}><option value="">Not selected</option>${options(pellets, model.pellet_id, pelletOptionLabel)}<option value="add">${pelletEmpty ? "Nothing in the pantry yet, add some" : "+ Add new..."}</option></select></label>
      <label class="paper-field"><span>Pellets used</span><span class="input-suffix"><input name="pellets_used_lb" type="number" min="0" step="0.01" value="${model.pellets_used_lb ?? ""}"><b>lb</b></span></label>
      <div class="paper-field"><span>Pellet cost</span><output name="pellet_cost">${money(model.cost?.pellet_cost)}</output></div>
      <label class="paper-field"><span>Profile used</span><input readonly value="${escapeHtml(model.profile_name || "None")}"></label>
      <fieldset class="paper-field rotisserie"${disabled("rotisserie")}><legend>Rotisserie</legend><label><input type="radio" name="rotisserie" value="true"${model.rotisserie ? " checked" : ""}${disabled("rotisserie")}> Yes</label><label><input type="radio" name="rotisserie" value="false"${model.rotisserie ? "" : " checked"}${disabled("rotisserie")}> No</label></fieldset>
      <label class="paper-field paper-area"><span>How it turned out</span><textarea name="results_text" rows="4">${escapeHtml(model.results_text)}</textarea></label>
      <label class="paper-field paper-area"><span>Photos</span><input name="photo" type="file" accept="image/jpeg,image/png,image/webp"></label>
      <div class="order-photos">${photos.map((photo) => `<span><a href="${photo.url}" target="_blank" rel="noopener">Photo ${photo.id}</a><button class="paper-button delete-photo" type="button" data-photo-id="${photo.id}">Delete</button></span>`).join("")}</div>
      <p class="form-message" role="status" aria-live="polite"></p>
      <button class="pbtn order-save" type="submit">Save order</button>
    </form>
    ${otherPlans.length ? `<div class="planned-orders"><h3>Other planned orders</h3>${otherPlans.map((item) => `<div><a href="#live?order=${item.id}">Order #${item.id}${item.meat?.type ? ` · ${escapeHtml(item.meat.type)}` : ""}</a><button class="paper-button cancel-plan" data-cook-id="${item.id}" type="button">Cancel</button><span class="plan-confirm" hidden></span></div>`).join("")}</div>` : ""}
  </section>`;
}

function showMessage(form, message, error = false) {
  const output = form.querySelector(".form-message");
  output.textContent = message;
  output.classList.toggle("error", error);
}

function apiMessage(error) {
  return typeof error.message === "string" ? error.message : "Something went wrong. Please try again.";
}

export function bindLiveForms(container, { cook, orderCook = cook, events, meat, pellets, refresh, setBusy, mode = "live" }) {
  const eventForm = container.querySelector("#event-form");
  const orderForm = container.querySelector("#order-form");
  if (eventForm) {
  let editingId = null;
  let useNow = true;

  const resetEvent = () => {
    editingId = null;
    useNow = true;
    eventForm.reset();
    eventForm.elements.kind.value = "stall";
    eventForm.elements.title.value = "Stall";
    eventForm.elements.ts.hidden = true;
    eventForm.querySelectorAll("[data-kind]").forEach((button) => button.classList.toggle("on", button.dataset.kind === "stall"));
    eventForm.querySelectorAll("[data-when]").forEach((button) => button.classList.toggle("on", button.dataset.when === "now"));
    eventForm.querySelector(".save-event").textContent = "Pin it";
    eventForm.querySelector(".cancel-event").hidden = true;
    eventForm.querySelector(".delete-event").hidden = true;
    showMessage(eventForm, "");
    setBusy(false);
  };

  eventForm.addEventListener("input", () => setBusy(true));
  eventForm.querySelectorAll("[data-kind]").forEach((button) => button.addEventListener("click", () => {
    eventForm.elements.kind.value = button.dataset.kind;
    eventForm.querySelectorAll("[data-kind]").forEach((item) => item.classList.toggle("on", item === button));
    if (!editingId || kinds.map((kind) => labels[kind]).includes(eventForm.elements.title.value)) eventForm.elements.title.value = labels[button.dataset.kind];
    setBusy(true);
  }));
  eventForm.querySelectorAll("[data-when]").forEach((button) => button.addEventListener("click", () => {
    useNow = button.dataset.when === "now";
    eventForm.querySelectorAll("[data-when]").forEach((item) => item.classList.toggle("on", item === button));
    eventForm.elements.ts.hidden = useNow;
    if (!useNow && !eventForm.elements.ts.value) eventForm.elements.ts.value = localDateTime(new Date());
    setBusy(true);
  }));
  eventForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const title = eventForm.elements.title.value.trim();
    if (!title) return showMessage(eventForm, "Give the event a title.", true);
    if (!useNow && !eventForm.elements.ts.value) return showMessage(eventForm, "Choose a date and time.", true);
    const body = { kind: eventForm.elements.kind.value, title, description: eventForm.elements.description.value.trim() || null };
    if (!useNow) body.ts = new Date(eventForm.elements.ts.value).toISOString();
    const submit = eventForm.querySelector(".save-event");
    submit.disabled = true;
    try {
      if (editingId) await updateCookEvent(editingId, body); else await createCookEvent(cook.id, body);
      resetEvent();
      await refresh();
    } catch (error) {
      showMessage(eventForm, apiMessage(error), true);
      submit.disabled = false;
    }
  });
  eventForm.querySelector(".cancel-event").addEventListener("click", resetEvent);
  eventForm.querySelector(".delete-event").addEventListener("click", async () => {
    const button = eventForm.querySelector(".delete-event");
    button.disabled = true;
    try { await deleteCookEvent(editingId); resetEvent(); await refresh(); }
    catch (error) { showMessage(eventForm, apiMessage(error), true); button.disabled = false; }
  });
  container.querySelectorAll(".event-edit").forEach((button) => button.addEventListener("click", () => {
    const item = events.find((entry) => entry.id === Number(button.dataset.eventId));
    if (!item) return;
    editingId = item.id;
    useNow = false;
    eventForm.elements.kind.value = kinds.includes(item.kind) ? item.kind : "custom";
    eventForm.elements.title.value = item.title;
    eventForm.elements.description.value = item.description || "";
    eventForm.elements.ts.value = localDateTime(item.ts);
    eventForm.elements.ts.hidden = false;
    eventForm.querySelectorAll("[data-kind]").forEach((chip) => chip.classList.toggle("on", chip.dataset.kind === eventForm.elements.kind.value));
    eventForm.querySelectorAll("[data-when]").forEach((choice) => choice.classList.toggle("on", choice.dataset.when === "pick"));
    eventForm.querySelector(".save-event").textContent = "Save pin";
    eventForm.querySelector(".cancel-event").hidden = false;
    eventForm.querySelector(".delete-event").hidden = false;
    showMessage(eventForm, "Editing this pin.");
    setBusy(true);
    eventForm.scrollIntoView({ behavior: "smooth", block: "center" });
  }));
  }

  orderForm.addEventListener("input", () => setBusy(true));
  orderForm.elements.meat_id?.addEventListener("change", () => {
    if (orderForm.elements.meat_id.value === "add") { window.location.hash = "meat"; return; }
    const item = meat.find((row) => row.id === Number(orderForm.elements.meat_id.value));
    orderForm.elements.weight.value = item ? `${item.pounds} lb` : "—";
  });
  orderForm.elements.pellet_id?.addEventListener("change", () => {
    if (orderForm.elements.pellet_id.value === "add") window.location.hash = "pellets";
  });
  orderForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const prep = orderForm.elements.prep_time_minutes.value;
    if (prep && (!Number.isInteger(Number(prep)) || Number(prep) < 0)) return showMessage(orderForm, "Prep time must be a whole number of minutes.", true);
    const pelletsUsed = orderForm.elements.pellets_used_lb.value;
    const pelletsUsedError = validatePelletsUsed(pelletsUsed);
    if (pelletsUsedError) return showMessage(orderForm, pelletsUsedError, true);
    const body = {
      meat_id: orderForm.elements.meat_id.value ? Number(orderForm.elements.meat_id.value) : null,
      pellet_id: orderForm.elements.pellet_id.value ? Number(orderForm.elements.pellet_id.value) : null,
      seasonings: orderForm.elements.seasonings.value.trim() || null,
      sauces: orderForm.elements.sauces.value.trim() || null,
      prep_time_minutes: prep === "" ? null : Number(prep),
      pellets_used_lb: pelletsUsed === "" ? null : Number(pelletsUsed),
      rotisserie: orderForm.elements.rotisserie.value === "true",
      results_text: orderForm.elements.results_text.value.trim() || null,
    };
    if (mode === "closed") closedCookReadOnlyFields().forEach((field) => delete body[field]);
    const submit = orderForm.querySelector(".order-save");
    submit.disabled = true;
    try {
      const updated = mode === "new" ? await createPlannedCook(body) : await updateCook(orderCook.id, body);
      const photo = orderForm.elements.photo.files[0];
      if (photo) await uploadCookPhoto(updated.id, photo);
      orderForm.elements.meat_cost.value = money(updated.cost?.meat_cost);
      orderForm.elements.pellet_cost.value = money(updated.cost?.pellet_cost);
      setBusy(false);
      const savedMessage = orderPadSavedMessage(mode);
      if (mode === "new") {
        orderCook = updated;
        mode = "planned";
      }
      showMessage(orderForm, savedMessage);
      submit.disabled = false;
      if (savedMessage !== "Order saved.") window.history.replaceState(null, "", `#live?order=${updated.id}`);
    } catch (error) {
      showMessage(orderForm, apiMessage(error), true);
      submit.disabled = false;
    }
  });
  container.querySelectorAll(".cancel-plan").forEach((button) => button.addEventListener("click", () => {
    const prompt = button.parentElement.querySelector(".plan-confirm");
    confirmDelete(prompt, async () => { await deleteCook(Number(button.dataset.cookId)); await refresh(); });
  }));
  container.querySelectorAll(".delete-photo").forEach((button) => button.addEventListener("click", async () => {
    button.disabled = true;
    try { await deletePhoto(Number(button.dataset.photoId)); await refresh(); }
    catch (error) { showMessage(orderForm, apiMessage(error), true); button.disabled = false; }
  }));
}
