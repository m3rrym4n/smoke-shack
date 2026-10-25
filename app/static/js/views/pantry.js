import { mountMeatView } from "./meat.js";
import { mountPelletsView } from "./pellets.js";

export function mountPantryView(container, tab) {
  container.innerHTML = `<section class="pantry-shell">
    <nav class="pantry-nav" aria-label="Pantry navigation">
      <a class="pbtn" href="#pantry/pellets">Pellets</a>
      <a class="pbtn" href="#pantry/meat">Meat</a>
      <a class="pbtn" href="#pantry/spices">Spices</a>
    </nav>
    <div class="pantry-view"></div>
  </section>`;
  container.querySelectorAll(".pantry-nav a").forEach((link) => {
    link.classList.toggle("on", link.hash === `#pantry/${tab}`);
  });
  const pantryView = container.querySelector(".pantry-view");
  if (tab === "pellets") return mountPelletsView(pantryView);
  if (tab === "meat") return mountMeatView(pantryView);
  pantryView.innerHTML = `<section class="board coming-soon">
    <h1 class="hd">Spices</h1>
    <p>Spice rack coming next</p>
  </section>`;
  return () => {};
}
