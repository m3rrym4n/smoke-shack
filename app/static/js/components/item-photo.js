import { deletePhoto, uploadPhoto, withBase } from "../api.js";
import { PHOTO_MAX_BYTES, downscaleSize, validatePhotoFile } from "../photo-logic.js";

function photoError(error) {
  if (error?.status === 413) return "Photo must be 5 MB or smaller.";
  if (error?.status === 415) return "That image format is not supported.";
  return error?.message || "Could not update the photo.";
}

async function jpegBlob(file) {
  const url = URL.createObjectURL(file);
  const image = new Image();
  try {
    await new Promise((resolve, reject) => {
      image.onload = resolve;
      image.onerror = () => reject(new Error("Could not read this photo."));
      image.src = url;
    });
  } finally {
    URL.revokeObjectURL(url);
  }
  const size = downscaleSize(image.naturalWidth, image.naturalHeight);
  if (!size) throw new Error("Could not read this photo.");
  const canvas = document.createElement("canvas");
  canvas.width = size.width;
  canvas.height = size.height;
  const context = canvas.getContext("2d");
  if (!context) throw new Error("Could not resize this photo.");
  context.drawImage(image, 0, 0, size.width, size.height);
  const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.85));
  if (!blob) throw new Error("Could not resize this photo.");
  if (blob.size > PHOTO_MAX_BYTES) throw new Error("Photo must be 5 MB or smaller.");
  return blob;
}

export function itemPhotoMarkup(item) {
  const image = item.photo_url
    ? `<button class="item-photo-thumb" type="button" aria-label="View photo"><img src="${withBase(item.photo_url)}" alt="" loading="lazy"></button>`
    : '<div class="item-photo-placeholder" aria-label="No photo">No photo</div>';
  return `<div class="item-photo" data-photo>
    ${image}
    <div class="item-photo-actions">
      <label class="cc item-photo-upload">${item.photo_url ? "Replace photo" : "Upload photo"}<input type="file" accept="image/*"></label>
      <button class="cc item-photo-remove" type="button"${item.photo_url ? "" : " hidden"}>Remove photo</button>
    </div>
    <p class="item-photo-message" role="status"></p>
  </div>`;
}

function openLightbox(url) {
  const dialog = document.createElement("dialog");
  dialog.className = "item-photo-lightbox";
  const image = document.createElement("img");
  image.src = url;
  image.alt = "Pantry item photo";
  dialog.append(image);
  dialog.addEventListener("click", () => dialog.close());
  dialog.addEventListener("close", () => dialog.remove());
  document.body.append(dialog);
  dialog.showModal();
}

export function bindItemPhoto(root, kind, id) {
  let currentUrl = root.querySelector("img")?.src || null;
  const input = root.querySelector('input[type="file"]');
  const uploadLabel = root.querySelector(".item-photo-upload");
  const removeButton = root.querySelector(".item-photo-remove");
  const message = root.querySelector(".item-photo-message");

  const setBusy = (busy, text = "") => {
    input.disabled = busy;
    removeButton.disabled = busy;
    uploadLabel.classList.toggle("disabled", busy);
    message.textContent = text;
    message.classList.remove("error");
  };
  const showError = (error) => {
    message.textContent = photoError(error);
    message.classList.add("error");
  };
  const showPhoto = (url) => {
    currentUrl = url;
    let thumb = root.querySelector(".item-photo-thumb");
    const placeholder = root.querySelector(".item-photo-placeholder");
    if (!thumb) {
      thumb = document.createElement("button");
      thumb.type = "button";
      thumb.className = "item-photo-thumb";
      thumb.setAttribute("aria-label", "View photo");
      thumb.append(document.createElement("img"));
      placeholder.replaceWith(thumb);
      thumb.addEventListener("click", () => currentUrl && openLightbox(currentUrl));
    }
    thumb.querySelector("img").src = url;
    thumb.querySelector("img").alt = "";
    uploadLabel.firstChild.textContent = "Replace photo";
    removeButton.hidden = false;
  };
  root.querySelector(".item-photo-thumb")?.addEventListener("click", () => {
    if (currentUrl) openLightbox(currentUrl);
  });
  input.addEventListener("change", async () => {
    const file = input.files?.[0];
    const validation = validatePhotoFile(file);
    if (validation) { showError(new Error(validation)); input.value = ""; return; }
    setBusy(true, "Preparing photo…");
    try {
      const blob = await jpegBlob(file);
      setBusy(true, "Uploading photo…");
      const updated = await uploadPhoto(kind, id, blob);
      showPhoto(withBase(updated.photo_url));
      setBusy(false, "Photo uploaded.");
    } catch (error) {
      setBusy(false);
      showError(error);
    } finally {
      input.value = "";
    }
  });
  removeButton.addEventListener("click", async () => {
    setBusy(true, "Removing photo…");
    try {
      await deletePhoto(kind, id);
      currentUrl = null;
      const placeholder = document.createElement("div");
      placeholder.className = "item-photo-placeholder";
      placeholder.setAttribute("aria-label", "No photo");
      placeholder.textContent = "No photo";
      root.querySelector(".item-photo-thumb").replaceWith(placeholder);
      uploadLabel.firstChild.textContent = "Upload photo";
      removeButton.hidden = true;
      setBusy(false, "Photo removed.");
    } catch (error) {
      setBusy(false);
      showError(error);
    }
  });
}
