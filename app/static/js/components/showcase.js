import { withBase } from "../api.js";
import { readStackPosition as readStackPositionValue, showcaseLayoutClass, showcaseNameLines } from "../live-logic.js";

const STACK_POSITION_KEY = "smoke-stack.showcase.stack-position";
const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (character) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
})[character]);

export function readStackPosition(storage = window.localStorage) {
  return readStackPositionValue(storage, STACK_POSITION_KEY);
}

function photoMarkup(url, position) {
  if (!url) return '<div class="showcase-photo"></div>';
  return `<div class="showcase-photo"><img src="${escapeHtml(withBase(url))}" alt="Grill"><span class="photo-stack-anchor" data-smokestack style="left:${position.x}%;top:${position.y}%" aria-hidden="true"></span></div>`;
}

export function showcaseMarkup(showcase, grillIdentity, width = window.innerWidth, smokeControl = true) {
  return `<div class="pit-showcase ${showcaseLayoutClass(width)}">
    <div class="showcase-name"><span class="showcase-title"></span><span class="showcase-maker" hidden></span></div>
    ${photoMarkup(showcase?.photo_url, readStackPosition())}
    <div class="showcase-controls">${smokeControl ? '<button class="smoke-toggle cc" type="button" aria-pressed="true">Smoke</button>' : ""}</div>
  </div>`;
}

export function bindShowcase(container, { grillIdentity = {} }) {
  const strip = container.querySelector(".pit-showcase");
  if (!strip) return () => {};
  const name = showcaseNameLines(grillIdentity);
  const title = strip.querySelector(".showcase-title");
  const maker = strip.querySelector(".showcase-maker");
  title.textContent = name.title;
  title.title = name.title;
  maker.textContent = name.maker ? `by ${name.maker}` : "";
  maker.hidden = !name.maker;
  const resize = () => {
    strip.classList.remove("showcase-mobile", "showcase-wide");
    strip.classList.add(showcaseLayoutClass(window.innerWidth));
  };
  window.addEventListener("resize", resize);
  return () => window.removeEventListener("resize", resize);
}
