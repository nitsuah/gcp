const test = require('node:test');
const assert = require('node:assert');
const { startServer } = require('./helpers');

const TOKEN = 'test-access-token-0123456789';

const authed = (url, init = {}) =>
  fetch(url, {
    ...init,
    headers: {
      Authorization: `Bearer ${TOKEN}`,
      'Content-Type': 'application/json',
      ...(init.headers || {})
    }
  });

const unauthed = (url, init = {}) =>
  fetch(url, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init.headers || {})
    }
  });

test('config routes require authentication', async (t) => {
  const s = await startServer({ APP_AUTH_TOKEN: TOKEN });
  t.after(() => s.stop());

  const driveLoggingRes = await unauthed(`${s.base}/api/config/drive-logging`, {
    method: 'POST',
    body: JSON.stringify({ enabled: true })
  });
  assert.strictEqual(driveLoggingRes.status, 401);

  const disconnectRes = await unauthed(`${s.base}/api/accounts/disconnect`, {
    method: 'POST',
    body: JSON.stringify({ email: 'test@example.com' })
  });
  assert.strictEqual(disconnectRes.status, 401);
});

test('drive-logging toggles and GET /api/config reflects the value', async (t) => {
  const s = await startServer({ APP_AUTH_TOKEN: TOKEN });
  t.after(() => s.stop());

  // Enable drive logging
  let res = await authed(`${s.base}/api/config/drive-logging`, {
    method: 'POST',
    body: JSON.stringify({ enabled: true })
  });
  assert.strictEqual(res.status, 200);
  const enabledBody = await res.json();
  assert.strictEqual(enabledBody.success, true);
  assert.strictEqual(enabledBody.driveLoggingEnabled, true);

  // Verify via GET /api/config
  const cfgEnabled = await (await authed(`${s.base}/api/config`)).json();
  assert.strictEqual(cfgEnabled.driveLoggingEnabled, true);

  // Disable drive logging with explicit false
  res = await authed(`${s.base}/api/config/drive-logging`, {
    method: 'POST',
    body: JSON.stringify({ enabled: false })
  });
  assert.strictEqual(res.status, 200);
  const disabledBody = await res.json();
  assert.strictEqual(disabledBody.success, true);
  assert.strictEqual(disabledBody.driveLoggingEnabled, false);

  // Verify via GET /api/config
  const cfgDisabled = await (await authed(`${s.base}/api/config`)).json();
  assert.strictEqual(cfgDisabled.driveLoggingEnabled, false);

  // Disable drive logging with missing body (empty object)
  res = await authed(`${s.base}/api/config/drive-logging`, {
    method: 'POST',
    body: JSON.stringify({})
  });
  assert.strictEqual(res.status, 200);
  const missingBody = await res.json();
  assert.strictEqual(missingBody.success, true);
  assert.strictEqual(missingBody.driveLoggingEnabled, false);

  // Verify via GET /api/config again
  const cfgMissing = await (await authed(`${s.base}/api/config`)).json();
  assert.strictEqual(cfgMissing.driveLoggingEnabled, false);
});

test('disconnect returns 404 for unknown account', async (t) => {
  const s = await startServer({ APP_AUTH_TOKEN: TOKEN });
  t.after(() => s.stop());

  const res = await authed(`${s.base}/api/accounts/disconnect`, {
    method: 'POST',
    body: JSON.stringify({ email: 'nobody@example.com' })
  });
  assert.strictEqual(res.status, 404);
  const body = await res.json();
  assert.strictEqual(body.error, 'Account not found');
});

test('disconnect removes a linked demo account and second attempt is 404', async (t) => {
  const s = await startServer({ APP_AUTH_TOKEN: TOKEN });
  t.after(() => s.stop());

  // Link a demo account
  const linkRes = await authed(`${s.base}/oauth2callback?code=mock_demo_auth_code`);
  assert.strictEqual(linkRes.status, 200);

  // Get the connected account email
  const cfg = await (await authed(`${s.base}/api/config`)).json();
  assert.strictEqual(cfg.isDemoMode, true);
  assert.strictEqual(cfg.connectedAccounts.length, 1);
  const email = cfg.connectedAccounts[0].email;

  // Disconnect the account
  const disconnectRes = await authed(`${s.base}/api/accounts/disconnect`, {
    method: 'POST',
    body: JSON.stringify({ email })
  });
  assert.strictEqual(disconnectRes.status, 200);
  const disconnectBody = await disconnectRes.json();
  assert.strictEqual(disconnectBody.success, true);

  // Verify account is removed
  const cfgAfter = await (await authed(`${s.base}/api/config`)).json();
  assert.deepStrictEqual(cfgAfter.connectedAccounts, []);

  // Second disconnect attempt returns 404
  const secondRes = await authed(`${s.base}/api/accounts/disconnect`, {
    method: 'POST',
    body: JSON.stringify({ email })
  });
  assert.strictEqual(secondRes.status, 404);
  const secondBody = await secondRes.json();
  assert.strictEqual(secondBody.error, 'Account not found');
});