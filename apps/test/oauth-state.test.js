const test = require('node:test');
const assert = require('node:assert');
const { startServer } = require('./helpers');

const REAL = { GOOGLE_CLIENT_ID: 'test-client.apps.example', GOOGLE_CLIENT_SECRET: 'test-secret' };

async function begin(base) {
  const res = await fetch(`${base}/connect-google`, { redirect: 'manual' });
  assert.strictEqual(res.status, 302);
  const url = new URL(res.headers.get('location'));
  const cookie = res.headers.get('set-cookie').split(';')[0];
  return { url, cookie, res };
}

test('authorization URL carries state and an S256 PKCE challenge', async (t) => {
  const s = await startServer(REAL);
  t.after(() => s.stop());
  const { url, res } = await begin(s.base);
  const state = url.searchParams.get('state');
  assert.match(state, /^[0-9a-f]{64}$/);
  assert.ok(url.searchParams.get('code_challenge'));
  assert.strictEqual(url.searchParams.get('code_challenge_method'), 'S256');
  const cookie = res.headers.get('set-cookie');
  assert.ok(cookie.startsWith(`oauth_state=${state}`));
  assert.match(cookie, /HttpOnly/i);
  assert.match(cookie, /SameSite=Lax/i);
});

test('each flow gets a fresh state and challenge', async (t) => {
  const s = await startServer(REAL);
  t.after(() => s.stop());
  const a = (await begin(s.base)).url.searchParams;
  const b = (await begin(s.base)).url.searchParams;
  assert.notStrictEqual(a.get('state'), b.get('state'));
  assert.notStrictEqual(a.get('code_challenge'), b.get('code_challenge'));
});

test('callback rejects missing, mismatched and unbound state', async (t) => {
  const s = await startServer(REAL);
  t.after(() => s.stop());
  const { url, cookie } = await begin(s.base);
  const state = url.searchParams.get('state');

  assert.strictEqual((await fetch(`${s.base}/oauth2callback?code=abc`)).status, 400);
  assert.strictEqual((await fetch(`${s.base}/oauth2callback?code=abc&state=${'0'.repeat(64)}`, { headers: { Cookie: cookie } })).status, 400);
  // Correct state but without the browser-bound cookie (e.g. a link opened by someone else).
  assert.strictEqual((await fetch(`${s.base}/oauth2callback?code=abc&state=${state}`)).status, 400);
});

test('state is single use', async (t) => {
  const s = await startServer(REAL);
  t.after(() => s.stop());
  const { url, cookie } = await begin(s.base);
  const state = url.searchParams.get('state');
  const target = `${s.base}/oauth2callback?code=abc&state=${state}`;

  const first = await fetch(target, { headers: { Cookie: cookie } });
  assert.notStrictEqual(first.status, 400, 'a valid state proceeds to the token exchange');
  const second = await fetch(target, { headers: { Cookie: cookie } });
  assert.strictEqual(second.status, 400);
});
