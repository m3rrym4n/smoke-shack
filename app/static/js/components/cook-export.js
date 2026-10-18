import { buildExportFilename, exportPaneSelectors, exportSectionKeys } from "../cook-export-logic.js";

const EXPORT_WIDTH = 1080;

function copySvgStyles(sourcePane, pane) {
  const sourceNodes = sourcePane.querySelectorAll("svg, svg *");
  const clonedNodes = pane.querySelectorAll("svg, svg *");
  sourceNodes.forEach((source, index) => {
    const styles = window.getComputedStyle(source);
    for (const property of styles) {
      clonedNodes[index].style.setProperty(property, styles.getPropertyValue(property));
    }
  });
}

function makeSheet(detail, sectionKeys) {
  const sheet = document.createElement("div");
  sheet.className = "cook-export-sheet";
  for (const selector of exportPaneSelectors(sectionKeys)) {
    const sourcePane = detail.querySelector(selector);
    if (!sourcePane) continue;
    const pane = sourcePane.cloneNode(true);
    copySvgStyles(sourcePane, pane);
    pane.querySelectorAll("button, .photo-confirm").forEach((control) => control.remove());
    pane.querySelectorAll("img").forEach((image) => image.setAttribute("loading", "eager"));
    sheet.append(pane);
  }
  return sheet;
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
      await navigator.share({ files: [file], title: "Smoke-Stack cook" });
      return;
    } catch (error) {
      if (error?.name === "AbortError") return;
    }
  }
  download(blob, filename);
}

export function bindCookExport(detail, cook, content) {
  const button = detail.querySelector(".export-cook");
  const message = detail.querySelector(".export-message");
  if (!button) return;
  button.addEventListener("click", async () => {
    button.disabled = true;
    button.textContent = "Making PNG…";
    message.textContent = "";
    const sectionKeys = exportSectionKeys(content);
    const sheet = makeSheet(detail, sectionKeys);
    const host = document.createElement("div");
    host.className = "cook-export-host";
    host.append(sheet);
    document.body.append(host);
    try {
      await document.fonts?.ready;
      const blob = await window.htmlToImage.toBlob(sheet, {
        backgroundColor: "#4a2d19",
        cacheBust: true,
        pixelRatio: 2,
        width: EXPORT_WIDTH,
        height: sheet.scrollHeight,
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
  });
}
