import { getCookStats, getCookStatsMeatTypes, getMeat, getPellets } from "../api.js";
import { renderApiError } from "../components/ui.js";
import {
  buildAnswerSentence, cookTimePerPound, filtersFromHash, filtersToHash, mergeMeatTypeOptions,
  formatDuration, statsQuery,
} from "../pitmaster-logic.js";

const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (character) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
})[character]);

const option = (value, label, selected) => `<option value="${escapeHtml(value)}"${value === selected ? " selected" : ""}>${escapeHtml(label)}</option>`;

function formValues(form) {
  const data = new FormData(form);
  return {
    meat: String(data.get("meat") || ""), poundsMin: String(data.get("pounds_min") || ""),
    poundsMax: String(data.get("pounds_max") || ""), setpoint: String(data.get("setpoint") || ""),
    tolerance: String(data.get("tolerance") || "10"), rotisserie: String(data.get("rotisserie") || "false"),
    pelletId: String(data.get("pellet_id") || ""),
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

export function mountPitmasterView(container) {
  let disposed = false;
  const filters = filtersFromHash(window.location.hash);
  const canonicalHash = filtersToHash(filters);
  if (window.location.hash !== canonicalHash) window.history.replaceState(null, "", canonicalHash);
  container.innerHTML = `<section class="board pitmaster-board">
    <h1 class="hd">Ask the Pitmaster</h1>
    <p class="mut">Tell me what's headed for the smoker.</p>
    <form class="pitmaster-form">
      <label class="fl"><span class="lb">Meat type</span><select class="ci" name="meat"><option value="">Any meat</option></select></label>
      <label class="fl"><span class="lb">Minimum pounds</span><input class="ci" name="pounds_min" type="number" min="0" step="0.1" inputmode="decimal" value="${escapeHtml(filters.poundsMin)}"></label>
      <label class="fl"><span class="lb">Maximum pounds</span><input class="ci" name="pounds_max" type="number" min="0" step="0.1" inputmode="decimal" value="${escapeHtml(filters.poundsMax)}"></label>
      <label class="fl"><span class="lb">Setpoint °F</span><input class="ci" name="setpoint" type="number" step="1" inputmode="numeric" value="${escapeHtml(filters.setpoint)}"></label>
      <label class="fl"><span class="lb">Plus or minus °F</span><input class="ci" name="tolerance" type="number" min="0" step="1" inputmode="numeric" value="${escapeHtml(filters.tolerance)}"></label>
      <label class="fl"><span class="lb">Rotisserie</span><select class="ci" name="rotisserie">${option("true", "Yes", filters.rotisserie)}${option("false", "No", filters.rotisserie)}</select></label>
      <label class="fl"><span class="lb">Pellets</span><select class="ci" name="pellet_id"><option value="">Any pellets</option></select></label>
      <div class="pitmaster-actions"><button class="pbtn" type="submit">Ask the pitmaster</button><a class="cc" href="${filtersToHash({})}">Clear filters</a></div>
      <p class="form-message" role="status"></p>
    </form>
    <div class="pitmaster-result" aria-live="polite"><p class="mut">Consulting the cook log…</p></div>
  </section>`;
  const form = container.querySelector(".pitmaster-form");
  const result = container.querySelector(".pitmaster-result");

  function fillSelect(name, items, selected) {
    const select = form.elements[name];
    select.insertAdjacentHTML("beforeend", items.map(([value, label]) => option(value, label, selected)).join(""));
  }

  async function load() {
    try {
      const [meatTypes, pellets, meat] = await Promise.all([getCookStatsMeatTypes(), getPellets(), getMeat()]);
      if (disposed) return;
      const meatOptions = mergeMeatTypeOptions(meatTypes, meat, filters.meat);
      fillSelect("meat", meatOptions.map((item) => [item.value, item.label]), filters.meat);
      const pelletOptions = pellets
        .map((item) => [String(item.id), `${item.vendor} - ${item.product_name}`])
        .sort((left, right) => left[1].localeCompare(right[1], undefined, { sensitivity: "base" }));
      fillSelect("pellet_id", pelletOptions, filters.pelletId);
      const stats = await getCookStats(statsQuery(filters));
      if (!disposed) renderResult(result, filters, stats);
    } catch (error) {
      if (disposed) return;
      console.error("Could not load cook-time statistics", error);
      result.innerHTML = "";
      renderApiError(form, error);
    }
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    window.location.hash = filtersToHash(formValues(form));
  });
  load();
  return () => { disposed = true; };
}
