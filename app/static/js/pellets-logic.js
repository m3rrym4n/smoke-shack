export function cleanUpc(value) {
  return String(value || "").replace(/[\s-]/g, "");
}

export function validateUpc(value) {
  const upc = cleanUpc(value);
  if (!upc) return "";
  return /^\d{8,14}$/.test(upc) ? "" : "UPC must be 8 to 14 digits.";
}

export function validateBagSize(value) {
  if (value === "" || value === null || value === undefined) return "";
  const amount = Number(value);
  return Number.isFinite(amount) && amount > 0 && amount <= 100
    ? ""
    : "Bag size must be greater than 0 and no more than 100 lb.";
}

export function bagCostDisplay(item) {
  if (item?.bag_size_lb === null || item?.bag_size_lb === undefined
      || item?.price_per_pound === null || item?.price_per_pound === undefined
      || !Number.isFinite(Number(item.bag_cost))) return "";
  return `$${Number(item.bag_cost).toFixed(2)}/bag`;
}

export function splitPellets(items) {
  return {
    inStock: items.filter((item) => !item.is_empty),
    empty: items.filter((item) => item.is_empty),
  };
}

export function validatePellet(values) {
  const errors = {};
  if (!["pellets", "charcoal", "wood"].includes(values.type)) errors.type = "Choose a fuel type.";
  if (!String(values.vendor || "").trim()) errors.vendor = "Enter a fuel vendor.";
  if (!String(values.product_name || "").trim()) errors.product_name = "Enter a product name.";
  if (values.price_per_pound !== ""
      && (!Number.isFinite(Number(values.price_per_pound)) || Number(values.price_per_pound) < 0)) {
    errors.price_per_pound = "Price per pound cannot be negative.";
  }
  if (!/^\d{4}-\d{2}-\d{2}$/.test(values.purchased_on || "")) {
    errors.purchased_on = "Choose a purchase date.";
  }
  const upcError = validateUpc(values.upc);
  if (upcError) errors.upc = upcError;
  const bagSizeError = validateBagSize(values.bag_size_lb);
  if (bagSizeError) errors.bag_size_lb = bagSizeError;
  return errors;
}
