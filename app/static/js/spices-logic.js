const compareText = (left, right) => String(left).localeCompare(String(right), undefined, {
  sensitivity: "base",
});

export function filterSpices(items, query) {
  const needle = String(query || "").trim().toLocaleLowerCase();
  if (!needle) return [...items];
  return items.filter((item) => [item.brand, item.name].some(
    (value) => String(value || "").toLocaleLowerCase().includes(needle),
  ));
}

export function groupSpices(items) {
  const sorted = [...items].sort((left, right) => (
    compareText(left.brand, right.brand)
    || compareText(left.name, right.name)
    || Number(left.id) - Number(right.id)
  ));
  const groups = [];
  sorted.forEach((item) => {
    const previous = groups.at(-1);
    if (!previous || compareText(previous.brand, item.brand) !== 0) {
      groups.push({ brand: item.brand, items: [item] });
    } else {
      previous.items.push(item);
    }
  });
  return groups;
}

export function formatSpicePrice(value) {
  if (value === null || value === undefined || value === "") return "";
  const amount = Number(value);
  return Number.isFinite(amount) ? `$${amount.toFixed(2)}` : "";
}

export function formatSpiceSize(value) {
  if (value === null || value === undefined || value === "") return "";
  const amount = Number(value);
  return Number.isFinite(amount) ? `${amount} oz` : "";
}

export function isLockedSpice(item) {
  return String(item.brand).toLocaleLowerCase() === "custom"
    && String(item.name).toLocaleLowerCase() === "custom blend";
}

export function validateSpice(values) {
  const errors = {};
  if (!values.brand.trim()) errors.brand = "Enter a brand.";
  if (!values.name.trim()) errors.name = "Enter a rub name.";
  if (values.price !== "" && (!Number.isFinite(Number(values.price)) || Number(values.price) < 0)) {
    errors.price = "Price cannot be negative.";
  }
  if (values.size_oz !== "" && (!Number.isFinite(Number(values.size_oz)) || Number(values.size_oz) <= 0)) {
    errors.size_oz = "Size must be greater than zero.";
  }
  return errors;
}
