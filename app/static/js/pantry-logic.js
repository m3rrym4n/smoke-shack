const pantryTabs = new Set(["pellets", "meat", "spices"]);

export function legacyPantryRedirect(hash) {
  const route = String(hash ?? "").replace(/^#/, "").split("?", 1)[0];
  if (route === "pellets") return "#pantry/pellets";
  if (route === "meat") return "#pantry/meat";
  return null;
}

export function parsePantryRoute(hash) {
  const route = String(hash ?? "").replace(/^#/, "").split("?", 1)[0];
  if (route === "pantry") return { name: "pantry", nav: "pantry", pantryTab: "pellets" };
  const match = route.match(/^pantry\/([^/]+)$/);
  if (!match || !pantryTabs.has(match[1])) return null;
  return { name: "pantry", nav: "pantry", pantryTab: match[1] };
}
