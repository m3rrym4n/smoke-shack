import { getCookLogCooks } from "../api.js";
import { cookTag, elapsedSeconds, formatDuration, isLiveCook, orderCookLogRows } from "../cooks-logic.js";
import { seasoningText } from "../spice-picker-logic.js";

const PAGE_SIZE = 20;
const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (character) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
})[character]);

function cookDate(value) {
  if (!value) return "Next cook";
  return new Intl.DateTimeFormat(undefined, { year: "numeric", month: "short", day: "numeric" }).format(new Date(value));
}

function row(cook, now) {
  const meat = cook.meat?.type || "Cook details not set";
  const setpointValue = isLiveCook(cook) ? cook.current_setpoint : cook.effective_setpoint;
  const setpoint = setpointValue !== null && setpointValue !== undefined && Number.isFinite(Number(setpointValue)) ? `${Math.round(setpointValue)}°` : "—";
  const planned = cook.state === "planned";
  const tag = cookTag(cook);
  const tagMarkup = tag ? `<span class="cook-tag ${tag === "Test" ? "test-tag" : planned ? "planned-tag" : tag === "Incomplete" ? "incomplete" : "progress-tag"}">${tag}</span>` : "";
  const seconds = isLiveCook(cook) ? elapsedSeconds(cook, now) : cook.grill_duration_seconds;
  const rubs = seasoningText(cook);
  return `<a class="cook-row${planned ? " planned" : ""}" href="#cooks/${cook.id}"><div><span class="cook-date">${cookDate(cook.started_at)}</span><strong>${escapeHtml(meat)}</strong>${rubs ? `<small class="cook-row-rubs">${escapeHtml(rubs)}</small>` : ""}${tagMarkup}</div><span>${planned ? "—" : setpoint}</span><span>${planned ? "—" : formatDuration(seconds)}</span><span class="cook-arrow" aria-hidden="true">›</span></a>`;
}

export function mountCookList(container) {
  let disposed = false;
  let requestedClosed = PAGE_SIZE;
  let loading = false;
  container.innerHTML = `<section class="board cooks-board"><h1 class="hd">Cook Log</h1><div class="cook-columns mut"><span>Date &amp; meat</span><span>Setpoint</span><span>Total time</span><span></span></div><div id="cook-rows"></div><button class="cc load-more" type="button">Load more</button><p class="mut cooks-message" role="status"></p></section>`;
  const rows = container.querySelector("#cook-rows");
  const button = container.querySelector(".load-more");
  const message = container.querySelector(".cooks-message");
  const load = async (append = false) => {
    if (disposed || loading) return;
    loading = true;
    button.disabled = true;
    message.textContent = append ? "Loading more cooks…" : "Loading cooks…";
    try {
      if (append) requestedClosed += PAGE_SIZE;
      const allCooks = await getCookLogCooks(requestedClosed);
      if (disposed) return;
      const closedCount = allCooks.filter((cook) => cook.state !== "planned" && !isLiveCook(cook)).length;
      const now = new Date();
      rows.innerHTML = orderCookLogRows(allCooks).map((cook) => row(cook, now)).join("");
      button.hidden = closedCount < requestedClosed;
      message.textContent = allCooks.length ? "" : "No cooks in the book yet.";
    } catch (error) {
      console.error("Could not load cooks", error);
      message.textContent = "Could not load the cook log.";
    } finally {
      loading = false;
      if (!disposed) button.disabled = false;
    }
  };
  const loadMore = () => load(true);
  const visibilityChanged = () => { if (!document.hidden) load(); };
  button.addEventListener("click", loadMore);
  document.addEventListener("visibilitychange", visibilityChanged);
  load();
  const timer = window.setInterval(load, 30000);
  return () => {
    disposed = true;
    window.clearInterval(timer);
    button.removeEventListener("click", loadMore);
    document.removeEventListener("visibilitychange", visibilityChanged);
  };
}
