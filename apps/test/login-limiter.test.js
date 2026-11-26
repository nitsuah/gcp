const test = require('node:test');
const assert = require('node:assert');
const { createLoginLimiter } = require('../lib/login-limiter');

const T0 = 1_000_000;

function fail(limiter, ip, times, now = T0) {
  for (let i = 0; i < times; i += 1) limiter.recordFailure(ip, now);
}

test('an address with no failures is not blocked', () => {
  assert.strictEqual(createLoginLimiter().blocked('1.1.1.1', T0), false);
});

test('blocks exactly at the 10th failure inside the window', () => {
  const limiter = createLoginLimiter();
  fail(limiter, '1.1.1.1', 9);
  assert.strictEqual(limiter.blocked('1.1.1.1', T0), false);
  fail(limiter, '1.1.1.1', 1);
  assert.strictEqual(limiter.blocked('1.1.1.1', T0), true);
});

test('a different address is unaffected', () => {
  const limiter = createLoginLimiter();
  fail(limiter, '1.1.1.1', 10);
  assert.strictEqual(limiter.blocked('2.2.2.2', T0), false);
});

test('the block ends once the window has elapsed', () => {
  const limiter = createLoginLimiter();
  fail(limiter, '1.1.1.1', 10);
  assert.strictEqual(limiter.blocked('1.1.1.1', T0 + limiter.windowMs - 1), true);
  assert.strictEqual(limiter.blocked('1.1.1.1', T0 + limiter.windowMs), false);
});

test('a failure after the window starts a fresh count of one', () => {
  const limiter = createLoginLimiter();
  fail(limiter, '1.1.1.1', 10);
  const later = T0 + limiter.windowMs;
  limiter.recordFailure('1.1.1.1', later);
  assert.strictEqual(limiter.blocked('1.1.1.1', later), false);
  fail(limiter, '1.1.1.1', 8, later);
  assert.strictEqual(limiter.blocked('1.1.1.1', later), false);
  fail(limiter, '1.1.1.1', 1, later);
  assert.strictEqual(limiter.blocked('1.1.1.1', later), true);
});

test('reset unblocks an address', () => {
  const limiter = createLoginLimiter();
  fail(limiter, '1.1.1.1', 10);
  limiter.reset('1.1.1.1');
  assert.strictEqual(limiter.blocked('1.1.1.1', T0), false);
});

test('maxFailures is configurable', () => {
  const limiter = createLoginLimiter({ maxFailures: 2 });
  fail(limiter, '1.1.1.1', 1);
  assert.strictEqual(limiter.blocked('1.1.1.1', T0), false);
  fail(limiter, '1.1.1.1', 1);
  assert.strictEqual(limiter.blocked('1.1.1.1', T0), true);
});

test('hitting maxEntries clears the map before counting the new address', () => {
  const limiter = createLoginLimiter({ maxFailures: 1, maxEntries: 3 });
  for (const ip of ['a', 'b', 'c']) limiter.recordFailure(ip, T0);
  assert.strictEqual(limiter.blocked('a', T0), true);
  limiter.recordFailure('d', T0);
  for (const ip of ['a', 'b', 'c']) assert.strictEqual(limiter.blocked(ip, T0), false);
  assert.strictEqual(limiter.blocked('d', T0), true);
});

test('windowMs reflects the configuration', () => {
  assert.strictEqual(createLoginLimiter().windowMs, 15 * 60 * 1000);
  assert.strictEqual(createLoginLimiter({ windowMs: 5000 }).windowMs, 5000);
});
