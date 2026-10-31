import {
  createMeatGroup, deleteMeatGroup, getCookStats, getCookStatsMeatTypes, getMeat,
  getMeatGroups, getPellets, renameMeatGroup, replaceMeatGroupTypes,
} from "../api.js";
import { renderApiError } from "../components/ui.js";
import {
  buildAnswerSentence, buildMeatOptions, cookTimePerPound, filtersFromHash, filtersToHash,
  formatDuration, statsQuery,
} from "../pitmaster-logic.js";

const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (character) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
})[character]);

const option = (value, label, selected) => `<option value="${escapeHtml(value)}"${value === selected ? " selected" : ""}>${escapeHtml(label)}</option>`;
const meatValue = (filters) => filters.meatGroup ? `group:${filters.meatGroup}` : (filters.meat ? `type:${filters.meat}` : "");

function formValues(form) {
  const data = new FormData(form);
  const selectedMeat = String(data.get("meat") || "");
  const [kind, ...parts] = selectedMeat.split(":");
  const value = parts.join(":");
  return {
    meat: kind === "type" ? value : "", meatGroup: kind === "group" ? value : "",
    poundsMin: String(data.get("pounds_min") || ""), poundsMax: String(data.get("pounds_max") || ""),
    setpoint: String(data.get("setpoint") || ""), tolerance: String(data.get("tolerance") || "10"),
    rotisserie: String(data.get("rotisserie") || "false"), pelletId: String(data.get("pellet_id") || ""),
  };
}

function summaryRow(label, summary) {
  return `<div class="pitmaster-stat"><strong>${label}</strong><span>Average <b>${formatDuration(summary?.avg)}</b></span><span>Min <b>${formatDuration(summary?.min)}</b></span><span>Max <b>${formatDuration(summary?.max)}</b></span></div>`;
}

function renderResult(target, filters, stats) {
  const sentence = escapeHtml(buildAnswerSentence(filters, stats));
  if (!stats.count) {
    target.innerHTML = `<p class="pitmaster-answer">${sentence}</p>`;
    return;
  }
  const perPound = cookTimePerPound(stats.cooks);
  target.innerHTML = `<p class="pitmaster-answer">${sentence}</p>
    <p class="match-count">${stats.count} matching ${stats.count === 1 ? "cook" : "cooks"}</p>
    <div class="pitmaster-stats">
      ${summaryRow("Startup", stats.startup_seconds)}
      ${summaryRow("Cook", stats.cook_seconds)}
      ${summaryRow("Cool down", stats.cooldown_seconds)}
      ${summaryRow("Grill time", stats.grill_seconds)}
      <div class="pitmaster-stat per-pound"><strong>Cook time / lb</strong><span>Average <b>${formatDuration(perPound)}</b></span></div>
    </div>`;
}

function typeDisplayName(type, knownNames) {
  return knownNames.get(String(type).toLocaleLowerCase()) || type;
}

function renderManager(target, data, knownNames) {
  const groupOptions = data.groups.map((group) => [String(group.id), group.name]);
  const rows = data.groups.flatMap((group) => group.types.map((type) => ({ type, groupId: String(group.id) })))
    .concat(data.ungrouped_types.map((type) => ({ type, groupId: "" })))
    .sort((left, right) => typeDisplayName(left.type, knownNames).localeCompare(typeDisplayName(right.type, knownNames), undefined, { sensitivity: "base" }));
  const groups = data.groups.map((group) => `<article class="meat-group-card" data-group-id="${group.id}">
    <form class="rename-group"><label class="fl"><span class="lb">Group name</span><input class="ci" name="name" required value="${escapeHtml(group.name)}"></label><button class="cc" type="submit">Rename</button></form>
    <p class="mut">${group.types.length ? group.types.map((type) => escapeHtml(typeDisplayName(type, knownNames))).join(" · ") : "No meat types"}</p>
    <button class="cc delete-group" type="button">Delete group</button>
  </article>`).join("");
  target.innerHTML = `<div class="meat-group-list">${groups || '<p class="mut">No groups yet.</p>'}</div>
    <form class="create-group"><label class="fl"><span class="lb">New group name</span><input class="ci" name="name" required></label><button class="pbtn" type="submit">Create group</button></form>
    <h3>Meat types</h3>
    <div class="meat-type-groups">${rows.map((row) => `<label class="fl"><span class="lb">${escapeHtml(typeDisplayName(row.type, knownNames))}</span><select class="ci type-group" data-type="${escapeHtml(row.type)}" data-current-group="${row.groupId}">
      ${option("", "Ungrouped", row.groupId)}${groupOptions.map(([id, name]) => option(id, name, row.groupId)).join("")}
    </select></label>`).join("") || '<p class="mut">No meat types yet.</p>'}</div>
    <p class="group-message" role="status"></p>`;
}

export function mountPitmasterView(container) {
  let disposed = false;
  let groupData = { groups: [], ungrouped_types: [] };
  let statsMeatTypes = [];
  let meats = [];
  const filters = filtersFromHash(window.location.hash);
  const canonicalHash = filtersToHash(filters);
  if (window.location.hash !== canonicalHash) window.history.replaceState(null, "", canonicalHash);
  container.innerHTML = `<section class="board pitmaster-board">
    <h1 class="hd">Ask the Pitmaster</h1>
    <p class="mut">Tell me what's headed for the smoker.</p>
    <form class="pitmaster-form">
      <label class="fl"><span class="lb">Meat type or group</span><select class="ci" name="meat"><option value="">Any meat</option></select></label>
      <label class="fl"><span class="lb">Minimum pounds</span><input class="ci" name="pounds_min" type="number" min="0" step="0.1" inputmode="decimal" value="${escapeHtml(filters.poundsMin)}"></label>
      <label class="fl"><span class="lb">Maximum pounds</span><input class="ci" name="pounds_max" type="number" min="0" step="0.1" inputmode="decimal" value="${escapeHtml(filters.poundsMax)}"></label>
      <label class="fl"><span class="lb">Setpoint °F</span><input class="ci" name="setpoint" type="number" step="1" inputmode="numeric" value="${escapeHtml(filters.setpoint)}"></label>
      <label class="fl"><span class="lb">Plus or minus °F</span><input class="ci" name="tolerance" type="number" min="0" step="1" inputmode="numeric" value="${escapeHtml(filters.tolerance)}"></label>
      <label class="fl"><span class="lb">Rotisserie</span><select class="ci" name="rotisserie">${option("true", "Yes", filters.rotisserie)}${option("false", "No", filters.rotisserie)}</select></label>
      <label class="fl"><span class="lb">Pellets</span><select class="ci" name="pellet_id"><option value="">Any pellets</option></select></label>
      <div class="pitmaster-actions"><button class="pbtn" type="submit">Ask the pitmaster</button><a class="cc" href="${filtersToHash({})}">Clear filters</a><button class="cc manage-groups" type="button" aria-expanded="false">Manage groups</button></div>
      <p class="form-message" role="status"></p>
    </form>
    <section class="meat-groups-panel" hidden><h2>Manage meat groups</h2><div class="meat-groups-content"></div></section>
    <div class="pitmaster-result" aria-live="polite"><p class="mut">Consulting the cook log…</p></div>
  </section>`;
  const form = container.querySelector(".pitmaster-form");
  const result = container.querySelector(".pitmaster-result");
  const manager = container.querySelector(".meat-groups-content");
  const panel = container.querySelector(".meat-groups-panel");
  const manageButton = container.querySelector(".manage-groups");

  function knownNames() {
    const names = new Map();
    meats.forEach((item) => names.set(String(item.type).trim().toLocaleLowerCase(), String(item.type).trim()));
    statsMeatTypes.forEach((item) => names.set(String(item.meat_type).trim().toLocaleLowerCase(), String(item.meat_type).trim()));
    return names;
  }

  function fillMeatSelect() {
    const selected = meatValue(filters);
    const options = buildMeatOptions(groupData.groups, statsMeatTypes, meats, filters);
    form.elements.meat.innerHTML = `<option value="">Any meat</option>${options.map((item) => option(`${item.kind}:${item.value}`, item.label, selected)).join("")}`;
  }

  async function refreshGroups() {
    [groupData, statsMeatTypes, meats] = await Promise.all([getMeatGroups(), getCookStatsMeatTypes(), getMeat()]);
    if (disposed) return;
    fillMeatSelect();
    renderManager(manager, groupData, knownNames());
  }

  async function load() {
    try {
      const pellets = await getPellets();
      await refreshGroups();
      if (disposed) return;
      const pelletOptions = pellets.map((item) => [String(item.id), `${item.vendor} - ${item.product_name}`])
        .sort((left, right) => left[1].localeCompare(right[1], undefined, { sensitivity: "base" }));
      form.elements.pellet_id.insertAdjacentHTML("beforeend", pelletOptions.map(([value, label]) => option(value, label, filters.pelletId)).join(""));
      const selectedGroup = groupData.groups.find((group) => String(group.id) === filters.meatGroup);
      const stats = await getCookStats(statsQuery(filters));
      if (!disposed) renderResult(result, { ...filters, meatGroupName: selectedGroup?.name || "" }, stats);
    } catch (error) {
      if (disposed) return;
      console.error("Could not load cook-time statistics", error);
      result.innerHTML = "";
      renderApiError(form, error);
    }
  }

  async function changeGroups(action) {
    const message = manager.querySelector(".group-message");
    try {
      await action();
      await refreshGroups();
    } catch (error) {
      if (message) message.textContent = error.message;
    }
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    window.location.hash = filtersToHash(formValues(form));
  });
  manageButton.addEventListener("click", () => {
    panel.hidden = !panel.hidden;
    manageButton.setAttribute("aria-expanded", String(!panel.hidden));
  });
  manager.addEventListener("submit", (event) => {
    event.preventDefault();
    const data = new FormData(event.target);
    if (event.target.matches(".create-group")) changeGroups(() => createMeatGroup(String(data.get("name") || "")));
    if (event.target.matches(".rename-group")) {
      const groupId = event.target.closest("[data-group-id]").dataset.groupId;
      changeGroups(() => renameMeatGroup(groupId, String(data.get("name") || "")));
    }
  });
  manager.addEventListener("click", (event) => {
    const button = event.target.closest(".delete-group");
    if (!button) return;
    const card = button.closest("[data-group-id]");
    const group = groupData.groups.find((item) => String(item.id) === card.dataset.groupId);
    if (window.confirm(`Delete ${group.name}? Cooks and meat records are kept, and its types become ungrouped.`)) {
      changeGroups(() => deleteMeatGroup(group.id));
    }
  });
  manager.addEventListener("change", (event) => {
    const select = event.target.closest(".type-group");
    if (!select) return;
    const type = select.dataset.type;
    const oldGroup = groupData.groups.find((group) => String(group.id) === select.dataset.currentGroup);
    const newGroup = groupData.groups.find((group) => String(group.id) === select.value);
    if (newGroup) changeGroups(() => replaceMeatGroupTypes(newGroup.id, [...new Set([...newGroup.types, type])]));
    else if (oldGroup) changeGroups(() => replaceMeatGroupTypes(oldGroup.id, oldGroup.types.filter((item) => item !== type)));
  });
  load();
  return () => { disposed = true; };
}
