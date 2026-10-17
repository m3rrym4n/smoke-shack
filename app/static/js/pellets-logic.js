export function validatePellet(values) {
  const errors = {};
  if (!String(values.vendor || "").trim()) errors.vendor = "Enter a pellet vendor.";
  if (!String(values.product_name || "").trim()) errors.product_name = "Enter a product name.";
  if (!Number.isFinite(Number(values.price_per_pound)) || Number(values.price_per_pound) < 0) {
    errors.price_per_pound = "Price per pound cannot be negative.";
  }
  if (!/^\d{4}-\d{2}-\d{2}$/.test(values.purchased_on || "")) {
    errors.purchased_on = "Choose a purchase date.";
  }
  return errors;
}
