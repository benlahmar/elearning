// A discontinuity must never become a played interval (seek, stall, speed change).
export function continuousInterval(from, to, elapsed, rate) {
  if (![from, to, elapsed, rate].every(Number.isFinite) || to <= from || elapsed <= 0) return null
  if (to - from > Math.min(60, elapsed * rate + 1.5)) return null
  return { from_seconds: from, to_seconds: to }
}
