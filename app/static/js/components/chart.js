const WIDTH = 1100;
const HEIGHT = 316;
const PLOT = { left: 62, right: 28, top: 28, bottom: 42 };
const MAX_POINTS = 500;

const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (character) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
})[character]);

function numberOrNull(value) {
  if (value === null || value === undefined || value === "") return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

export function downsample(samples, maximum = MAX_POINTS) {
  if (samples.length <= maximum) return samples;
  const result = [];
  const step = (samples.length - 1) / (maximum - 1);
  for (let index = 0; index < maximum; index += 1) {
    result.push(samples[Math.round(index * step)]);
  }
  return result;
}

function finiteValues(samples) {
  return samples.flatMap((sample) => [sample.pit_temp, sample.probe1, sample.probe2, sample.probe1_target, sample.probe2_target]).map(numberOrNull).filter((value) => value !== null);
}

function linePath(samples, field, x, y) {
  let drawing = false;
  return samples.map((sample) => {
    const value = numberOrNull(sample[field]);
    if (value === null) {
      drawing = false;
      return "";
    }
    const command = drawing ? "L" : "M";
    drawing = true;
    return `${command}${x(sample.elapsed_seconds).toFixed(1)},${y(value).toFixed(1)}`;
  }).filter(Boolean).join(" ");
}

function elapsedLabel(seconds) {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  return hours ? `${hours}h ${minutes}m` : `${minutes}m`;
}

export function chartMarkup(samples, events, cook) {
  if (!samples.length) return `<section class="board chart-board"><h2 class="hd">Chalked up: this cook</h2><p class="mut">No temperature samples yet.</p></section>`;
  const points = downsample(samples);
  const lastElapsed = Math.max(1, ...samples.map((sample) => Number(sample.elapsed_seconds) || 0));
  const values = finiteValues(samples);
  const minTemp = Math.max(0, Math.floor((Math.min(...values, 0) - 10) / 25) * 25);
  const maxTemp = Math.max(100, Math.ceil((Math.max(...values, 100) + 10) / 25) * 25);
  const plotWidth = WIDTH - PLOT.left - PLOT.right;
  const plotHeight = HEIGHT - PLOT.top - PLOT.bottom;
  const x = (elapsed) => PLOT.left + (Math.max(0, Number(elapsed) || 0) / lastElapsed) * plotWidth;
  const y = (temperature) => PLOT.top + ((maxTemp - temperature) / (maxTemp - minTemp)) * plotHeight;
  const ticks = Array.from({ length: 5 }, (_, index) => minTemp + ((maxTemp - minTemp) * index) / 4);
  const startupSeconds = cook.startup_duration_seconds ?? (cook.startup_ended_at ? Math.max(0, (new Date(cook.startup_ended_at) - new Date(cook.started_at)) / 1000) : 0);
  const target = [...samples].reverse().flatMap((sample) => [sample.probe1_target, sample.probe2_target]).map(numberOrNull).find((value) => value !== null);
  const userEvents = events.filter((event) => event.source === "user");
  const pinNumber = new Map(userEvents.map((event, index) => [event.id, index + 1]));
  const pins = userEvents.filter((event) => Number(event.elapsed_seconds) >= 0 && Number(event.elapsed_seconds) <= lastElapsed).map((event) => {
    const pinX = x(event.elapsed_seconds);
    return `<g aria-label="${escapeHtml(event.title)}"><line class="event-stem" x1="${pinX}" x2="${pinX}" y1="${PLOT.top}" y2="${HEIGHT - PLOT.bottom}"/><circle class="event-pin" cx="${pinX}" cy="${PLOT.top + 17}" r="15"/><text class="event-pin-label" x="${pinX}" y="${PLOT.top + 23}">${pinNumber.get(event.id)}</text></g>`;
  }).join("");
  const grid = ticks.map((tick) => `<line class="chart-grid" x1="${PLOT.left}" x2="${WIDTH - PLOT.right}" y1="${y(tick)}" y2="${y(tick)}"/><text class="chart-axis" x="${PLOT.left - 10}" y="${y(tick) + 5}">${Math.round(tick)}°</text>`).join("");
  return `<section class="board chart-board">
    <div class="chart-heading"><h2 class="hd">Chalked up: this cook</h2><div class="chart-legend"><span class="pit-key">Pit</span><span class="probe-key">Probe 1</span><span class="probe-key probe-two-key">Probe 2</span>${target == null ? "" : '<span class="target-key">Target</span>'}</div></div>
    <div class="chart-scroll" tabindex="0" aria-label="Temperature chart; scroll horizontally on small screens">
      <svg class="temperature-chart" viewBox="0 0 ${WIDTH} ${HEIGHT}" role="img" aria-label="Pit and probe temperatures over ${elapsedLabel(lastElapsed)}">
        <defs><filter id="chalk-displacement"><feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="1" seed="7" result="noise"/><feDisplacementMap in="SourceGraphic" in2="noise" scale="2.5"/></filter></defs>
        <rect class="startup-band" x="${PLOT.left}" y="${PLOT.top}" width="${Math.max(0, x(Math.min(startupSeconds, lastElapsed)) - PLOT.left)}" height="${plotHeight}"/>
        ${grid}
        ${target == null ? "" : `<line class="target-line" x1="${PLOT.left}" x2="${WIDTH - PLOT.right}" y1="${y(target)}" y2="${y(target)}"/><text class="target-label" x="${WIDTH - PLOT.right - 8}" y="${y(target) - 8}">done at ${Math.round(target)}°</text>`}
        <g class="chalk-lines" filter="url(#chalk-displacement)"><path class="pit-line" d="${linePath(points, "pit_temp", x, y)}"/><path class="probe-line" d="${linePath(points, "probe1", x, y)}"/><path class="probe-line probe-two" d="${linePath(points, "probe2", x, y)}"/></g>
        ${pins}
        <text class="chart-axis" x="${PLOT.left}" y="${HEIGHT - 12}">0m</text><text class="chart-axis chart-axis-end" x="${WIDTH - PLOT.right}" y="${HEIGHT - 12}">${elapsedLabel(lastElapsed)}</text>
      </svg>
    </div>
  </section>`;
}
