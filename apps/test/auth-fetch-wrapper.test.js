const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '..', 'public', 'app.js'), 'utf8');
const endMarker = source.search(/^\}\)\(\);\s*$/m);
assert.ok(endMarker > 0, 'could not find the end of the sign-in wrapper IIFE');
const iifeEnd = source.indexOf('\n', endMarker);
const wrapperCode = source.slice(0, iifeEnd);

const res = (status, body = {}) => ({ status, ok: status >= 200 && status < 300, json: async () => body });

/** Load the wrapper against a scripted fetch and prompt; returns the wrapped fetch. */
function load({ fetchImpl, prompts = [] }) {
  const queue = [...prompts];
  const fakeFetch = test.mock.fn(fetchImpl);
  const fakePrompt = test.mock.fn(() => (queue.length ? queue.shift() : null));
  const window = { fetch: fakeFetch, prompt: fakePrompt };
  vm.runInNewContext(wrapperCode, { window });
  return { wrapped: window.fetch, fakeFetch, fakePrompt };
}

const callsTo = (fakeFetch, url) => fakeFetch.mock.calls.filter((c) => c.arguments[0] === url);

test('a non-401 response passes through untouched without prompting', async () => {
  const ok = res(200);
  const { wrapped, fakePrompt } = load({ fetchImpl: async () => ok });
  assert.strictEqual(await wrapped('/api/config'), ok);
  assert.strictEqual(fakePrompt.mock.callCount(), 0);
});

test('a 401 prompts once, logs in with the token and retries the original request', async () => {
  let configCalls = 0;
  const retried = res(200, { ok: true });
  const { wrapped, fakeFetch, fakePrompt } = load({
    prompts: ['secret'],
    fetchImpl: async (url) => {
      if (url === '/auth/login') return res(200);
      configCalls += 1;
      return configCalls === 1 ? res(401) : retried;
    },
  });
  assert.strictEqual(await wrapped('/api/config'), retried);
  assert.strictEqual(fakePrompt.mock.callCount(), 1);
  assert.strictEqual(callsTo(fakeFetch, '/api/config').length, 2);
  const [login] = callsTo(fakeFetch, '/auth/login');
  assert.strictEqual(login.arguments[1].method, 'POST');
  assert.strictEqual(login.arguments[1].headers['Content-Type'], 'application/json');
  assert.strictEqual(login.arguments[1].body, JSON.stringify({ token: 'secret' }));
});

test('401s on /auth/ URLs, non-string inputs and non-root URLs are returned as-is', async () => {
  const unauthorized = res(401);
  const { wrapped, fakePrompt } = load({ fetchImpl: async () => unauthorized });
  assert.strictEqual(await wrapped('/auth/login'), unauthorized);
  assert.strictEqual(await wrapped({ url: '/api/config' }), unauthorized);
  assert.strictEqual(await wrapped('https://example.com/api'), unauthorized);
  assert.strictEqual(fakePrompt.mock.callCount(), 0);
});

test('cancelling the prompt throws Not signed in', async () => {
  for (const cancelled of [null, '']) {
    const { wrapped } = load({ prompts: [cancelled], fetchImpl: async () => res(401) });
    await assert.rejects(wrapped('/api/config'), /Not signed in\. Reload the page to enter the access token\./);
  }
});

test('three rejected tokens prompt three times, then throw Not signed in', async () => {
  const { wrapped, fakePrompt } = load({
    prompts: ['a', 'b', 'c', 'd'],
    fetchImpl: async () => res(401),
  });
  await assert.rejects(wrapped('/api/config'), /Not signed in/);
  assert.strictEqual(fakePrompt.mock.callCount(), 3);
  assert.strictEqual(fakePrompt.mock.calls[1].arguments[0], 'That token was not accepted. Try again:');
  assert.strictEqual(fakePrompt.mock.calls[2].arguments[0], 'That token was not accepted. Try again:');
});

test('a 429 from login surfaces the server message or a default', async () => {
  const withMessage = load({
    prompts: ['x'],
    fetchImpl: async (url) => (url === '/auth/login' ? res(429, { error: 'Slow down' }) : res(401)),
  });
  await assert.rejects(withMessage.wrapped('/api/config'), /Slow down/);

  const withoutMessage = load({
    prompts: ['x'],
    fetchImpl: async (url) => (url === '/auth/login' ? res(429, {}) : res(401)),
  });
  await assert.rejects(withoutMessage.wrapped('/api/config'), /Too many failed attempts\. Try again later\./);
});
