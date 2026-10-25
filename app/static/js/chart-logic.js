function formatter(timeZone, options) {
  return new Intl.DateTimeFormat(undefined, { ...options, ...(timeZone ? { timeZone } : {}) });
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
