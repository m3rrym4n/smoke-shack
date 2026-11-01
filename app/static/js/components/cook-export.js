import { buildExportFilename, cookStatusBadgeMarkup, exportPhotoSelection, NO_PHOTO, pelletLine, shownPapers, weightText } from "../cook-export-logic.js";
import { phaseDurations, showcaseNameLines } from "../live-logic.js";
import { chartMarkup } from "./chart.js";
import { seasoningText } from "../spice-picker-logic.js";
import { withBase } from "../api.js";

const EXPORT_WIDTH = 1080;
const EXPORT_HEIGHT = 1350;

const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (character) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
})[character]);

function duration(seconds) {
  if (!Number.isFinite(Number(seconds)) || Number(seconds) < 0) return "—";
  const minutes = Math.floor(Number(seconds) / 60);
  const hours = Math.floor(minutes / 60);
  return hours ? `${hours}h ${minutes % 60}m` : `${minutes}m`;
}

function cookDate(cook) {
  const source = cook?.started_at || cook?.created_at;
  if (!source) return "Cook date";
  return new Intl.DateTimeFormat(undefined, { weekday: "short", month: "short", day: "numeric" }).format(new Date(source));
}

function leader(label, value, active = false, total = false) {
  return `<div class="share-leader${active ? " active" : ""}${total ? " total" : ""}"><span>${label}</span><i></i><strong>${value}</strong></div>`;
}

function paper(title, text, className) {
  return `<article class="share-paper ${className}"><span class="tape"></span><h3>${title}</h3><p>${escapeHtml(text)}</p></article>`;
}

function makeCard(cook, content) {
  const times = phaseDurations(cook);
  const identity = showcaseNameLines(content.grillIdentity);
  const papers = shownPapers(content.notes, content.resultsText);
  const notesText = (content.notes || []).map((note) => note.body?.trim()).filter(Boolean).join(" · ");
  const paperMarkup = [
    papers.notes ? paper("Notes", notesText, "notes-paper") : "",
    papers.results ? paper("How it turned out", content.resultsText.trim(), "results-paper") : "",
  ].join("");
  const photo = content.photoUrl
    ? `<img src="${escapeHtml(withBase(content.photoUrl))}" alt="Cook">`
    : '<div class="share-photo-empty">COOK PHOTO</div>';
  const grillPhoto = content.showcase?.photo_url
    ? `<img class="share-grill-photo" src="${escapeHtml(withBase(content.showcase.photo_url))}" alt="Grill">`
    : "";
  const meat = cook.meat?.type || "Mystery smoke";
  const weight = weightText(cook.meat?.pounds);
  const pellet = pelletLine(cook.pellet);
  const rubs = seasoningText(cook);
  const card = document.createElement("div");
  card.className = "cook-share-card";
  card.innerHTML = `
    <header class="share-header"><div class="share-sign">SMOKE-SHACK</div><div class="share-header-details"><div class="share-date"><strong>${escapeHtml(cookDate(cook))}</strong><span>COOK OF THE DAY</span></div>${cookStatusBadgeMarkup(cook)}</div></header>
    <section class="share-hero">
      <div class="share-photo-column"><div class="share-cook-photo">${photo}</div><div class="share-grill-row"><div><strong>${escapeHtml(identity.title)}</strong>${identity.maker ? `<span>by ${escapeHtml(identity.maker)}</span>` : ""}</div>${grillPhoto}</div></div>
      <div class="share-special board"><h2>Today's Special</h2><div class="share-meat-line"><strong>${escapeHtml(meat)}</strong>${weight ? `<span>${escapeHtml(weight)}</span>` : ""}</div>${pellet ? `<div class="share-pellet">${escapeHtml(pellet)}</div>` : ""}${rubs ? `<div class="share-rubs">${escapeHtml(rubs)}</div>` : ""}<div class="share-phases">${leader("Startup", duration(times.startup))}${leader("Cook", duration(times.cook), true)}${leader("Cool down", duration(times.cooldown))}${leader("Total grill time", duration(times.total), false, true)}</div></div>
    </section>
    <section class="share-papers${papers.notes && papers.results ? "" : " single"}">${paperMarkup}</section>
    <div class="share-chart-slot"></div>`;
  const chart = document.createElement("template");
  chart.innerHTML = chartMarkup(content.samples || [], content.events || [], cook).trim();
  card.querySelector(".share-chart-slot").append(chart.content.firstElementChild);
  return card;
}

function inlineSvgStyles(card) {
  card.querySelectorAll("svg, svg *").forEach((element) => {
    const styles = window.getComputedStyle(element);
    for (const property of styles) {
      element.style.setProperty(property, styles.getPropertyValue(property));
    }
  });
}

async function waitForImages(card) {
  await Promise.all([...card.querySelectorAll("img")].map((image) => {
    if (image.complete) return image.decode?.().catch(() => {}) || Promise.resolve();
    return new Promise((resolve) => { image.addEventListener("load", resolve, { once: true }); image.addEventListener("error", resolve, { once: true }); });
  }));
}

function download(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function shareOrDownload(blob, filename) {
  const file = new File([blob], filename, { type: "image/png" });
  if (navigator.share && navigator.canShare?.({ files: [file] })) {
    try {
      await navigator.share({ files: [file], title: "Smoke-Shack cook" });
      return;
    } catch (error) {
      if (error?.name === "AbortError") return;
    }
  }
  download(blob, filename);
}

function rememberedPhoto(cookId) {
  try { return localStorage.getItem(`smoke-stack:share-photo:${cookId}`); } catch { return null; }
}

function rememberPhoto(cookId, selection) {
  try { localStorage.setItem(`smoke-stack:share-photo:${cookId}`, selection); } catch { /* Export still works without storage. */ }
}

function choosePhoto(cook, photos) {
  const selected = exportPhotoSelection(photos, rememberedPhoto(cook.id));
  const dialog = document.createElement("dialog");
  dialog.className = "share-photo-picker";
  const choices = [
    ...photos.map((photo) => `<label><input type="radio" name="share-photo" value="${photo.id}"${String(photo.id) === selected ? " checked" : ""}><span class="share-picker-thumb"><img src="${escapeHtml(withBase(photo.url))}" alt=""></span><span>${escapeHtml(photo.caption || `Photo ${photo.id}`)}</span></label>`),
    `<label><input type="radio" name="share-photo" value="${NO_PHOTO}"${selected === NO_PHOTO ? " checked" : ""}><span class="share-picker-empty">COOK<br>PHOTO</span><span>No photo</span></label>`,
  ].join("");
  dialog.innerHTML = `<form method="dialog"><h2>Pick the cook photo</h2><div class="share-picker-choices">${choices}</div><div class="share-picker-actions"><button class="cc" value="cancel" type="submit">Cancel</button><button class="pbtn" value="make" type="submit">Make PNG</button></div></form>`;
  document.body.append(dialog);
  dialog.showModal();
  return new Promise((resolve) => dialog.addEventListener("close", () => {
    const choice = dialog.querySelector('input[name="share-photo"]:checked')?.value || NO_PHOTO;
    const confirmed = dialog.returnValue === "make";
    dialog.remove();
    if (!confirmed) resolve(undefined);
    else {
      rememberPhoto(cook.id, choice);
      resolve(photos.find((photo) => String(photo.id) === choice)?.url || null);
    }
  }, { once: true }));
}

async function exportCook(button, message, cook, content, photoUrl) {
  button.disabled = true;
  button.textContent = "Making PNG…";
  message.textContent = "";
  const card = makeCard(cook, { ...content, photoUrl });
  const host = document.createElement("div");
  host.className = "cook-export-host";
  host.append(card);
  document.body.append(host);
  try {
    await document.fonts?.ready;
    await waitForImages(card);
    // html-to-image serializes the SVG outside the page stylesheet context.
    // Preserve the live chart's resolved strokes, fills, fonts, and pin styles.
    inlineSvgStyles(card);
    const blob = await window.htmlToImage.toBlob(card, {
      backgroundColor: "#4a2d19", cacheBust: true, pixelRatio: 2,
      width: EXPORT_WIDTH, height: EXPORT_HEIGHT,
    });
    if (!blob) throw new Error("The browser did not create an image.");
    await shareOrDownload(blob, buildExportFilename(cook));
  } catch (error) {
    console.error("Could not export cook", error);
    message.textContent = "Could not make the PNG. Please try again.";
  } finally {
    host.remove();
    button.disabled = false;
    button.textContent = "Export PNG";
  }
}

export function bindCookExport(detail, cook, content) {
  const button = detail.querySelector(".export-cook");
  const message = detail.querySelector(".export-message");
  if (!button) return;
  button.addEventListener("click", async () => {
    const photos = content.photos || [];
    const photoUrl = photos.length ? await choosePhoto(cook, photos) : null;
    if (photos.length && photoUrl === undefined) return;
    await exportCook(button, message, cook, content, photoUrl);
  });
}
