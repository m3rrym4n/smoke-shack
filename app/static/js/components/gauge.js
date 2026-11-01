import { withBase } from "../api.js";

const center = 200;

function number(value, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function angle(value) {
  return -135 + (Math.max(0, Math.min(500, number(value))) / 500) * 270;
}

function point(degrees, distance) {
  const radians = (degrees * Math.PI) / 180;
  return [center + Math.sin(radians) * distance, center - Math.cos(radians) * distance];
}

const escapeAttribute = (value) => String(value ?? "").replace(/[&<>'"]/g, (character) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
})[character]);

export function gaugeLogoGeometry(width, height) {
  const gaugeWidth = Math.max(0, number(width));
  const gaugeHeight = Math.max(0, number(height));
  const logoWidth = (gaugeWidth * 30) / 100;
  const logoHeight = Math.min((gaugeHeight * 14) / 100, logoWidth);
  return {
    x: (gaugeWidth - logoWidth) / 2,
    y: (gaugeHeight * 68) / 100,
    width: logoWidth,
    height: logoHeight,
  };
}

export function gaugeLogoMarkup(logoUrl, width = 400, height = 400) {
  const box = gaugeLogoGeometry(width, height);
  if (!logoUrl) {
    return `<text class="gauge-logo-slot gauge-logo-placeholder" x="${width / 2}" y="${box.y + box.height / 2}">GREEN MOUNTAIN GRILLS</text>`;
  }
  return `<image class="gauge-logo-slot" href="${escapeAttribute(withBase(logoUrl))}" x="${box.x}" y="${box.y}" width="${box.width}" height="${box.height}" preserveAspectRatio="xMidYMid meet"/>`;
}

export function gaugeSvg(temperature, setpoint, logoUrl = null) {
  const temp = number(temperature);
  const target = number(setpoint);
  const ticks = Array.from({ length: 51 }, (_, index) => {
    const degrees = angle(index * 10);
    const large = index % 5 === 0;
    const [x1, y1] = point(degrees, large ? 130 : 139);
    const [x2, y2] = point(degrees, 151);
    return `<line class="gauge-tick ${large ? "major" : ""}" x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}"/>`;
  }).join("");
  const labels = Array.from({ length: 11 }, (_, index) => {
    const value = index * 50;
    const [x, y] = point(angle(value), 111);
    return `<text class="gauge-number" x="${x}" y="${y}">${value}</text>`;
  }).join("");
  const [needleX, needleY] = point(angle(temp), 122);
  const [markerX, markerY] = point(angle(target), 154);
  const [leftX, leftY] = point(angle(target) - 4, 174);
  const [rightX, rightY] = point(angle(target) + 4, 174);

  return `<svg class="gauge" viewBox="0 0 400 400" role="img" aria-label="Pit temperature ${Math.round(temp)} degrees, setpoint ${Math.round(target)}">
    <circle class="gauge-rim" cx="200" cy="200" r="184"/><circle class="gauge-ring" cx="200" cy="200" r="171"/><circle class="gauge-face" cx="200" cy="200" r="158"/>
    ${ticks}${labels}
    <text class="gauge-temp" x="200" y="205">${Math.round(temp)}°</text>
    <text class="gauge-unit" x="200" y="232">DEGREES F</text>
    ${gaugeLogoMarkup(logoUrl)}
    <polygon class="gauge-marker" points="${markerX},${markerY} ${leftX},${leftY} ${rightX},${rightY}"/>
    <line class="gauge-needle" x1="200" y1="200" x2="${needleX}" y2="${needleY}"/><circle class="gauge-hub" cx="200" cy="200" r="13"/>
    <text class="gauge-setpoint" x="200" y="375">SETPOINT ${Math.round(target)}</text>
  </svg>`;
}
