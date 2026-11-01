import { restoreBackup, withBase } from "../api.js";
import { restoreEnabled } from "../backup-logic.js";

const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (character) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
})[character]);

function label(value) {
  return String(value).replaceAll("_", " ").replace(/^./, (letter) => letter.toUpperCase());
}

function summaryMarkup(result) {
  const rows = Object.entries(result.tables || {}).map(([name, count]) => (
    `<li><span>${escapeHtml(label(name))}</span><strong>${escapeHtml(count)}</strong></li>`
  )).join("");
  return `<div class="restore-success">
    <h2>Restore complete</h2>
    <p>Your backup is back on the board.</p>
    <ul class="restore-counts">${rows}<li><span>Photos</span><strong>${escapeHtml(result.photo_count)}</strong></li></ul>
    <p>Safety copy: <code>${escapeHtml(result.safety_copy)}</code></p>
    <button class="pbtn reload-app" type="button">Reload the app</button>
  </div>`;
}

export function mountBackupView(container) {
  let disposed = false;
  container.innerHTML = `<section class="board backup-board">
    <h1 class="hd">Backup &amp; Restore</h1>
    <div class="backup-sections">
      <section class="stp backup-section">
        <h2>Backup</h2>
        <p>Download the cook log, pantry and its photos, grill logo and picture, notes, pinned events, meat groups, profiles, pellets, and everything else in the database.</p>
        <p class="mut">Home Assistant connection settings and <code>entities.yaml</code> are not included.</p>
        <a class="pbtn backup-download" href="${withBase("/api/backup")}" download>Download backup</a>
      </section>
      <section class="stp backup-section restore-section">
        <h2>Restore</h2>
        <p class="restore-warning">Restore REPLACES all current data. A safety copy is saved first.</p>
        <label class="fl"><span class="lb">Backup file</span><input class="ci restore-file" type="file" accept=".zip,application/zip"></label>
        <button class="pbtn begin-restore" type="button" disabled>Restore</button>
        <div class="restore-confirm" hidden>
          <p>Replace all current data with <strong class="restore-filename"></strong>?</p>
          <div class="restore-actions"><button class="pbtn confirm-restore" type="button">Yes, restore it</button><button class="cc cancel-restore" type="button">Cancel</button></div>
        </div>
        <p class="restore-message" role="status"></p>
        <div class="restore-result"></div>
      </section>
    </div>
  </section>`;
  const picker = container.querySelector(".restore-file");
  const begin = container.querySelector(".begin-restore");
  const confirmation = container.querySelector(".restore-confirm");
  const filename = container.querySelector(".restore-filename");
  const message = container.querySelector(".restore-message");
  const result = container.querySelector(".restore-result");
  const confirm = container.querySelector(".confirm-restore");
  const cancel = container.querySelector(".cancel-restore");

  picker.addEventListener("change", () => {
    begin.disabled = !restoreEnabled(picker.files[0]);
    confirmation.hidden = true;
    message.textContent = "";
  });
  begin.addEventListener("click", () => {
    if (!restoreEnabled(picker.files[0])) return;
    filename.textContent = picker.files[0].name;
    confirmation.hidden = false;
  });
  cancel.addEventListener("click", () => { confirmation.hidden = true; });
  confirm.addEventListener("click", async () => {
    const file = picker.files[0];
    if (!restoreEnabled(file)) return;
    picker.disabled = true;
    begin.disabled = true;
    confirm.disabled = true;
    cancel.disabled = true;
    message.classList.remove("error");
    message.textContent = "Restoring backup…";
    result.innerHTML = "";
    try {
      const restored = await restoreBackup(file);
      if (disposed) return;
      confirmation.hidden = true;
      message.textContent = "";
      result.innerHTML = summaryMarkup(restored);
      result.querySelector(".reload-app").addEventListener("click", () => window.location.reload());
    } catch (error) {
      if (disposed) return;
      message.classList.add("error");
      message.textContent = error.message;
      picker.disabled = false;
      begin.disabled = !restoreEnabled(picker.files[0]);
      confirm.disabled = false;
      cancel.disabled = false;
    }
  });
  return () => { disposed = true; };
}
