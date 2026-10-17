import { getStatus } from "./api.js";

const routes = new Set(["live", "cooks", "profiles", "pellets", "meat", "notes", "pitmaster"]);
const view = document.querySelector("#view");
const neon = document.querySelector("#now-smoking");

function currentRoute() {
  const route = window.location.hash.slice(1);
  return routes.has(route) ? route : "live";
}

function renderRoute() {
  const route = currentRoute();
  document.querySelectorAll(".nav a").forEach((link) => {
    link.classList.toggle("on", link.hash === `#${route}`);
  });
  view.innerHTML = `
    <section class="board coming-soon">
      <h1 class="hd">Coming soon</h1>
      <p>This part of the pit is still warming up.</p>
    </section>`;
}

async function updateCookSign() {
  try {
    const status = await getStatus();
    neon.hidden = status.active_cook === null;
  } catch (error) {
    neon.hidden = true;
    console.error("Could not load grill status", error);
  }
}

window.addEventListener("hashchange", renderRoute);
renderRoute();
updateCookSign();
window.setInterval(updateCookSign, 5000);
