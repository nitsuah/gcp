/**
 * Failed-login limiter: at most `maxFailures` failures per client address within
 * `windowMs`, so a short configured token cannot be brute-forced.
 */
function createLoginLimiter({ maxFailures = 10, windowMs = 15 * 60 * 1000, maxEntries = 10000 } = {}) {
  const failures = new Map();

  function blocked(ip, now) {
    const entry = failures.get(ip);
    if (!entry || now - entry.start >= windowMs) return false;
    return entry.count >= maxFailures;
  }

  function recordFailure(ip, now) {
    const entry = failures.get(ip);
    if (!entry || now - entry.start >= windowMs) {
      if (failures.size >= maxEntries) failures.clear(); // bound memory
      failures.set(ip, { start: now, count: 1 });
    } else {
      entry.count += 1;
    }
  }

  function reset(ip) {
    failures.delete(ip);
  }

  return { blocked, recordFailure, reset, windowMs };
}

module.exports = { createLoginLimiter };
