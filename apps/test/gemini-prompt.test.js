const test = require('node:test');
const assert = require('node:assert');
const { startServer } = require('./helpers');

const TOKEN = 'test-access-token-0123456789';
const authed = (url, init = {}) =>
  fetch(url, { ...init, headers: { Authorization: `Bearer ${TOKEN}`, ...(init.headers || {}) } });

test('gemini query: missing prompt returns 200 with success and response string', async (t) => {
  const s = await startServer({ APP_AUTH_TOKEN: TOKEN });
  t.after(() => s.stop());
  const res = await authed(`${s.base}/api/gemini/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: 'demo-a@example.com' })
  });
  assert.strictEqual(res.status, 200);
  const body = await res.json();
  assert.strictEqual(body.success, true);
  assert.ok(typeof body.response === 'string' && body.response.length > 0);
});

test('gemini query: numeric prompt returns 200 with success and response string', async (t) => {
  const s = await startServer({ APP_AUTH_TOKEN: TOKEN });
  t.after(() => s.stop());
  const res = await authed(`${s.base}/api/gemini/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: 'demo-a@example.com', prompt: 42 })
  });
  assert.strictEqual(res.status, 200);
  const body = await res.json();
  assert.strictEqual(body.success, true);
  assert.ok(typeof body.response === 'string' && body.response.length > 0);
});

test('gemini query: normal prompt echoes in response', async (t) => {
  const s = await startServer({ APP_AUTH_TOKEN: TOKEN });
  t.after(() => s.stop());
  const res = await authed(`${s.base}/api/gemini/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: 'demo-a@example.com', prompt: 'Hello world' })
  });
  assert.strictEqual(res.status, 200);
  const body = await res.json();
  assert.strictEqual(body.success, true);
  assert.ok(body.response.includes('Hello world'));
});