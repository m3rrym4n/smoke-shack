export const MAX_SMOKE_PARTICLES = 140;

const normalized = (value) => String(value ?? "").trim().toLowerCase().replaceAll("_", " ");
const clamp = (value, low, high) => Math.min(high, Math.max(low, value));
const smooth = (value) => value * value * (3 - 2 * value);

export function smokeIntensity(cookStatus, fireState) {
  const phase = normalized(cookStatus);
  const fire = normalized(fireState);
  if (["off", "idle", "fan only"].includes(fire) || ["closed", "planned"].includes(phase)) return 0;
  if (phase === "cooldown" || phase === "cool down" || fire === "cooldown" || fire === "cool down") return 0.12;
  if (phase === "startup" || fire === "startup" || fire === "ignition") return 0.9;
  if (phase === "cook" && ["running", "heating"].includes(fire)) return fire === "heating" ? 0.75 : 0.58;
  return 0;
}

export function smokeDemoMode(hash) {
  const [route, query = ""] = String(hash ?? "").replace(/^#/, "").split("?", 2);
  return route === "live" && new URLSearchParams(query).get("smoke") === "demo";
}

export function shouldAnimateSmoke({ liveCook, intensity, reducedMotion, hidden, enabled, anchor }) {
  return Boolean(liveCook && intensity > 0 && !reducedMotion && !hidden && enabled && anchor);
}

export function pageToScreen(point, scroll) {
  return { x: point.x - scroll.x, y: point.y - scroll.y };
}

function lattice(x, y, seed) {
  let value = Math.imul(x, 374761393) + Math.imul(y, 668265263) + Math.imul(seed, 1442695041);
  value = Math.imul(value ^ (value >>> 13), 1274126177);
  return ((value ^ (value >>> 16)) >>> 0) / 4294967295;
}

export function valueNoise2D(x, y, seed = 0) {
  const left = Math.floor(x), top = Math.floor(y);
  const fx = smooth(x - left), fy = smooth(y - top);
  const upper = lattice(left, top, seed) * (1 - fx) + lattice(left + 1, top, seed) * fx;
  const lower = lattice(left, top + 1, seed) * (1 - fx) + lattice(left + 1, top + 1, seed) * fx;
  return (upper * (1 - fy) + lower * fy) * 2 - 1;
}

export function spawnParticle(anchor, random = Math.random, intensity = 0.58) {
  const life = 17000 + random() * 7000;
  return {
    x: anchor.x + (random() - 0.5) * (7 + intensity * 10),
    y: anchor.y + (random() - 0.5) * 4,
    vx: (random() - 0.5) * 9,
    vy: -(48 + random() * 25),
    age: 0,
    life,
    radius: 7 + random() * 8,
    growth: 2.5 + random() * 2.8,
    spin: (random() - 0.5) * 0.45,
    rotation: random() * Math.PI * 2,
    noiseOffset: random() * 100,
    seed: Math.floor(random() * 100000),
    inactiveAge: 0,
    opacity: 0,
    remove: false,
    density: intensity,
  };
}

export function updateParticle(particle, elapsedSeconds, options = {}) {
  const elapsed = clamp(elapsedSeconds, 0, 0.1);
  const emitting = options.emitting ?? true;
  const wind = options.wind ?? 0;
  const next = { ...particle };
  next.age += elapsed * 1000;
  next.inactiveAge = emitting ? 0 : next.inactiveAge + elapsed * 1000;
  const ageSeconds = next.age / 1000;
  const curl = valueNoise2D(next.noiseOffset + ageSeconds * 0.32, next.y * 0.004, next.seed);
  next.vx += (curl * 11 + wind - next.vx * 0.16) * elapsed;
  next.vy += 1.05 * elapsed;
  next.x += next.vx * elapsed;
  next.y += next.vy * elapsed;
  next.radius += next.growth * elapsed;
  next.rotation += next.spin * elapsed;
  const progress = clamp(next.age / next.life, 0, 1);
  const appear = clamp(next.age / 700, 0, 1);
  const fade = Math.pow(1 - progress, 1.35);
  const stopped = emitting ? 1 : clamp(1 - next.inactiveAge / 3200, 0, 1);
  next.opacity = appear * fade * stopped * (0.16 + next.density * 0.18);
  next.remove = progress >= 1 || next.inactiveAge >= 3200;
  return next;
}

export function createCleanupBag() {
  const tasks = [];
  let cleaned = false;
  return { add(task) { if (cleaned) task(); else tasks.push(task); }, cleanup() {
    if (cleaned) return;
    cleaned = true;
    while (tasks.length) tasks.pop()();
  } };
}
