import {
  createNote, deleteNote, getNotes, getRecentCooks, getStatus, updateNote,
} from "../api.js";
import { confirmDelete, renderApiError } from "../components/ui.js";
import { notePayload, validateNote } from "../notes-logic.js";

const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (character) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
})[character]);

const scopeLabels = { this_cook: "This cook", pellets: "Pellets", gear: "Gear" };

function cookLabel(cook) {
  const date = cook.started_at
    ? new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", year: "numeric" }).format(new Date(cook.started_at))
    : "date unknown";
  return `Cook #${cook.id} · ${cook.meat?.type || date}`;
}

function cookOptions(cooks, selectedCookId) {
  if (!cooks.length) return '<option value="">No cooks available</option>';
  return `<option value="">Choose a cook</option>${cooks.map((cook) => (
    `<option value="${cook.id}"${cook.id === selectedCookId ? " selected" : ""}>${escapeHtml(cookLabel(cook))}</option>`
  )).join("")}`;
}

function fields(cooks, note = {}, defaultCookId = null) {
  const scope = note.scope || "this_cook";
  const selectedCookId = note.cook_id ?? defaultCookId;
  return `<div class="note-form-grid">
    <label class="fl"><span class="lb">Title</span><input class="ci" name="title" required value="${escapeHtml(note.title)}" placeholder="Remember next time"></label>
    <label class="fl note-body-field"><span class="lb">Note</span><textarea class="ci" name="body" rows="4" required placeholder="What should stay pinned up?">${escapeHtml(note.body)}</textarea></label>
    <label class="fl"><span class="lb">Scope</span><select class="ci note-scope" name="scope">
      ${Object.entries(scopeLabels).map(([value, label]) => `<option value="${value}"${scope === value ? " selected" : ""}>${label}</option>`).join("")}
    </select></label>
    <label class="fl cook-field"${scope === "this_cook" ? "" : " hidden"}><span class="lb">Cook</span><select class="ci" name="cook_id">${cookOptions(cooks, selectedCookId)}</select></label>
  </div>`;
}

function valuesFrom(form) {
  const data = new FormData(form);
  return {
    title: data.get("title"), body: data.get("body"), scope: data.get("scope"),
    cook_id: data.get("cook_id") ? Number(data.get("cook_id")) : null,
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

function noteCard(note, cooks, defaultCookId) {
  const date = new Intl.DateTimeFormat(undefined, {
    year: "numeric", month: "short", day: "numeric",
  }).format(new Date(note.created_at));
  const cookLink = note.cook_id === null
    ? ""
    : `<a href="#cooks/${note.cook_id}">cook #${note.cook_id}</a>`;
  return `<article class="note pit-note" data-id="${note.id}">
    <span class="tape" aria-hidden="true"></span>
    <div class="note-summary">
      <h2>${escapeHtml(note.title)}</h2><p>${escapeHtml(note.body)}</p>
      <footer><span>${escapeHtml(scopeLabels[note.scope])}</span>${cookLink}<time datetime="${escapeHtml(note.created_at)}">${date}</time></footer>
      <div class="paper-actions"><button class="paper-button edit-note" type="button">Edit</button><button class="paper-button delete-note" type="button">Delete</button></div>
      <div class="delete-confirm paper-confirm" hidden></div>
    </div>
    <form class="note-edit-form" hidden>${fields(cooks, note, defaultCookId)}<div class="paper-actions"><button class="paper-button primary save-note" type="submit">Save note</button><button class="paper-button cancel-edit" type="button">Cancel</button></div><p class="form-message" role="status"></p></form>
  </article>`;
}

export function mountNotesView(container) {
  let disposed = false;
  let filter = "all";
  let cooks = [];
  let activeCookId = null;
  container.innerHTML = `<section class="board notes-board">
    <h1 class="hd">Pit Notes</h1>
    <div class="note-filters" aria-label="Filter notes">
      <button class="cc on" data-scope="all" type="button">All</button><button class="cc" data-scope="this_cook" type="button">This cook</button><button class="cc" data-scope="pellets" type="button">Pellets</button><button class="cc" data-scope="gear" type="button">Gear</button>
    </div>
    <form class="stp add-note"><h2>Pin a note</h2><div class="note-fields"></div><div class="form-actions"><button class="pbtn save-note" type="submit">Pin it up</button></div><p class="form-message" role="status"></p></form>
    <p class="mut notes-message" role="status">Checking the board…</p><div class="notes-grid"></div>
  </section>`;
  const grid = container.querySelector(".notes-grid");
  const message = container.querySelector(".notes-message");
  const addForm = container.querySelector(".add-note");

  function bindScope(form) {
    const select = form.querySelector(".note-scope");
    select.addEventListener("change", () => {
      form.querySelector(".cook-field").hidden = select.value !== "this_cook";
    });
  }

  function bindForm(form, id = null) {
    bindScope(form);
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const values = valuesFrom(form);
      const status = form.querySelector(".form-message");
      status.textContent = "";
      status.classList.remove("error");
      if (showValidation(form, validateNote(values))) return;
      const button = form.querySelector(".save-note");
      button.disabled = true;
      try {
        if (id === null) await createNote(notePayload(values));
        else await updateNote(id, notePayload(values));
        await loadNotes();
        if (id === null) {
          form.reset();
          form.querySelector('[name="cook_id"]').value = activeCookId ?? "";
          form.querySelector(".cook-field").hidden = false;
        }
      } catch (error) {
        renderApiError(form, error);
      } finally {
        if (!disposed && button.isConnected) button.disabled = false;
      }
    });
  }

  function bindCards() {
    grid.querySelectorAll(".pit-note").forEach((card) => {
      const id = Number(card.dataset.id);
      const summary = card.querySelector(".note-summary");
      const editForm = card.querySelector(".note-edit-form");
      card.querySelector(".edit-note").addEventListener("click", () => { summary.hidden = true; editForm.hidden = false; });
      card.querySelector(".cancel-edit").addEventListener("click", () => { editForm.hidden = true; summary.hidden = false; });
      card.querySelector(".delete-note").addEventListener("click", () => {
        const prompt = card.querySelector(".delete-confirm");
        confirmDelete(prompt, async () => {
          try { await deleteNote(id); await loadNotes(); }
          catch (error) { prompt.textContent = error.message; }
        });
      });
      bindForm(editForm, id);
    });
  }

  async function loadNotes() {
    message.textContent = "Loading the notes…";
    try {
      const notes = await getNotes(filter);
      if (disposed) return;
      grid.innerHTML = notes.map((note) => noteCard(note, cooks, activeCookId)).join("");
      message.textContent = notes.length ? "" : "No notes pinned up yet.";
      bindCards();
    } catch (error) {
      if (!disposed) message.textContent = "Could not load the pit notes.";
      console.error("Could not load notes", error);
    }
  }

  container.querySelectorAll(".note-filters button").forEach((button) => button.addEventListener("click", async () => {
    filter = button.dataset.scope;
    container.querySelectorAll(".note-filters button").forEach((item) => item.classList.toggle("on", item === button));
    await loadNotes();
  }));

  Promise.all([getRecentCooks(50), getStatus()]).then(([recentCooks, status]) => {
    if (disposed) return;
    cooks = recentCooks;
    activeCookId = status.active_cook?.id ?? null;
    addForm.querySelector(".note-fields").innerHTML = fields(cooks, {}, activeCookId);
    bindForm(addForm);
    loadNotes();
  }).catch((error) => {
    console.error("Could not prepare pit notes", error);
    message.textContent = "Could not load the pit notes.";
  });

  return () => { disposed = true; };
}
