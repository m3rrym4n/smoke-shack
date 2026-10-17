import { getPlannedCooks, getRecentCooks } from "../api.js";
import { orderPlannedCooks } from "../live-logic.js";

const PAGE_SIZE = 20;
const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (character) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
})[character]);

function duration(seconds) {
  if (seconds === null || seconds === undefined || !Number.isFinite(Number(seconds))) return "—";
  const value = Math.max(0, Number(seconds));
  const hours = Math.floor(value / 3600);
  const minutes = Math.floor((value % 3600) / 60);
  return hours ? `${hours}h ${minutes}m` : `${minutes}m`;
}

function cookDate(value) {
  if (!value) return "Next cook";
  return new Intl.DateTimeFormat(undefined, { year: "numeric", month: "short", day: "numeric" }).format(new Date(value));
}

function row(cook) {
  const meat = cook.meat?.type || "Cook details not set";
  const setpoint = cook.effective_setpoint !== null && cook.effective_setpoint !== undefined && Number.isFinite(Number(cook.effective_setpoint)) ? `${Math.round(cook.effective_setpoint)}°` : "—";
  const planned = cook.state === "planned";
  return `<a class="cook-row${planned ? " planned" : ""}" href="#cooks/${cook.id}"><div><span class="cook-date">${cookDate(cook.started_at)}</span><strong>${escapeHtml(meat)}</strong>${planned ? '<span class="planned-tag">Planned</span>' : ""}${cook.incomplete ? '<span class="incomplete">incomplete</span>' : ""}</div><span>${planned ? "—" : setpoint}</span><span>${planned ? "—" : duration(cook.grill_duration_seconds)}</span><span class="cook-arrow" aria-hidden="true">›</span></a>`;
}

export function mountCookList(container) {
  let disposed = false;
  let offset = 0;
  let loading = false;
  container.innerHTML = `<section class="board cooks-board"><h1 class="hd">Cook Log</h1><div class="cook-columns mut"><span>Date &amp; meat</span><span>Setpoint</span><span>Total time</span><span></span></div><div id="cook-rows"></div><button class="cc load-more" type="button">Load more</button><p class="mut cooks-message" role="status"></p></section>`;
  const rows = container.querySelector("#cook-rows");
  const button = container.querySelector(".load-more");
  const message = container.querySelector(".cooks-message");
  const load = async () => {
    if (disposed || loading) return;
    loading = true;
    button.disabled = true;
    message.textContent = offset ? "Loading more cooks…" : "Loading cooks…";
    try {
      const [plans, cooks] = await Promise.all([offset === 0 ? getPlannedCooks() : [], getRecentCooks(PAGE_SIZE, offset)]);
      if (disposed) return;
      rows.insertAdjacentHTML("beforeend", [...orderPlannedCooks(plans), ...cooks].map(row).join(""));
      offset += cooks.length;
      button.hidden = cooks.length < PAGE_SIZE;
      message.textContent = offset || plans.length ? (cooks.length ? "" : "That’s every cook in the book.") : "No cooks in the book yet.";
    } catch (error) {
      console.error("Could not load cooks", error);
      message.textContent = "Could not load the cook log.";
    } finally {
      loading = false;
      if (!disposed) button.disabled = false;
    }
  };
  button.addEventListener("click", load);
  load();
  return () => { disposed = true; };
}
