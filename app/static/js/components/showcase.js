import { deleteShowcaseImage, uploadShowcaseImage } from "../api.js";
import {
  readStackPosition as readStackPositionValue, showcaseLayoutClass, showcasePlaceholder, showcaseSaveEnabled,
  validateShowcaseFile, writeStackPosition,
} from "../live-logic.js";

const STACK_POSITION_KEY = "smoke-stack.showcase.stack-position";

const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (character) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
})[character]);

export function readStackPosition(storage = window.localStorage) {
  return readStackPositionValue(storage, STACK_POSITION_KEY);
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
  return `<div class="showcase-photo"><img src="${escapeHtml(url)}" alt="Grill"><span class="photo-stack-anchor" data-smokestack style="left:${position.x}%;top:${position.y}%" aria-hidden="true"></span></div>`;
}

export function showcaseMarkup(showcase, grillName, width = window.innerWidth, smokeControl = true) {
  const position = readStackPosition();
  return `<div class="pit-showcase ${showcaseLayoutClass(width)}">
    <div class="showcase-name" title="${escapeHtml(grillName)}">${escapeHtml(grillName || "My grill")}</div>
    ${photoMarkup(showcase?.photo_url, position)}
    <div class="showcase-controls">${smokeControl ? '<button class="smoke-toggle cc" type="button" aria-pressed="true">Smoke</button>' : ""}<button class="change-pictures" type="button" aria-expanded="false">Change pictures</button></div>
    <div class="showcase-editor" hidden>
      ${editorRow("logo", "Logo", showcase?.logo_url)}
      ${editorRow("photo", "Grill photo", showcase?.photo_url)}
      <fieldset class="stack-position" ${showcase?.photo_url ? "" : "hidden"}><legend>Smoke position on photo</legend>
        <label>Horizontal <input name="stack-x" type="range" min="0" max="100" value="${position.x}"><output>${position.x}%</output></label>
        <label>Vertical <input name="stack-y" type="range" min="0" max="100" value="${position.y}"><output>${position.y}%</output></label>
      </fieldset>
    </div>
  </div>`;
}

function editorRow(kind, label, imageUrl) {
  const preview = imageUrl
    ? `<img src="${escapeHtml(imageUrl)}" alt="Current ${label.toLowerCase()}">`
    : `<span>No ${label.toLowerCase()} uploaded</span>`;
  const accept = kind === "logo"
    ? "image/png,image/jpeg,image/webp,.svg,image/svg+xml"
    : "image/png,image/jpeg,image/webp";
  return `<div class="showcase-image-field" data-image-kind="${kind}"><label><span>${label}</span><input type="file" accept="${accept}"></label><button class="showcase-preview" type="button" aria-label="Choose ${label.toLowerCase()}">${preview}</button><div class="showcase-image-actions"><button class="cc save-showcase" type="button" disabled>Save</button><span class="showcase-message" role="status"></span><button class="cc remove-showcase" type="button" ${imageUrl ? "" : "disabled"}>Remove</button></div></div>`;
}

export function bindShowcase(container, { onLogoChange = () => {}, setBusy }) {
  const strip = container.querySelector(".pit-showcase");
  if (!strip) return () => {};
  const editor = strip.querySelector(".showcase-editor");
  const toggle = strip.querySelector(".change-pictures");
  const objectUrls = new Set();
  const close = () => objectUrls.forEach((url) => URL.revokeObjectURL(url));

  toggle.addEventListener("click", () => {
    const opening = editor.hidden;
    editor.hidden = !opening;
    toggle.setAttribute("aria-expanded", String(opening));
    toggle.textContent = opening ? "Close picture editor" : "Change pictures";
    strip.classList.toggle("editor-open", opening);
    setBusy(opening);
  });
  strip.querySelectorAll(".showcase-image-field").forEach((field) => {
    const input = field.querySelector("input");
    const preview = field.querySelector(".showcase-preview");
    const save = field.querySelector(".save-showcase");
    const remove = field.querySelector(".remove-showcase");
    const message = field.querySelector(".showcase-message");
    const kind = field.dataset.imageKind;
    let messageTimer;
    const showMessage = (text, error = false, temporary = false) => {
      window.clearTimeout(messageTimer);
      message.textContent = text;
      message.classList.toggle("error", error);
      if (temporary) messageTimer = window.setTimeout(() => showMessage(""), 4000);
    };
    const updateImages = (url) => {
      const currentUrl = url ? `${url}?v=${Date.now()}` : null;
      preview.innerHTML = currentUrl
        ? `<img src="${escapeHtml(currentUrl)}" alt="Current ${kind} preview">`
        : `<span>No ${kind === "logo" ? "logo" : "grill photo"} uploaded</span>`;
      if (kind === "logo") {
        onLogoChange(currentUrl);
      } else {
        const position = readStackPosition();
        strip.querySelector(".showcase-photo").outerHTML = photoMarkup(currentUrl, position);
        strip.querySelector(".stack-position").hidden = !currentUrl;
      }
      remove.disabled = !currentUrl;
    };
    preview.addEventListener("click", () => input.click());
    input.addEventListener("change", () => {
      const file = input.files[0];
      save.disabled = !showcaseSaveEnabled(file);
      showMessage("");
      if (!file) return;
      const validation = validateShowcaseFile(file, kind);
      if (validation) { input.value = ""; save.disabled = true; showMessage(validation, true); return; }
      const url = URL.createObjectURL(file);
      objectUrls.add(url);
      preview.innerHTML = `<img src="${url}" alt="Selected ${kind} preview">`;
    });
    save.addEventListener("click", async () => {
      const file = input.files[0];
      const validation = file ? validateShowcaseFile(file, kind) : "Choose an image first.";
      if (validation) { showMessage(validation, true, !file); return; }
      try {
        const result = await uploadShowcaseImage(kind, file);
        updateImages(result[`${kind}_url`]);
        input.value = "";
        save.disabled = true;
        showMessage("Saved");
      } catch (error) { showMessage(error.message || "Could not save image.", true); }
    });
    remove.addEventListener("click", async () => {
      try {
        await deleteShowcaseImage(kind);
        updateImages(null);
        input.value = "";
        save.disabled = true;
        showMessage("");
      } catch (error) { showMessage(error.message || "Could not remove image.", true); }
    });
  });
  strip.querySelectorAll(".stack-position input").forEach((slider) => slider.addEventListener("input", () => {
    const { x, y } = writeStackPosition(window.localStorage, STACK_POSITION_KEY, {
      x: strip.querySelector('[name="stack-x"]').value,
      y: strip.querySelector('[name="stack-y"]').value,
    });
    strip.querySelector('[name="stack-x"] + output').textContent = `${x}%`;
    strip.querySelector('[name="stack-y"] + output').textContent = `${y}%`;
    const anchor = strip.querySelector(".photo-stack-anchor");
    if (anchor) { anchor.style.left = `${x}%`; anchor.style.top = `${y}%`; }
  }));
  const resize = () => { strip.classList.remove("showcase-mobile", "showcase-wide"); strip.classList.add(showcaseLayoutClass(window.innerWidth)); };
  window.addEventListener("resize", resize);
  return () => { close(); setBusy(false); window.removeEventListener("resize", resize); };
}
