export const PHOTO_MAX_BYTES = 5 * 1024 * 1024;
export const PHOTO_MAX_EDGE = 1600;

export function downscaleSize(width, height, maxEdge = PHOTO_MAX_EDGE) {
  if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) {
    return null;
  }
  const scale = Math.min(1, maxEdge / Math.max(width, height));
  return {
    width: Math.max(1, Math.round(width * scale)),
    height: Math.max(1, Math.round(height * scale)),
  };
}

export function validatePhotoFile(file) {
  if (!file) return "Choose a photo.";
  if (!String(file.type || "").toLowerCase().startsWith("image/")) {
    return "Choose an image file.";
  }
  if (file.size > PHOTO_MAX_BYTES) return "Photo must be 5 MB or smaller.";
  return null;
}
