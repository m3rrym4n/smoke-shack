export const MAX_SMOKE_PARTICLES = 60;

const normalized = (value) => String(value ?? "").trim().toLowerCase().replaceAll("_", " ");

export function smokeIntensity(cookStatus, fireState) {
  const phase = normalized(cookStatus);
  const fire = normalized(fireState);
  if (phase === "cooldown" || phase === "cool down" || fire === "cooldown" || fire === "cool down") return 0.22;
  if (["startup", "cook"].includes(phase) && ["startup", "running", "heating"].includes(fire)) return 1;
  return 0;
}

export function shouldAnimateSmoke({ liveCook, intensity, reducedMotion, hidden, enabled, anchor }) {
  return Boolean(liveCook && intensity > 0 && !reducedMotion && !hidden && enabled && anchor);
}

export function spawnParticle(anchor, random = Math.random) {
  return { x: anchor.x + (random() - 0.5) * 8, y: anchor.y, vx: (random() - 0.5) * 7,
    vy: -(45 + random() * 25), age: 0, life: 9000 + random() * 3000,
    radius: 8 + random() * 7, sway: random() * Math.PI * 2, inactiveAge: 0 };
}

export function updateParticle(particle, elapsedSeconds, emitting = true) {
  const next = { ...particle };
  next.age += elapsedSeconds * 1000;
  next.inactiveAge = emitting ? 0 : next.inactiveAge + elapsedSeconds * 1000;
  next.x += (next.vx + Math.sin(next.sway + next.age / 1100) * 5) * elapsedSeconds;
  next.y += next.vy * elapsedSeconds;
  next.radius += 6 * elapsedSeconds;
  next.opacity = Math.max(0, 1 - next.age / next.life) * (emitting ? 1 : Math.max(0, 1 - next.inactiveAge / 3000));
  next.remove = next.age >= next.life || next.inactiveAge >= 3000 || next.y + next.radius < 0;
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
