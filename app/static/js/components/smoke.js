import {
  MAX_SMOKE_PARTICLES, createCleanupBag, shouldAnimateSmoke, smokeDemoMode, smokeIntensity,
  pageToScreen, spawnParticle, updateParticle, valueNoise2D,
} from "../smoke-logic.js";

const SMOKE_ENABLED_KEY = "smoke-stack.showcase.smoke-enabled";
function readEnabled(storage) { try { return storage.getItem(SMOKE_ENABLED_KEY) !== "false"; } catch { return true; } }
function writeEnabled(storage, enabled) { try { storage.setItem(SMOKE_ENABLED_KEY, String(enabled)); } catch { /* Storage may be disabled. */ } }

function smokeSprite(color) {
  const sprite = document.createElement("canvas");
  sprite.width = 128; sprite.height = 128;
  const context = sprite.getContext("2d");
  const gradient = context.createRadialGradient(64, 64, 3, 64, 64, 62);
  gradient.addColorStop(0, `rgba(${color},.92)`);
  gradient.addColorStop(0.28, `rgba(${color},.55)`);
  gradient.addColorStop(0.68, `rgba(${color},.13)`);
  gradient.addColorStop(1, `rgba(${color},0)`);
  context.fillStyle = gradient; context.fillRect(0, 0, 128, 128);
  return sprite;
}

export function mountSmoke(container) {
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
  const cleanup = createCleanupBag();
  const canvas = document.createElement("canvas");
  canvas.className = "smoke-canvas"; canvas.setAttribute("aria-hidden", "true");
  document.body.append(canvas);
  const context = canvas.getContext("2d");
  const sprites = [smokeSprite("186,202,210"), smokeSprite("213,211,202"), smokeSprite("238,235,224")];
  let enabled = readEnabled(window.localStorage), liveCook = false, intensity = 0, anchor = null;
  let scrollContainer = window;
  let particles = [], frame = 0, previousTime = 0, spawnCarry = 0, windClock = 0;
  const findScrollContainer = (element) => {
    for (let parent = element?.parentElement; parent; parent = parent.parentElement) {
      const style = window.getComputedStyle(parent);
      if (/(auto|scroll)/.test(`${style.overflow} ${style.overflowY}`) && parent.scrollHeight > parent.clientHeight) return parent;
    }
    return window;
  };
  const scrollPosition = () => ({
    x: window.scrollX + (scrollContainer === window ? 0 : scrollContainer.scrollLeft),
    y: window.scrollY + (scrollContainer === window ? 0 : scrollContainer.scrollTop),
  });
  const locateAnchor = () => {
    const element = container.querySelector("[data-smokestack]");
    if (!element) { anchor = null; return; }
    const bounds = element.getBoundingClientRect();
    const scroll = scrollPosition();
    anchor = { x: bounds.left + bounds.width / 2 + scroll.x, y: bounds.top + bounds.height / 2 + scroll.y };
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
    const screen = pageToScreen(particle, scrollPosition());
    if (screen.y + particle.radius < -window.innerHeight || screen.y - particle.radius > window.innerHeight * 2
      || screen.x + particle.radius < -window.innerWidth || screen.x - particle.radius > window.innerWidth * 2) return;
    const progress = Math.min(1, particle.age / particle.life);
    const sprite = sprites[Math.min(2, Math.floor(progress * 3))];
    const size = particle.radius * 2;
    context.save(); context.globalAlpha = particle.opacity;
    context.translate(screen.x, screen.y); context.rotate(particle.rotation);
    context.drawImage(sprite, -size, -size, size * 2, size * 2); context.restore();
  };
  const tick = (time) => {
    const elapsed = Math.min((time - previousTime) / 1000 || 0, 0.1); previousTime = time; locateAnchor();
    const emitting = shouldAnimateSmoke({ liveCook, intensity, reducedMotion: reduced.matches, hidden: document.hidden, enabled, anchor });
    windClock += elapsed;
    const wind = valueNoise2D(windClock * 0.035, 4.2, 78) * 8;
    if (emitting) {
      spawnCarry += elapsed * (5 + intensity * 18);
      while (spawnCarry >= 1 && particles.length < MAX_SMOKE_PARTICLES) { particles.push(spawnParticle(anchor, Math.random, intensity)); spawnCarry -= 1; }
    } else spawnCarry = 0;
    particles = particles.map((particle) => updateParticle(particle, elapsed, { emitting, wind })).filter((particle) => !particle.remove);
    context.clearRect(0, 0, window.innerWidth, window.innerHeight); particles.forEach(draw);
    frame = window.requestAnimationFrame(tick);
  };
  const visibilityChanged = () => {
    if (document.hidden || reduced.matches) { window.cancelAnimationFrame(frame); frame = 0; previousTime = 0; }
    else if (!frame) frame = window.requestAnimationFrame(tick);
  };
  const motionChanged = () => { particles = []; context.clearRect(0, 0, window.innerWidth, window.innerHeight); visibilityChanged(); };
  const anchorChanged = () => locateAnchor();
  const resizeObserver = new ResizeObserver(anchorChanged);
  const observeLayout = () => {
    resizeObserver.disconnect();
    const photo = container.querySelector(".showcase-photo");
    const pit = container.querySelector(".pit-board");
    if (photo) resizeObserver.observe(photo);
    if (pit) resizeObserver.observe(pit);
  };
  const imageLoaded = (event) => { if (event.target.matches?.(".showcase-photo img")) { observeLayout(); locateAnchor(); } };
  scrollContainer = findScrollContainer(container.querySelector(".pit-board"));
  window.addEventListener("resize", resize); scrollContainer.addEventListener("scroll", locateAnchor, { passive: true });
  container.addEventListener("load", imageLoaded, true); observeLayout();
  document.addEventListener("visibilitychange", visibilityChanged); reduced.addEventListener("change", motionChanged); resize();
  if (!reduced.matches && !document.hidden) frame = window.requestAnimationFrame(tick);
  cleanup.add(() => canvas.remove()); cleanup.add(() => window.cancelAnimationFrame(frame));
  cleanup.add(() => reduced.removeEventListener("change", motionChanged)); cleanup.add(() => document.removeEventListener("visibilitychange", visibilityChanged));
  cleanup.add(() => resizeObserver.disconnect()); cleanup.add(() => container.removeEventListener("load", imageLoaded, true));
  cleanup.add(() => scrollContainer.removeEventListener("scroll", locateAnchor)); cleanup.add(() => window.removeEventListener("resize", resize));
  return { update(cook, sample) {
    const demo = smokeDemoMode(window.location.hash);
    liveCook = demo || Boolean(cook && cook.ended_at == null && cook.status !== "planned");
    intensity = demo ? smokeIntensity("cook", "running") : smokeIntensity(cook?.status, sample?.fire_state);
    syncToggle(); observeLayout(); locateAnchor();
  }, cleanup: cleanup.cleanup };
}
