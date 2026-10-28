export function totalCost(pounds, pricePerPound) {
  const weight = Number(pounds);
  const price = Number(pricePerPound);
  if (!Number.isFinite(weight) || !Number.isFinite(price)) return 0;
  return Math.round((weight * price + Number.EPSILON) * 100) / 100;
}

export function cookedFilterValue(filter) {
  if (filter === "cooked") return true;
  if (filter === "uncooked") return false;
  return null;
}

export function validateMeat(values) {
  const errors = {};
  if (!String(values.type || "").trim()) errors.type = "Enter a cut or meat type.";
  if (!Number.isFinite(Number(values.pounds)) || Number(values.pounds) <= 0) {
    errors.pounds = "Pounds must be greater than zero.";
  }
  if (!Number.isFinite(Number(values.price_per_pound)) || Number(values.price_per_pound) <= 0) {
    errors.price_per_pound = "Price per pound must be greater than zero.";
  }
  if (!/^\d{4}-\d{2}-\d{2}$/.test(values.purchased_on || "")) {
    errors.purchased_on = "Choose a purchase date.";
  }
  return errors;
}
