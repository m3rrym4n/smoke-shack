export function formatMoney(value) {
  const amount = Number(value);
  if (!Number.isFinite(amount)) return "—";
  return new Intl.NumberFormat(undefined, { style: "currency", currency: "USD" }).format(amount);
}

export function formatDate(value) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value || "")) return "—";
  const [year, month, day] = value.split("-").map(Number);
  return new Intl.DateTimeFormat(undefined, {
    year: "numeric", month: "short", day: "numeric",
  }).format(new Date(year, month - 1, day));
}

function errorText(error) {
  const detail = error?.message || "Something went wrong. Please try again.";
  if (!detail.startsWith("[")) return detail;
  try {
    const errors = JSON.parse(detail);
    return errors.map((item) => item.msg?.replace(/^Value error, /, "") || "Check this field.").join(" ");
  } catch {
    return detail;
  }
}

export function renderApiError(form, error) {
  const message = form.querySelector(".form-message");
  if (!message) return;
  message.textContent = errorText(error);
  message.classList.add("error");
}

export function confirmDelete(container, onConfirm) {
  container.innerHTML = `<span>Delete this?</span><button class="cc confirm-yes" type="button">Yes, delete</button><button class="cc confirm-no" type="button">Keep it</button>`;
  const cancel = () => { container.hidden = true; };
  container.hidden = false;
  container.querySelector(".confirm-no").addEventListener("click", cancel, { once: true });
  container.querySelector(".confirm-yes").addEventListener("click", async (event) => {
    event.currentTarget.disabled = true;
    await onConfirm();
  }, { once: true });
}
