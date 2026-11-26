const test = require('node:test');
const assert = require('node:assert');
const { safeEqual, parseCookies, readCookie } = require('../lib/http-utils');

test('safeEqual compares values in constant time and coerces to strings', () => {
  assert.strictEqual(safeEqual('abc', 'abc'), true);
  assert.strictEqual(safeEqual('abc', 'abd'), false);
  assert.strictEqual(safeEqual('abc', 'abcd'), false);
  assert.strictEqual(safeEqual(1, '1'), true);
  assert.strictEqual(safeEqual('', ''), true);
});

test('parseCookies handles empty input', () => {
  assert.deepStrictEqual(parseCookies(undefined), {});
  assert.deepStrictEqual(parseCookies(''), {});
});

test('parseCookies parses and percent-decodes pairs', () => {
  assert.deepStrictEqual(parseCookies('a=1; b=two'), { a: '1', b: 'two' });
  assert.strictEqual(parseCookies('x=a%20b').x, 'a b');
});

test('parseCookies skips malformed escapes, nameless parts and parts without =', () => {
  assert.deepStrictEqual(parseCookies('bad=%E0%A4%A; ok=1'), { ok: '1' });
  assert.deepStrictEqual(parseCookies('=x; novalue; ok=1'), { ok: '1' });
});

test('parseCookies keeps everything after the first =', () => {
  assert.strictEqual(parseCookies('t=a=b=c').t, 'a=b=c');
});

test('readCookie returns the decoded named cookie or an empty string', () => {
  const req = { get: (h) => (h === 'cookie' ? 'a=1; session=abc%20d' : undefined) };
  assert.strictEqual(readCookie(req, 'session'), 'abc d');
  assert.strictEqual(readCookie(req, 'missing'), '');
  assert.strictEqual(readCookie({ get: () => undefined }, 'session'), '');
});
