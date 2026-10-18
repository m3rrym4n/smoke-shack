const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (character) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
})[character]);

export function cookNotesMarkup(notes) {
  if (!notes.length) return "";
  return `<section class="board cook-notes"><h2 class="hd">Notes</h2><div class="cook-notes-grid">${notes.map((note) => `<article class="note"><span class="tape" aria-hidden="true"></span><h3>${escapeHtml(note.title)}</h3><p>${escapeHtml(note.body)}</p></article>`).join("")}</div></section>`;
}
