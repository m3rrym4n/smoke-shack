import { getStatus } from "./api.js";
import { mountCookList } from "./views/cooks.js";
import { mountCookView, mountLiveView } from "./views/live.js";
import { mountMeatView } from "./views/meat.js";
import { mountNotesView } from "./views/notes.js";
import { mountPelletsView } from "./views/pellets.js";
import { mountPitmasterView } from "./views/pitmaster.js";

const routes = new Set(["live", "cooks", "profiles", "pellets", "meat", "notes", "pitmaster"]);
const view = document.querySelector("#view");
const neon = document.querySelector("#now-smoking");
const buildVersion = document.querySelector("#build-version");
let disposeView = () => {};

function currentRoute() {
  const value = window.location.hash.slice(1);
  const cookMatch = value.match(/^cooks\/(\d+)$/);
  if (cookMatch) return { name: "cook-detail", cookId: Number(cookMatch[1]), nav: "cooks" };
  const name = value.split("?", 1)[0];
  if (!routes.has(name)) return { name: "live", nav: "live" };
  return { name, nav: name };
}

function renderRoute() {
  disposeView();
  disposeView = () => {};
  const route = currentRoute();
  document.querySelectorAll(".nav a").forEach((link) => {
    link.classList.toggle("on", link.hash === `#${route.nav}`);
  });
  if (route.name === "live") {
    disposeView = mountLiveView(view, (active) => {
      neon.hidden = !active;
    });
    return;
  }
  if (route.name === "cooks") {
    disposeView = mountCookList(view);
    return;
  }
  if (route.name === "cook-detail") {
    disposeView = mountCookView(view, { cookId: route.cookId });
    return;
  }
  if (route.name === "meat") {
    disposeView = mountMeatView(view);
    return;
  }
  if (route.name === "pellets") {
    disposeView = mountPelletsView(view);
    return;
  }
  if (route.name === "notes") {
    disposeView = mountNotesView(view);
    return;
  }
  if (route.name === "pitmaster") {
    disposeView = mountPitmasterView(view);
    return;
  }
  view.innerHTML = `
    <section class="board coming-soon">
      <h1 class="hd">Coming soon</h1>
      <p>This part of the pit is still warming up.</p>
    </section>`;
}

async function updateCookSign() {
  if (document.hidden || currentRoute().name === "live") return;
  try {
    const status = await getStatus();
    neon.hidden = status.active_cook === null;
  } catch (error) {
    neon.hidden = true;
    console.error("Could not load grill status", error);
  }
}

async function updateBuildVersion() {
  try {
    const status = await getStatus();
    buildVersion.textContent = status.version;
  } catch (error) {
    console.error("Could not load build version", error);
  }
}

window.addEventListener("hashchange", renderRoute);
document.addEventListener("visibilitychange", updateCookSign);
renderRoute();
updateCookSign();
updateBuildVersion();
window.setInterval(updateCookSign, 5000);
