const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const { startServer } = require('./helpers');

const REAL = { GOOGLE_CLIENT_ID: 'test-client.apps.example', GOOGLE_CLIENT_SECRET: 'test-secret' };

test('demo mode: demo code links a mock account into the demo store only', async (t) => {
  const s = await startServer({});
  t.after(() => s.stop());
  const res = await fetch(`${s.base}/oauth2callback?code=mock_demo_auth_code`);
  assert.strictEqual(res.status, 200);
  assert.ok(fs.existsSync(path.join(s.dataDir, 'tokens.demo.json')));
  assert.ok(!fs.existsSync(path.join(s.dataDir, 'tokens.json')));
  const cfg = await (await fetch(`${s.base}/api/config`)).json();
  assert.strictEqual(cfg.isDemoMode, true);
  assert.strictEqual(cfg.connectedAccounts.length, 1);
});

test('real mode: the demo code does not create an account', async (t) => {
  const s = await startServer(REAL);
  t.after(() => s.stop());
  const res = await fetch(`${s.base}/oauth2callback?code=mock_demo_auth_code`);
  assert.notStrictEqual(res.status, 200);
  assert.ok(!fs.existsSync(path.join(s.dataDir, 'tokens.demo.json')));
  assert.ok(!fs.existsSync(path.join(s.dataDir, 'tokens.json')));
  const cfg = await (await fetch(`${s.base}/api/config`)).json();
  assert.strictEqual(cfg.isDemoMode, false);
  assert.deepStrictEqual(cfg.connectedAccounts, []);
});

test('real mode: demo- account names do not get mock API responses', async (t) => {
  const s = await startServer(REAL);
  t.after(() => s.stop());
  const gmail = await fetch(`${s.base}/api/gmail/list?email=demo-someone@example.com`);
  assert.strictEqual(gmail.status, 500);
  const body = await gmail.json();
  assert.ok(!body.messages);

  const drive = await fetch(`${s.base}/api/drive/log`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: 'demo-someone@example.com', logMessage: 'x' })
  });
  assert.strictEqual(drive.status, 500);
});

test('demo mode: demo- accounts still get mock responses', async (t) => {
  const s = await startServer({});
  t.after(() => s.stop());
  const res = await fetch(`${s.base}/api/gmail/list?email=demo-someone@example.com`);
  assert.strictEqual(res.status, 200);
  assert.strictEqual((await res.json()).messages.length, 3);
});
