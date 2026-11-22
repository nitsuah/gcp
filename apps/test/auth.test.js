const test = require('node:test');
const assert = require('node:assert');
const { startServer, runUntilExit, request } = require('./helpers');

const TOKEN = 'test-access-token-0123456789';

test('API and OAuth routes require the access token', async (t) => {
  const s = await startServer({ APP_AUTH_TOKEN: TOKEN });
  t.after(() => s.stop());

  assert.strictEqual((await fetch(`${s.base}/api/config`)).status, 401);
  assert.strictEqual((await fetch(`${s.base}/connect-google`, { redirect: 'manual' })).status, 401);
  assert.strictEqual((await fetch(`${s.base}/oauth2callback?code=x`)).status, 401);
  assert.strictEqual((await fetch(`${s.base}/api/config`, { headers: { Authorization: 'Bearer wrong' } })).status, 401);
  assert.strictEqual((await fetch(`${s.base}/api/config`, { headers: { Authorization: `Bearer ${TOKEN}` } })).status, 200);
  // Static dashboard shell stays reachable so it can prompt for the token.
  assert.strictEqual((await fetch(`${s.base}/`)).status, 200);
});

test('login issues a session cookie that unlocks the API', async (t) => {
  const s = await startServer({ APP_AUTH_TOKEN: TOKEN });
  t.after(() => s.stop());
  const headers = { 'Content-Type': 'application/json' };

  const bad = await fetch(`${s.base}/auth/login`, { method: 'POST', headers, body: JSON.stringify({ token: 'nope' }) });
  assert.strictEqual(bad.status, 401);

  const ok = await fetch(`${s.base}/auth/login`, { method: 'POST', headers, body: JSON.stringify({ token: TOKEN }) });
  assert.strictEqual(ok.status, 200);
  const cookie = ok.headers.get('set-cookie');
  assert.match(cookie, /HttpOnly/i);
  assert.match(cookie, /SameSite=Lax/i);
  assert.ok(!cookie.includes(TOKEN), 'cookie must not contain the raw token');

  const res = await fetch(`${s.base}/api/config`, { headers: { Cookie: cookie.split(';')[0] } });
  assert.strictEqual(res.status, 200);
});

test('a generated one-time token is printed when none is configured', async (t) => {
  const s = await startServer({});
  t.after(() => s.stop());
  assert.strictEqual((await fetch(`${s.base}/api/config`)).status, 401);
  const printed = /\[AUTH\]\s+([0-9a-f]{48})/.exec(s.getOutput());
  assert.ok(printed, 'token should be printed at startup');
  const res = await fetch(`${s.base}/api/config`, { headers: { Authorization: `Bearer ${printed[1]}` } });
  assert.strictEqual(res.status, 200);
});

test('binds to loopback by default', async (t) => {
  const s = await startServer({ APP_AUTH_TOKEN: TOKEN });
  t.after(() => s.stop());
  assert.match(s.getOutput(), /listening on http:\/\/127\.0\.0\.1:/);
});

test('a non-loopback bind without a token is refused', async () => {
  const r = await runUntilExit({ HOST: '0.0.0.0' });
  assert.strictEqual(r.code, 1);
  assert.match(r.output, /APP_AUTH_TOKEN is required/);
});

test('a non-loopback bind with a token starts', async (t) => {
  const s = await startServer({ HOST: '0.0.0.0', APP_AUTH_TOKEN: TOKEN });
  t.after(() => s.stop());
  assert.strictEqual((await fetch(`${s.base}/api/config`)).status, 401);
});

test('opting out of auth is only allowed on loopback', async (t) => {
  const refused = await runUntilExit({ HOST: '0.0.0.0', APP_AUTH_DISABLED: '1' });
  assert.strictEqual(refused.code, 1);

  const s = await startServer({ APP_AUTH_DISABLED: '1' });
  t.after(() => s.stop());
  assert.strictEqual((await fetch(`${s.base}/api/config`)).status, 200);
});

test('unexpected Host headers are rejected on a loopback bind', async (t) => {
  const s = await startServer({ APP_AUTH_TOKEN: TOKEN });
  t.after(() => s.stop());
  const headers = { Authorization: `Bearer ${TOKEN}` };
  const bad = await request(s.base, '/api/config', { headers: { ...headers, Host: 'evil.example' } });
  assert.strictEqual(bad.status, 403);
  const good = await request(s.base, '/api/config', { headers: { ...headers, Host: `localhost:${s.port}` } });
  assert.strictEqual(good.status, 200);
});

test('a malformed cookie is ignored instead of failing the request', async (t) => {
  const s = await startServer({ APP_AUTH_TOKEN: TOKEN });
  t.after(() => s.stop());
  const res = await fetch(`${s.base}/api/config`, { headers: { Cookie: 'junk=%GG; other=1' } });
  assert.strictEqual(res.status, 401);
});

test('TRUST_PROXY marks the session cookie Secure behind a TLS proxy', async (t) => {
  const s = await startServer({ APP_AUTH_TOKEN: TOKEN, TRUST_PROXY: 'loopback' });
  t.after(() => s.stop());
  const res = await fetch(`${s.base}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Forwarded-Proto': 'https' },
    body: JSON.stringify({ token: TOKEN }),
  });
  assert.strictEqual(res.status, 200);
  assert.match(res.headers.get('set-cookie'), /;\s*Secure/i);
});

test('repeated failed logins from one address are throttled', async (t) => {
  const s = await startServer({ APP_AUTH_TOKEN: TOKEN });
  t.after(() => s.stop());
  const headers = { 'Content-Type': 'application/json' };
  const statuses = [];
  for (let i = 0; i < 11; i++) {
    statuses.push((await fetch(`${s.base}/auth/login`, { method: 'POST', headers, body: JSON.stringify({ token: 'wrong-token-value' }) })).status);
  }
  assert.deepStrictEqual(statuses.slice(0, 10), Array(10).fill(401));
  assert.strictEqual(statuses[10], 429);
  // Even the right token waits out the window.
  const right = await fetch(`${s.base}/auth/login`, { method: 'POST', headers, body: JSON.stringify({ token: TOKEN }) });
  assert.strictEqual(right.status, 429);
});

test('a non-loopback bind still rejects unexpected Host headers', async (t) => {
  const s = await startServer({ APP_AUTH_TOKEN: TOKEN, HOST: '0.0.0.0' });
  t.after(() => s.stop());
  const headers = { Authorization: `Bearer ${TOKEN}` };
  const bad = await request(s.base, '/api/config', { headers: { ...headers, Host: 'evil.example' } });
  assert.strictEqual(bad.status, 403);
  const local = await request(s.base, '/api/config', { headers: { ...headers, Host: `localhost:${s.port}` } });
  assert.strictEqual(local.status, 200);
});

test('ALLOWED_HOSTS admits a configured host name on a non-loopback bind', async (t) => {
  const s = await startServer({ APP_AUTH_TOKEN: TOKEN, HOST: '0.0.0.0', ALLOWED_HOSTS: 'dash.example' });
  t.after(() => s.stop());
  const headers = { Authorization: `Bearer ${TOKEN}` };
  const ok = await request(s.base, '/api/config', { headers: { ...headers, Host: 'dash.example' } });
  assert.strictEqual(ok.status, 200);
});
