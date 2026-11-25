const test = require('node:test');
const assert = require('node:assert');
const { startServer } = require('./helpers');

const TOKEN = 'test-access-token-0123456789';
const authed = (url, init = {}) =>
  fetch(url, { ...init, headers: { Authorization: `Bearer ${TOKEN}`, ...(init.headers || {}) } });

const DEMO_EMAIL = 'demo-a@example.com';

test('POST /api/calendar/create with summary', async (t) => {
  const s = await startServer({ APP_AUTH_TOKEN: TOKEN });
  t.after(() => s.stop());
  const res = await authed(`${s.base}/api/calendar/create`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: DEMO_EMAIL, summary: 'Standup' })
  });
  assert.strictEqual(res.status, 200);
  const data = await res.json();
  assert.strictEqual(data.success, true);
  assert.strictEqual(data.event.summary, 'Standup');
  assert.strictEqual(data.event.status, 'confirmed');
  assert.strictEqual(data.event.htmlLink, 'https://calendar.google.com/calendar/r/eventedit?text=Standup');
  assert.ok(data.event.description);
});

test('POST /api/calendar/create without summary', async (t) => {
  const s = await startServer({ APP_AUTH_TOKEN: TOKEN });
  t.after(() => s.stop());
  const res = await authed(`${s.base}/api/calendar/create`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: DEMO_EMAIL })
  });
  assert.strictEqual(res.status, 200);
  const data = await res.json();
  assert.strictEqual(data.success, true);
  assert.strictEqual(data.event.summary, 'Mock Demo Workspace Event');
  assert.strictEqual(data.event.htmlLink, 'https://calendar.google.com/calendar/r/eventedit?text=' + encodeURIComponent('Demo Event'));
});

test('POST /api/gemini/query with moon prompt', async (t) => {
  const s = await startServer({ APP_AUTH_TOKEN: TOKEN });
  t.after(() => s.stop());
  const res = await authed(`${s.base}/api/gemini/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: DEMO_EMAIL, prompt: 'How far is the moon?' })
  });
  assert.strictEqual(res.status, 200);
  const data = await res.json();
  assert.strictEqual(data.success, true);
  assert.ok(data.response.includes('384,400'));
});

test('POST /api/gemini/query without moon prompt', async (t) => {
  const s = await startServer({ APP_AUTH_TOKEN: TOKEN });
  t.after(() => s.stop());
  const res = await authed(`${s.base}/api/gemini/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: DEMO_EMAIL, prompt: 'What is 2+2?' })
  });
  assert.strictEqual(res.status, 200);
  const data = await res.json();
  assert.strictEqual(data.success, true);
  assert.ok(data.response.includes('What is 2+2?'));
  assert.ok(data.response.includes('Simulated Gemini'));
});

test('POST /api/drive/log with demo email', async (t) => {
  const s = await startServer({ APP_AUTH_TOKEN: TOKEN });
  t.after(() => s.stop());
  const res = await authed(`${s.base}/api/drive/log`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: DEMO_EMAIL })
  });
  assert.strictEqual(res.status, 200);
  const data = await res.json();
  assert.strictEqual(data.success, true);
  assert.strictEqual(data.fileId, 'mock_drive_file_id_571288');
});