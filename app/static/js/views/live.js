import { getCook, getCookSamples, getRecentCooks, getStatus } from "../api.js";
import { gaugeSvg } from "../components/gauge.js";
import { clampPercent, phaseDurations, phasePercentages } from "../live-logic.js";

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

function render(container, cook, sample, active) {
  const times = phaseDurations(cook);
  const widths = phasePercentages(times);
  const setpoint = sample?.setpoint ?? cook.effective_setpoint ?? 0;
  const meat = cook.meat?.type || "Mystery smoke";
  const weight = cook.meat?.pounds ? `<span>${escapeHtml(cook.meat.pounds)} lb</span>` : "";
  const details = [setpoint ? `${temp(setpoint)} setpoint` : null, cook.pellet ? `${cook.pellet.vendor} ${cook.pellet.product_name}` : null, cook.profile_name].filter(Boolean).map(escapeHtml).join(" · ");
  container.innerHTML = `<div class="live-hero">
    <section class="board pit-board"><div class="board-title"><h1 class="hd">The Pit</h1><span class="cook-label">${active ? escapeHtml(cook.status) : "fire's out"}</span></div>${gaugeSvg(sample?.pit_temp, setpoint)}</section>
    <div class="live-details">
      <section class="board special-board"><div class="board-title"><h2 class="hd">Today's Special</h2>${active ? "" : '<span class="cook-label">last cook</span>'}</div>
        <div class="meat-name">${escapeHtml(meat)} ${weight}</div><p class="mut special-meta">${details || "Cook details not set"}</p>
        <div class="phase-bar" aria-label="Cook phase progress"><span class="startup" style="width:${widths.startup}%"></span><span class="cooking" style="width:${widths.cook}%"></span><span class="cooldown" style="width:${widths.cooldown}%"></span></div>
        <div class="phase-list">${leader("Startup", duration(times.startup), active && cook.status === "startup")}${leader("Cook", duration(times.cook), active && cook.status === "cook")}${leader("Cool down", duration(times.cooldown), active && cook.status === "cooldown")}${leader("Total grill time", duration(times.total), false, true)}</div>
      </section>
      <div class="probe-grid">${probeBoard("Probe 1", sample?.probe1, sample?.probe1_target)}${probeBoard("Probe 2", sample?.probe2, sample?.probe2_target)}</div>
    </div>
  </div>`;
}

async function load(container, onStatus, isCurrent) {
  const status = await getStatus();
  if (!isCurrent()) return;
  const active = status.active_cook !== null;
  onStatus(active);
  let cookId = status.active_cook?.id;
  if (!cookId) {
    const recent = await getRecentCooks(1);
    if (!isCurrent()) return;
    cookId = recent[0]?.id;
  }
  if (!cookId) {
    container.innerHTML = `<section class="board live-empty"><h1 class="hd">The Pit</h1><p>The fire's out. No cooks on the board yet.</p></section>`;
    return;
  }
  const [cook, samples] = await Promise.all([getCook(cookId), getCookSamples(cookId)]);
  if (!isCurrent()) return;
  render(container, cook, samples.at(-1), active);
}

export function mountLiveView(container, onStatus) {
  let timer;
  let disposed = false;
  const refresh = async () => {
    if (disposed || document.hidden) return;
    try {
      await load(container, onStatus, () => !disposed);
    } catch (error) {
      console.error("Could not load live cook", error);
      if (!container.querySelector(".live-hero")) container.innerHTML = `<section class="board live-empty"><h1 class="hd">The Pit</h1><p>Could not load the cook board.</p></section>`;
    }
  };
  const visibilityChanged = () => { if (!document.hidden) refresh(); };
  container.innerHTML = `<section class="board live-empty"><h1 class="hd">The Pit</h1><p>Checking the smoker…</p></section>`;
  refresh();
  timer = window.setInterval(refresh, 5000);
  document.addEventListener("visibilitychange", visibilityChanged);
  return () => {
    disposed = true;
    window.clearInterval(timer);
    document.removeEventListener("visibilitychange", visibilityChanged);
  };
}
