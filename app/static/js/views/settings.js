import { connectGrill, disconnectGrill, getGrills } from "../api.js";
import { renderGrills } from "../settings-logic.js";

export function mountSettingsView(container) {
  let disposed = false;
  let busy = false;
  let grills = [];
  const messages = {};
  container.innerHTML = `<section class="board settings-board">
    <div class="settings-heading">
      <div><h1 class="hd">Settings</h1><h2>Grills</h2></div>
      <button class="pbtn refresh-grills" type="button">Refresh</button>
    </div>
    <p class="settings-message" role="status">Loading grills…</p>
    <div class="grill-list"></div>
  </section>`;
  const list = container.querySelector(".grill-list");
  const pageMessage = container.querySelector(".settings-message");
  const refresh = container.querySelector(".refresh-grills");

  function showGrills() {
    list.innerHTML = renderGrills(grills, messages);
  }

  async function loadGrills() {
    if (busy) return;
    busy = true;
    pageMessage.textContent = "Loading grills…";
    try {
      grills = await getGrills();
      if (disposed) return;
      pageMessage.textContent = "";
      showGrills();
    } catch (error) {
      if (disposed) return;
      list.innerHTML = "";
      pageMessage.textContent = error.status === 503
        ? "Home Assistant is not reachable"
        : error.message;
    } finally {
      busy = false;
    }
  }

  refresh.addEventListener("click", loadGrills);
  list.addEventListener("click", async (event) => {
    const button = event.target.closest(".grill-control");
    if (!button || busy) return;
    const card = button.closest(".grill-card");
    const grillId = card.dataset.grillId;
    const action = button.dataset.action;
    busy = true;
    delete messages[grillId];
    showGrills();
    try {
      await (action === "connect" ? connectGrill(grillId) : disconnectGrill(grillId));
      if (disposed) return;
      busy = false;
      await loadGrills();
    } catch (error) {
      if (disposed) return;
      messages[grillId] = error.message;
      showGrills();
    } finally {
      busy = false;
    }
  });
  loadGrills();
  return () => { disposed = true; };
}
