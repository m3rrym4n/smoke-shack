function formatter(timeZone, options) {
  return new Intl.DateTimeFormat(undefined, { ...options, ...(timeZone ? { timeZone } : {}) });
}

function finiteNumber(value) {
  if (value === null || value === undefined || value === "") return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

export function finalTarget(samples) {
  for (let index = samples.length - 1; index >= 0; index -= 1) {
    const targets = [1, 2].map((probe) => ({
      probe,
      value: finiteNumber(samples[index][`probe${probe}_target`]),
    })).filter((target) => target.value !== null && target.value > 0);
    if (targets.length) return targets.reduce((largest, target) => target.value > largest.value ? target : largest);
  }
  return null;
}

export function finalTargets(samples, probes) {
  return probes.flatMap((probe, index) => {
    for (let sampleIndex = samples.length - 1; sampleIndex >= 0; sampleIndex -= 1) {
      const sample = samples[sampleIndex];
      const channel = sample.channels?.find((item) => item.key === probe.key);
      const value = finiteNumber(channel ? channel.target : sample[`${probe.key}_target`]);
      if (value !== null && value > 0) {
        return [{ probe: index + 1, key: probe.key, label: probe.label, value }];
      }
    }
    return [];
  });
}

export function reachedTarget(samples, target) {
  if (!target) return null;
  const targetValue = finiteNumber(target.value);
  if (targetValue === null || targetValue <= 0) return null;
  for (const sample of samples) {
    const key = target.key ?? `probe${target.probe}`;
    const channel = sample.channels?.find((item) => item.key === key);
    const temp = finiteNumber(channel ? channel.value : sample[key] ?? sample.extra_probes?.[key]);
    const elapsed = finiteNumber(sample.elapsed_seconds);
    if (temp !== null && elapsed !== null && temp >= targetValue) return { elapsed, temp };
  }
  return null;
}

export function localClockTime(startedAtIso, elapsed) {
  const reachedAt = new Date(new Date(startedAtIso).getTime() + Number(elapsed) * 1000);
  if (!Number.isFinite(reachedAt.getTime())) return "";
  return new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit" }).format(reachedAt);
}

export function hourTicks(startedAtIso, lastElapsedSeconds, timeZone = undefined) {
  if (!startedAtIso) return [];
  const startedAt = new Date(startedAtIso);
  const elapsedLimit = Number(lastElapsedSeconds);
  if (!Number.isFinite(startedAt.getTime()) || !Number.isFinite(elapsedLimit) || elapsedLimit <= 0) return [];

  const hourLabel = formatter(timeZone, { hour: "numeric" });
  const clockParts = formatter(timeZone, {
    hour: "numeric", minute: "numeric", second: "numeric", hourCycle: "h23",
  });
  const endTime = startedAt.getTime() + elapsedLimit * 1000;
  let candidateTime = Math.ceil((startedAt.getTime() + 1) / 60000) * 60000;
  const ticks = [];

  while (candidateTime < endTime) {
    const parts = Object.fromEntries(clockParts.formatToParts(new Date(candidateTime)).map((part) => [part.type, part.value]));
    if (Number(parts.minute) === 0 && Number(parts.second) === 0) {
      ticks.push({
        elapsed: (candidateTime - startedAt.getTime()) / 1000,
        label: hourLabel.format(new Date(candidateTime)),
      });
    }
    candidateTime += 60000;
  }

  return elapsedLimit > 14 * 3600 ? ticks.filter((_, index) => index % 2 === 0) : ticks;
}
