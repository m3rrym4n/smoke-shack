import { deleteCook, getCook, getCookEvents, getCookLogCooks, getCookPhotos, getCookSamples, getFuel, getMeat, getNotes, getPlannedCooks, getRecentCooks, getStatus, listSpices, updateCook, withBase } from "../api.js";
import { chartMarkup } from "../components/chart.js";
import { cookLogMarkup } from "../components/cook-log.js";
import { cookNotesMarkup } from "../components/cook-notes.js";
import { bindCookExport } from "../components/cook-export.js";
import { cookStatusBadgeMarkup } from "../cook-export-logic.js";
import { gaugeLogoMarkup, gaugeSvg } from "../components/gauge.js";
import { bindLiveForms, bindPhotoGallery, orderPadMarkup, photoGalleryMarkup, pinBoardMarkup } from "../components/live-forms.js";
import { clampPercent, orderPlannedCooks, phaseDurations, phasePercentages, selectOrderPadMode } from "../live-logic.js";
import { confirmDelete } from "../components/ui.js";
import { bindShowcase, showcaseMarkup } from "../components/showcase.js";
import { mountSmoke } from "../components/smoke.js";
import { smokeDemoMode } from "../smoke-logic.js";
import { spiceLabel } from "../spice-picker-logic.js";

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

function fuelLabel(item) {
  if (!item) return "Not selected";
  const type = item.type ? item.type[0].toUpperCase() + item.type.slice(1) : "Pellets";
  return `${item.vendor} ${item.product_name} (${type})`;
}

function channelReading(sample, key) {
  const channel = sample?.channels?.find((item) => item.key === key);
  if (channel) return channel;
  const number = /^probe(\d+)$/.exec(key)?.[1];
  if (!number) return { value: null, target: null };
  return {
    value: sample?.[`probe${number}`] ?? sample?.extra_probes?.[key],
    target: sample?.[`probe${number}_target`] ?? sample?.extra_probe_targets?.[key],
  };
}

export function probeBoard(name, probe, samples, cook, active) {
  if (!active) return `<section class="board probe-board unplugged"><h2 class="hd">${name}</h2><div class="sold-out"><b>×</b><span>sold out<br>(unplugged)</span></div></section>`;
  const latest = samples.at(-1);
  const channel = channelReading(latest, typeof probe === "string" ? probe : `probe${probe}`);
  const reading = channel.value;
  const currentTarget = Number(channel.target);
  const target = Number.isFinite(currentTarget) && currentTarget > 0 ? currentTarget : null;
  const connected = reading !== null && reading !== undefined;
  if (!connected) return `<section class="board probe-board unplugged"><h2 class="hd">${name}</h2><div class="sold-out"><b>×</b><span>sold out<br>(unplugged)</span></div></section>`;
  const percent = clampPercent(reading, target);
  const progress = target === null ? "" : `<div class="probe-progress" role="progressbar" aria-valuenow="${Math.round(percent)}" aria-valuemin="0" aria-valuemax="100"><span style="width:${percent}%"></span></div>
    <div class="mut">${Math.round(percent)}% of the way to done</div>`;
  return `<section class="board probe-board">
    <div class="probe-heading"><h2 class="hd">${name}</h2><span class="connected">plugged in</span></div>
    <div class="probe-temp">${temp(reading)}</div>
    <div class="probe-target">${target == null ? "no target set" : `aiming for ${temp(target)}`}</div>
    ${progress}
  </section>`;
}

export function probeCards(channels, samples, cook, active) {
  return channels
    .filter((channel) => channel.role === "meat")
    .map((channel) => probeBoard(escapeHtml(channel.label), channel.key, samples, cook, active))
    .join("");
}

function rubDetailMarkup(cook) {
  const rubs = cook?.spices || [];
  if (!rubs.length && !cook?.seasonings) return '<p class="cook-rubs"><b>Rubs:</b> —</p>';
  return `<div class="cook-rubs"><b>Rubs:</b><div>${rubs.map((spice) => `<span>${spice.photo_url ? `<img src="${escapeHtml(withBase(spice.photo_url))}" alt="">` : ""}${escapeHtml(spiceLabel(spice))}</span>`).join("")}${cook.seasonings ? `<span class="seasoning-note">${escapeHtml(cook.seasonings)}</span>` : ""}</div></div>`;
}

export function heroMarkup(cook, samples, active, historical, showcase, grillIdentity) {
  const sample = samples.at(-1);
  const times = phaseDurations(cook);
  const widths = phasePercentages(times);
  const setpoint = sample?.setpoint ?? cook.effective_setpoint ?? 0;
  const meat = cook.meat?.type || "Mystery smoke";
  const weight = cook.meat?.pounds ? `<span>${escapeHtml(cook.meat.pounds)} lb</span>` : "";
  const details = [setpoint ? `${temp(setpoint)} setpoint` : null, cook.pellet ? fuelLabel(cook.pellet) : null, cook.profile_name].filter(Boolean).map(escapeHtml).join(" · ");
  const channels = historical ? cook.channels || [] : grillIdentity?.channels || [];
  const probes = probeCards(channels, samples, cook, active);
  return `<div class="live-hero">
    <section class="board pit-board"><div class="board-title"><h1 class="hd">The Pit</h1><span class="cook-label">${active ? escapeHtml(cook.status) : "fire's out"}</span></div>${gaugeSvg(active ? sample?.pit_temp : 0, setpoint, showcase?.logo_url)}${showcaseMarkup(showcase, grillIdentity, window.innerWidth, !historical)}</section>
    <div class="live-details">
      <section class="board special-board"><div class="board-title"><h2 class="hd">${historical ? "Cook Special" : "Today's Special"}</h2><div class="cook-heading-badges">${historical ? cookStatusBadgeMarkup(cook) : ""}${active ? "" : `<span class="cook-label">${historical ? "cook #" + cook.id : "last cook"}</span>`}</div></div>
        <div class="meat-name">${escapeHtml(meat)} ${weight}</div><p class="mut special-meta">${details || "Cook details not set"}</p>
        <div class="phase-bar" aria-label="Cook phase progress"><span class="startup" style="width:${widths.startup}%"></span><span class="cooking" style="width:${widths.cook}%"></span><span class="cooldown" style="width:${widths.cooldown}%"></span></div>
        <div class="phase-list">${leader("Startup", duration(times.startup), active && cook.status === "startup")}${leader("Cook", duration(times.cook), active && cook.status === "cook")}${leader("Cool down", duration(times.cooldown), active && cook.status === "cooldown")}${leader("Total grill time", duration(times.total), false, true)}</div>
      </section>
      ${probes ? `<div class="probe-grid">${probes}</div>` : ""}
    </div>
  </div>`;
}

async function load(container, onStatus, isCurrent, requestedCookId, editing, refresh, setBusy, setShowcaseCleanup, updateSmoke) {
  let cookId = requestedCookId;
  let active = false;
  const status = await getStatus();
  if (!isCurrent()) return;
  if (cookId == null) {
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
    updateSmoke(null, null);
    container.innerHTML = `<section class="board live-empty"><h1 class="hd">The Pit</h1><p>The fire's out. No cooks on the board yet.</p></section>`;
    return;
  }
  const liveForms = requestedCookId == null;
  const requestedCook = requestedCookId == null ? null : await getCook(requestedCookId);
  if (requestedCook?.state === "planned" && !editing) {
    const cook = requestedCook;
    const notes = await getNotes("this_cook", cook.id);
    if (!isCurrent()) return;
    updateSmoke(null, null);
    container.innerHTML = `<div class="cook-detail"><div class="detail-actions"><a class="back-link cc" href="#cooks">← All cooks</a><a class="pbtn" href="#cooks/${cook.id}/edit">Edit</a></div><section class="order-pad planned-summary"><span class="tape" aria-hidden="true"></span><div class="order-heading"><h2>PLANNED ORDER</h2><span>No. ${String(cook.id).padStart(4, "0")}</span></div><p><b>Meat:</b> ${escapeHtml(cook.meat?.type || "Not selected")}</p><p><b>Fuel:</b> ${escapeHtml(fuelLabel(cook.pellet))}</p>${rubDetailMarkup(cook)}<p><b>Sauces:</b> ${escapeHtml(cook.sauces || "—")}</p><p><b>Prep time:</b> ${cook.prep_time_minutes ?? "—"}${cook.prep_time_minutes != null ? " minutes" : ""}</p><p><b>Rotisserie:</b> ${cook.rotisserie ? "Yes" : "No"}</p><p><b>How it turned out:</b> ${escapeHtml(cook.results_text || "—")}</p><div class="planned-detail-actions"><button class="paper-button planned-cancel" type="button">Cancel order</button><span class="plan-confirm" hidden></span></div></section></div>`;
    container.querySelector(".planned-summary").insertAdjacentHTML("beforebegin", cookNotesMarkup(notes));
    container.querySelector(".planned-cancel").addEventListener("click", () => confirmDelete(container.querySelector(".plan-confirm"), async () => { await deleteCook(cook.id); window.location.hash = "cooks"; }));
    return;
  }
  if (editing && requestedCook) {
    const [meat, availablePellets, cooks, photos, spices] = await Promise.all([
      getMeat(), getFuel(), getCookLogCooks(10000), getCookPhotos(requestedCook.id), listSpices(),
    ]);
    const pellets = requestedCook.pellet && !availablePellets.some((item) => item.id === requestedCook.pellet.id)
      ? [...availablePellets, requestedCook.pellet]
      : availablePellets;
    if (!isCurrent()) return;
    updateSmoke(null, null);
    const form = orderPadMarkup(requestedCook, meat, pellets, cooks, {
      mode: "history", banner: `Editing cook #${requestedCook.id}`, photos, spices,
    });
    container.innerHTML = `<div class="cook-detail"><a class="back-link cc" href="#cooks/${requestedCook.id}">← Back to cook</a>${form}</div>`;
    bindLiveForms(container, {
      cook: requestedCook, orderCook: requestedCook, events: [], meat, pellets, spices,
      refresh, setBusy, mode: "history",
      afterSave: (updated) => { window.location.hash = `cooks/${updated.id}`; },
    });
    return;
  }
  const [cook, samples, events, meat, pellets, closedCooks, planned, detailPhotos, showcase, notes, spices] = await Promise.all([
    requestedCook || (cookId ? getCook(cookId) : null), cookId ? getCookSamples(cookId) : [], cookId ? getCookEvents(cookId) : [],
    liveForms ? getMeat() : [], liveForms ? getFuel() : [], liveForms ? getRecentCooks(10000) : [], liveForms ? getPlannedCooks() : [],
    !liveForms && cookId ? getCookPhotos(cookId) : [],
    status,
    !liveForms && cookId ? getNotes("this_cook", cookId) : [],
    liveForms ? listSpices() : [],
  ]);
  if (!isCurrent()) return;
  const log = liveForms ? `<div class="log-pin-grid">${cookLogMarkup(events, true)}${pinBoardMarkup()}</div>` : cookLogMarkup(events, false);
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
    if (orderCook?.pellet && !pellets.some((item) => item.id === orderCook.pellet.id)) {
      pellets.push(orderCook.pellet);
    }
    const photos = orderCook?.id ? await getCookPhotos(orderCook.id) : [];
    order = orderPadMarkup(orderCook, meat, pellets, [...closedCooks, ...planned, ...(active && cook ? [cook] : [])], { ...selection, planned: sortedPlans, photos, spices });
  }
  const resultPhotos = !liveForms && cook ? `<section class="order-pad cook-results"><span class="tape" aria-hidden="true"></span>${rubDetailMarkup(cook)}<h2>How it turned out</h2><p>${escapeHtml(cook.results_text || "No write-up yet.")}</p>${photoGalleryMarkup(detailPhotos)}</section>` : "";
  const demo = requestedCookId == null && smokeDemoMode(window.location.hash);
  const demoPit = `<section class="board pit-board"><div class="board-title"><h1 class="hd">The Pit</h1><span class="cook-label">smoke demo</span></div>${gaugeSvg(null, 0, showcase?.logo_url)}${showcaseMarkup(showcase, status, window.innerWidth)}</section>`;
  const cookIsActive = cook?.ended_at == null;
  const cookContent = cook ? `${heroMarkup(cook, samples, cookIsActive, requestedCookId != null, showcase, status)}${cookNotesMarkup(notes)}${resultPhotos}${chartMarkup(samples, events, cook)}${log}` : demo ? demoPit : '<section class="board live-empty"><h1 class="hd">The Pit</h1><p>The fire’s out. Build the next order below.</p></section>';
  const liveDetail = requestedCookId != null && cook && cook.ended_at == null;
  const backLink = liveDetail
    ? '<a class="back-link cc" href="#live">← Back to live cook</a>'
    : '<a class="back-link cc" href="#cooks">← All cooks</a>';
  const detailActions = requestedCookId == null ? "" : `<div class="detail-actions">${backLink}<div class="detail-action-buttons"><label class="detail-stats-toggle"><input type="checkbox"${cook.exclude_from_stats ? " checked" : ""}> Exclude from stats (dry run / test)</label><span class="detail-stats-message" role="status"></span><button class="pbtn export-cook" type="button">Export PNG</button><a class="pbtn" href="#cooks/${cook.id}/edit">Edit</a></div><span class="export-message" role="status" aria-live="polite"></span></div>`;
  container.innerHTML = `<div class="cook-detail">${detailActions}${cookContent}${order}</div>`;
  const statsToggle = container.querySelector(".detail-stats-toggle input");
  statsToggle?.addEventListener("change", async () => {
    const message = container.querySelector(".detail-stats-message");
    statsToggle.disabled = true;
    try {
      await updateCook(cook.id, { exclude_from_stats: statsToggle.checked });
      message.textContent = "Saved";
    } catch (error) {
      statsToggle.checked = !statsToggle.checked;
      message.textContent = error.message || "Could not save";
    } finally {
      statsToggle.disabled = false;
    }
  });
  setShowcaseCleanup(bindShowcase(container, {
    grillIdentity: status,
    setBusy,
    onLogoChange: (url) => {
      const logo = container.querySelector(".gauge-logo-slot");
      if (logo) logo.outerHTML = gaugeLogoMarkup(url);
    },
  }));
  updateSmoke(active ? cook : null, samples.at(-1));
  if (liveForms) bindLiveForms(container, { cook, orderCook, events, meat, pellets, spices, refresh, setBusy, mode });
  else if (cook) {
    bindPhotoGallery(container.querySelector(".cook-results"), { cookId: cook.id });
    bindCookExport(container.querySelector(".cook-detail"), cook, {
      notes, resultsText: cook.results_text, samples, events, photos: detailPhotos, showcase, grillIdentity: status,
    });
  }
}

export function mountCookView(container, { cookId = null, editing = false, onStatus = () => {} } = {}) {
  let timer;
  let disposed = false;
  let formBusy = false;
  let showcaseCleanup = () => {};
  const smoke = cookId == null ? mountSmoke(container) : { update() {}, cleanup() {} };
  const refresh = async () => {
    if (disposed || document.hidden || formBusy) return;
    try {
      showcaseCleanup();
      showcaseCleanup = () => {};
      await load(container, onStatus, () => !disposed, cookId, editing, refresh, (busy) => { formBusy = busy; }, (cleanup) => { showcaseCleanup = cleanup; }, smoke.update);
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
    showcaseCleanup();
    smoke.cleanup();
    window.clearInterval(timer);
    document.removeEventListener("visibilitychange", visibilityChanged);
  };
}

export function mountLiveView(container, onStatus) {
  return mountCookView(container, { onStatus });
}
