import { MAX_SMOKE_PARTICLES, createCleanupBag, shouldAnimateSmoke, smokeIntensity, spawnParticle, updateParticle } from "../smoke-logic.js";

const SMOKE_ENABLED_KEY = "smoke-stack.showcase.smoke-enabled";
function readEnabled(storage) { try { return storage.getItem(SMOKE_ENABLED_KEY) !== "false"; } catch { return true; } }
function writeEnabled(storage, enabled) { try { storage.setItem(SMOKE_ENABLED_KEY, String(enabled)); } catch { /* Storage may be disabled. */ } }

export function mountSmoke(container) {
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
  const cleanup = createCleanupBag();
  const canvas = document.createElement("canvas");
  canvas.className = "smoke-canvas";
  canvas.setAttribute("aria-hidden", "true");
  document.body.append(canvas);
  const context = canvas.getContext("2d");
  let enabled = readEnabled(window.localStorage), liveCook = false, intensity = 0, anchor = null;
  let particles = [], frame = 0, previousTime = 0, spawnCarry = 0;
  const locateAnchor = () => {
    const element = container.querySelector("[data-smokestack]");
    if (!element) { anchor = null; return; }
    const bounds = element.getBoundingClientRect();
    anchor = { x: bounds.left + bounds.width / 2, y: bounds.top + bounds.height / 2 };
  };
  const resize = () => {
    const ratio = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = Math.round(window.innerWidth * ratio); canvas.height = Math.round(window.innerHeight * ratio);
    canvas.style.width = `${window.innerWidth}px`; canvas.style.height = `${window.innerHeight}px`;
    context.setTransform(ratio, 0, 0, ratio, 0, 0); locateAnchor();
  };
  const syncToggle = () => {
    const button = container.querySelector(".smoke-toggle");
    if (!button || button.dataset.bound) return;
    button.dataset.bound = "true"; button.classList.toggle("on", enabled); button.setAttribute("aria-pressed", String(enabled));
    button.addEventListener("click", () => {
      enabled = !enabled; writeEnabled(window.localStorage, enabled);
      button.classList.toggle("on", enabled); button.setAttribute("aria-pressed", String(enabled));
    });
  };
  const draw = (particle) => {
    const gradient = context.createRadialGradient(particle.x, particle.y, 0, particle.x, particle.y, particle.radius);
    gradient.addColorStop(0, `rgba(245,245,240,${particle.opacity * 0.13})`);
    gradient.addColorStop(0.55, `rgba(220,225,220,${particle.opacity * 0.08})`);
    gradient.addColorStop(1, "rgba(210,215,210,0)"); context.fillStyle = gradient;
    context.beginPath(); context.arc(particle.x, particle.y, particle.radius, 0, Math.PI * 2); context.fill();
  };
  const tick = (time) => {
    const elapsed = Math.min((time - previousTime) / 1000 || 0, 0.1); previousTime = time; locateAnchor();
    const emitting = shouldAnimateSmoke({ liveCook, intensity, reducedMotion: reduced.matches, hidden: document.hidden, enabled, anchor });
    if (emitting) {
      spawnCarry += elapsed * (intensity === 1 ? 7 : 2);
      while (spawnCarry >= 1 && particles.length < MAX_SMOKE_PARTICLES) { particles.push(spawnParticle(anchor)); spawnCarry -= 1; }
    } else spawnCarry = 0;
    particles = particles.map((particle) => updateParticle(particle, elapsed, emitting)).filter((particle) => !particle.remove);
    context.clearRect(0, 0, window.innerWidth, window.innerHeight); particles.forEach(draw);
    frame = window.requestAnimationFrame(tick);
  };
  const visibilityChanged = () => {
    if (document.hidden || reduced.matches) { window.cancelAnimationFrame(frame); frame = 0; previousTime = 0; }
    else if (!frame) frame = window.requestAnimationFrame(tick);
  };
  const motionChanged = () => { particles = []; context.clearRect(0, 0, window.innerWidth, window.innerHeight); visibilityChanged(); };
  window.addEventListener("resize", resize); window.addEventListener("scroll", locateAnchor, { passive: true });
  document.addEventListener("visibilitychange", visibilityChanged); reduced.addEventListener("change", motionChanged); resize();
  if (!reduced.matches && !document.hidden) frame = window.requestAnimationFrame(tick);
  cleanup.add(() => canvas.remove()); cleanup.add(() => window.cancelAnimationFrame(frame));
  cleanup.add(() => reduced.removeEventListener("change", motionChanged)); cleanup.add(() => document.removeEventListener("visibilitychange", visibilityChanged));
  cleanup.add(() => window.removeEventListener("scroll", locateAnchor)); cleanup.add(() => window.removeEventListener("resize", resize));
  return { update(cook, sample) { liveCook = Boolean(cook && cook.ended_at == null && cook.status !== "planned"); intensity = smokeIntensity(cook?.status, sample?.fire_state); syncToggle(); locateAnchor(); }, cleanup: cleanup.cleanup };
}
