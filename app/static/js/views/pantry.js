import { mountMeatView } from "./meat.js";
import { mountPelletsView } from "./pellets.js";
import { mountSpicesView } from "./spices.js";

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
  return mountSpicesView(pantryView);
}
