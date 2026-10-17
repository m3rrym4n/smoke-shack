import { deleteShowcaseImage, uploadShowcaseImage } from "../api.js";
import { clampStackPosition, showcaseLayoutClass, showcasePlaceholder, validateShowcaseFile } from "../live-logic.js";

const STACK_POSITION_KEY = "smoke-stack.showcase.stack-position";

const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (character) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
})[character]);

export function readStackPosition(storage = window.localStorage) {
  try {
    const saved = JSON.parse(storage.getItem(STACK_POSITION_KEY));
    return { x: clampStackPosition(saved?.x, 50), y: clampStackPosition(saved?.y, 5) };
  } catch {
    return { x: 50, y: 5 };
  }
}

function grillIllustration() {
  return `<svg class="showcase-grill" viewBox="0 0 300 190" role="img" aria-label="Pellet grill illustration">
    <g fill="none" stroke="currentColor" stroke-width="9" stroke-linecap="round" stroke-linejoin="round">
      <path d="M58 71 Q58 35 96 35 H205 Q235 35 235 71 V112 H58 Z" fill="rgba(241,239,228,.08)"/>
      <path d="M74 112 58 166M216 112l18 54M45 166h30M219 166h31M235 83h27v42h-27M96 35v77"/>
      <path d="M194 35V10h19v25" data-smokestack/>
      <circle cx="238" cy="166" r="12"/><path d="M42 73h16"/>
    </g>
  </svg>`;
}

function photoMarkup(url, position) {
  if (showcasePlaceholder(url) === "placeholder") return `<div class="showcase-photo placeholder">${grillIllustration()}</div>`;
  return `<div class="showcase-photo"><span class="photo-tape" aria-hidden="true"></span><img src="${escapeHtml(url)}" alt="Grill"><span class="photo-stack-anchor" data-smokestack style="left:${position.x}%;top:${position.y}%" aria-hidden="true"></span></div>`;
}

export function showcaseMarkup(showcase, grillName, width = window.innerWidth) {
  const position = readStackPosition();
  const logo = showcasePlaceholder(showcase?.logo_url) === "image"
    ? `<img src="${escapeHtml(showcase.logo_url)}" alt="Grill logo">`
    : `<span>GREEN MOUNTAIN GRILLS</span>`;
  return `<div class="pit-showcase ${showcaseLayoutClass(width)}">
    <div class="showcase-logo">${logo}</div>
    <div class="showcase-name" title="${escapeHtml(grillName)}">${escapeHtml(grillName || "My grill")}</div>
    ${photoMarkup(showcase?.photo_url, position)}
    <button class="change-pictures" type="button" aria-expanded="false">Change pictures</button>
    <div class="showcase-editor" hidden>
      ${editorRow("logo", "Logo", showcase?.logo_url)}
      ${editorRow("photo", "Grill photo", showcase?.photo_url)}
      <fieldset class="stack-position" ${showcase?.photo_url ? "" : "hidden"}><legend>Smoke position on photo</legend>
        <label>Horizontal <input name="stack-x" type="range" min="0" max="100" value="${position.x}"><output>${position.x}%</output></label>
        <label>Vertical <input name="stack-y" type="range" min="0" max="100" value="${position.y}"><output>${position.y}%</output></label>
      </fieldset>
      <p class="showcase-message" role="status"></p>
    </div>
  </div>`;
}

function editorRow(kind, label, imageUrl) {
  const preview = imageUrl
    ? `<img src="${escapeHtml(imageUrl)}" alt="Current ${label.toLowerCase()}">`
    : `<span>No ${label.toLowerCase()} uploaded</span>`;
  return `<div class="showcase-image-field" data-image-kind="${kind}"><label><span>${label}</span><input type="file" accept="image/png,image/jpeg,image/webp"></label><div class="showcase-preview">${preview}</div><div class="showcase-image-actions"><button class="cc save-showcase" type="button">Save</button><button class="cc remove-showcase" type="button" ${imageUrl ? "" : "disabled"}>Remove</button></div></div>`;
}

export function bindShowcase(container, { refresh, setBusy }) {
  const strip = container.querySelector(".pit-showcase");
  if (!strip) return () => {};
  const editor = strip.querySelector(".showcase-editor");
  const toggle = strip.querySelector(".change-pictures");
  const message = strip.querySelector(".showcase-message");
  const objectUrls = new Set();
  const showMessage = (text, error = false) => { message.textContent = text; message.classList.toggle("error", error); };
  const close = () => objectUrls.forEach((url) => URL.revokeObjectURL(url));

  toggle.addEventListener("click", () => {
    const opening = editor.hidden;
    editor.hidden = !opening;
    toggle.setAttribute("aria-expanded", String(opening));
    toggle.textContent = opening ? "Close picture editor" : "Change pictures";
    setBusy(opening);
  });
  strip.querySelectorAll(".showcase-image-field").forEach((field) => {
    const input = field.querySelector("input");
    const preview = field.querySelector(".showcase-preview");
    const kind = field.dataset.imageKind;
    input.addEventListener("change", () => {
      const file = input.files[0];
      if (!file) return;
      const validation = validateShowcaseFile(file);
      if (validation) { input.value = ""; showMessage(validation, true); return; }
      const url = URL.createObjectURL(file);
      objectUrls.add(url);
      preview.innerHTML = `<img src="${url}" alt="Selected ${kind} preview">`;
      showMessage("");
    });
    field.querySelector(".save-showcase").addEventListener("click", async () => {
      const file = input.files[0];
      const validation = file ? validateShowcaseFile(file) : "Choose an image first.";
      if (validation) { showMessage(validation, true); return; }
      try {
        await uploadShowcaseImage(kind, file);
        showMessage(`${kind === "logo" ? "Logo" : "Grill photo"} saved.`);
        setBusy(false);
        await refresh();
      } catch (error) { showMessage(error.message || "Could not save image.", true); }
    });
    field.querySelector(".remove-showcase").addEventListener("click", async () => {
      try {
        await deleteShowcaseImage(kind);
        showMessage(`${kind === "logo" ? "Logo" : "Grill photo"} removed.`);
        setBusy(false);
        await refresh();
      } catch (error) { showMessage(error.message || "Could not remove image.", true); }
    });
  });
  strip.querySelectorAll(".stack-position input").forEach((slider) => slider.addEventListener("input", () => {
    const x = clampStackPosition(strip.querySelector('[name="stack-x"]').value, 50);
    const y = clampStackPosition(strip.querySelector('[name="stack-y"]').value, 5);
    window.localStorage.setItem(STACK_POSITION_KEY, JSON.stringify({ x, y }));
    strip.querySelector('[name="stack-x"] + output').textContent = `${x}%`;
    strip.querySelector('[name="stack-y"] + output').textContent = `${y}%`;
    const anchor = strip.querySelector(".photo-stack-anchor");
    if (anchor) { anchor.style.left = `${x}%`; anchor.style.top = `${y}%`; }
  }));
  const resize = () => { strip.classList.remove("showcase-mobile", "showcase-wide"); strip.classList.add(showcaseLayoutClass(window.innerWidth)); };
  window.addEventListener("resize", resize);
  return () => { close(); setBusy(false); window.removeEventListener("resize", resize); };
}
