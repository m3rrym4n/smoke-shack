import { deleteCook, getCook, getCookEvents, getCookPhotos, getCookSamples, getMeat, getPellets, getPlannedCooks, getRecentCooks, getStatus } from "../api.js";
import { chartMarkup } from "../components/chart.js";
import { cookLogMarkup } from "../components/cook-log.js";
import { gaugeSvg } from "../components/gauge.js";
import { bindLiveForms, orderPadMarkup, pinBoardMarkup } from "../components/live-forms.js";
import { clampPercent, orderPlannedCooks, phaseDurations, phasePercentages, selectOrderPadMode } from "../live-logic.js";
import { confirmDelete } from "../components/ui.js";

const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (character) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
})[character]);

function temp(value) {
  return Number.isFinite(Number(value)) ? `${Math.round(Number(value))}°` : "—";
}

function duration(seconds) {
  if (!Number.isFinite(seconds) || seconds < 0) return "—";
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  return hours ? `${hours}h ${minutes}m` : `${minutes}m`;
}

function leader(label, value, active = false, total = false) {
  return `<div class="ld phase-row ${active ? "active" : ""} ${total ? "total" : ""}"><span>${label}</span><i></i><strong>${value}</strong></div>`;
}

function probeBoard(name, reading, target) {
  const connected = reading !== null && reading !== undefined;
  if (!connected) return `<section class="board probe-board unplugged"><h2 class="hd">${name}</h2><div class="sold-out"><b>×</b><span>sold out<br>(unplugged)</span></div></section>`;
  const percent = clampPercent(reading, target);
  return `<section class="board probe-board">
    <div class="probe-heading"><h2 class="hd">${name}</h2><span class="connected">plugged in</span></div>
    <div class="probe-temp">${temp(reading)}</div>
    <div class="probe-target">${target == null ? "no target set" : `aiming for ${temp(target)}`}</div>
    <div class="probe-progress" role="progressbar" aria-valuenow="${Math.round(percent)}" aria-valuemin="0" aria-valuemax="100"><span style="width:${percent}%"></span></div>
    <div class="mut">${target == null ? "Set a probe target on the grill" : `${Math.round(percent)}% of the way to done`}</div>
  </section>`;
}

function heroMarkup(cook, sample, active, historical) {
  const times = phaseDurations(cook);
  const widths = phasePercentages(times);
  const setpoint = sample?.setpoint ?? cook.effective_setpoint ?? 0;
  const meat = cook.meat?.type || "Mystery smoke";
  const weight = cook.meat?.pounds ? `<span>${escapeHtml(cook.meat.pounds)} lb</span>` : "";
  const details = [setpoint ? `${temp(setpoint)} setpoint` : null, cook.pellet ? `${cook.pellet.vendor} ${cook.pellet.product_name}` : null, cook.profile_name].filter(Boolean).map(escapeHtml).join(" · ");
  return `<div class="live-hero">
    <section class="board pit-board"><div class="board-title"><h1 class="hd">The Pit</h1><span class="cook-label">${active ? escapeHtml(cook.status) : "fire's out"}</span></div>${gaugeSvg(sample?.pit_temp, setpoint)}</section>
    <div class="live-details">
      <section class="board special-board"><div class="board-title"><h2 class="hd">${historical ? "Cook Special" : "Today's Special"}</h2>${active ? "" : `<span class="cook-label">${historical ? "cook #" + cook.id : "last cook"}</span>`}</div>
        <div class="meat-name">${escapeHtml(meat)} ${weight}</div><p class="mut special-meta">${details || "Cook details not set"}</p>
        <div class="phase-bar" aria-label="Cook phase progress"><span class="startup" style="width:${widths.startup}%"></span><span class="cooking" style="width:${widths.cook}%"></span><span class="cooldown" style="width:${widths.cooldown}%"></span></div>
        <div class="phase-list">${leader("Startup", duration(times.startup), active && cook.status === "startup")}${leader("Cook", duration(times.cook), active && cook.status === "cook")}${leader("Cool down", duration(times.cooldown), active && cook.status === "cooldown")}${leader("Total grill time", duration(times.total), false, true)}</div>
      </section>
      <div class="probe-grid">${probeBoard("Probe 1", sample?.probe1, sample?.probe1_target)}${probeBoard("Probe 2", sample?.probe2, sample?.probe2_target)}</div>
    </div>
  </div>`;
}

async function load(container, onStatus, isCurrent, requestedCookId, refresh, setBusy) {
  let cookId = requestedCookId;
  let active = false;
  if (cookId == null) {
    const status = await getStatus();
    if (!isCurrent()) return;
    active = status.active_cook !== null;
    onStatus(active);
    cookId = status.active_cook?.id;
  }
  if (cookId == null) {
    const recent = await getRecentCooks(1);
    if (!isCurrent()) return;
    cookId = recent[0]?.id;
  }
  if (!cookId && requestedCookId != null) {
    container.innerHTML = `<section class="board live-empty"><h1 class="hd">The Pit</h1><p>The fire's out. No cooks on the board yet.</p></section>`;
    return;
  }
  const liveForms = requestedCookId == null;
  const requestedCook = requestedCookId == null ? null : await getCook(requestedCookId);
  if (requestedCook?.state === "planned") {
    const cook = requestedCook;
    container.innerHTML = `<div class="cook-detail"><a class="back-link cc" href="#cooks">← All cooks</a><section class="order-pad planned-summary"><span class="tape" aria-hidden="true"></span><div class="order-heading"><h2>PLANNED ORDER</h2><span>No. ${String(cook.id).padStart(4, "0")}</span></div><p><b>Meat:</b> ${escapeHtml(cook.meat?.type || "Not selected")}</p><p><b>Pellets:</b> ${escapeHtml(cook.pellet ? `${cook.pellet.vendor} ${cook.pellet.product_name}` : "Not selected")}</p><p><b>Seasonings:</b> ${escapeHtml(cook.seasonings || "—")}</p><p><b>Sauces:</b> ${escapeHtml(cook.sauces || "—")}</p><p><b>Prep time:</b> ${cook.prep_time_minutes ?? "—"}${cook.prep_time_minutes != null ? " minutes" : ""}</p><p><b>Rotisserie:</b> ${cook.rotisserie ? "Yes" : "No"}</p><p><b>How it turned out:</b> ${escapeHtml(cook.results_text || "—")}</p><div class="planned-detail-actions"><a class="paper-button" href="#live?order=${cook.id}">Edit in Order Pad</a><button class="paper-button planned-cancel" type="button">Cancel order</button><span class="plan-confirm" hidden></span></div></section></div>`;
    container.querySelector(".planned-cancel").addEventListener("click", () => confirmDelete(container.querySelector(".plan-confirm"), async () => { await deleteCook(cook.id); window.location.hash = "cooks"; }));
    return;
  }
  const [cook, samples, events, meat, pellets, closedCooks, planned] = await Promise.all([
    requestedCook || (cookId ? getCook(cookId) : null), cookId ? getCookSamples(cookId) : [], cookId ? getCookEvents(cookId) : [],
    liveForms ? getMeat() : [], liveForms ? getPellets() : [], liveForms ? getRecentCooks(10000) : [], liveForms ? getPlannedCooks() : [],
  ]);
  if (!isCurrent()) return;
  const log = liveForms ? `<div class="log-pin-grid">${cookLogMarkup(events, true)}${pinBoardMarkup()}</div>` : cookLogMarkup(events);
  let order = "";
  let orderCook = cook;
  let mode;
  if (liveForms) {
    const params = new URLSearchParams(window.location.hash.split("?")[1] || "");
    const sortedPlans = orderPlannedCooks(planned);
    const selectedPlan = sortedPlans.find((item) => item.id === Number(params.get("order")));
    const forceNew = params.get("new") === "1";
    const closed = params.get("closed") === "1" ? closedCooks[0] || null : null;
    const selection = forceNew
      ? selectOrderPadMode(null, [])
      : selectedPlan
        ? { mode: "planned", cook: selectedPlan, banner: "Next order, will be used when the grill starts" }
        : selectOrderPadMode(active ? cook : null, sortedPlans, closed);
    mode = selection.mode;
    orderCook = selection.cook;
    const photos = orderCook?.id ? await getCookPhotos(orderCook.id) : [];
    order = orderPadMarkup(orderCook, meat, pellets, [...closedCooks, ...planned, ...(active && cook ? [cook] : [])], { ...selection, planned: sortedPlans, photos });
  }
  const cookContent = cook ? `${heroMarkup(cook, samples.at(-1), active, requestedCookId != null)}${chartMarkup(samples, events, cook)}${log}` : '<section class="board live-empty"><h1 class="hd">The Pit</h1><p>The fire’s out. Build the next order below.</p></section>';
  const liveDetail = requestedCookId != null && cook && cook.ended_at == null;
  const backLink = liveDetail
    ? '<a class="back-link cc" href="#live">← Back to live cook</a>'
    : '<a class="back-link cc" href="#cooks">← All cooks</a>';
  container.innerHTML = `<div class="cook-detail">${requestedCookId == null ? "" : backLink}${cookContent}${order}</div>`;
  if (liveForms) bindLiveForms(container, { cook, orderCook, events, meat, pellets, refresh, setBusy, mode });
}

export function mountCookView(container, { cookId = null, onStatus = () => {} } = {}) {
  let timer;
  let disposed = false;
  let formBusy = false;
  const refresh = async () => {
    if (disposed || document.hidden || formBusy) return;
    try {
      await load(container, onStatus, () => !disposed, cookId, refresh, (busy) => { formBusy = busy; });
    } catch (error) {
      console.error("Could not load live cook", error);
      if (!container.querySelector(".live-hero")) container.innerHTML = `<section class="board live-empty"><h1 class="hd">The Pit</h1><p>Could not load the cook board.</p></section>`;
    }
  };
  const visibilityChanged = () => { if (!document.hidden) refresh(); };
  container.innerHTML = `<section class="board live-empty"><h1 class="hd">The Pit</h1><p>Checking the smoker…</p></section>`;
  refresh();
  if (cookId == null) timer = window.setInterval(refresh, 5000);
  document.addEventListener("visibilitychange", visibilityChanged);
  return () => {
    disposed = true;
    window.clearInterval(timer);
    document.removeEventListener("visibilitychange", visibilityChanged);
  };
}

export function mountLiveView(container, onStatus) {
  return mountCookView(container, { onStatus });
}
