const test = require('node:test');
const assert = require('node:assert');
const crypto = require('crypto');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { startServer } = require('./helpers');

const KEY = 'test-encryption-key-for-unit-tests-only';
const TOKENS = { 'person@example.com': { access_token: 'secret-access-value', refresh_token: 'secret-refresh-value', expiry_date: 1 } };

// The format used by earlier versions, kept here to build fixtures.
function legacyEncrypt(text, secret) {
  const key = crypto.createHash('sha256').update(secret).digest();
  const iv = crypto.randomBytes(16);
  const cipher = crypto.createCipheriv('aes-256-cbc', key, iv);
  return iv.toString('hex') + ':' + Buffer.concat([cipher.update(text), cipher.final()]).toString('hex');
}

function tmpDir() {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'gcp-store-'));
}

async function accounts(base) {
  return (await (await fetch(`${base}/api/config`)).json()).connectedAccounts.map((a) => a.email);
}

test('new writes use the authenticated format and are not readable as plaintext', async (t) => {
  const s = await startServer({ ENCRYPTION_KEY: KEY });
  t.after(() => s.stop());
  await fetch(`${s.base}/oauth2callback?code=mock_demo_auth_code`);
  const file = fs.readFileSync(path.join(s.dataDir, 'tokens.json'), 'utf8');
  const parts = file.split(':');
  assert.strictEqual(parts[0], 'v2');
  assert.strictEqual(parts.length, 5);
  assert.strictEqual(parts[1].length, 32); // 16-byte salt
  assert.strictEqual(parts[2].length, 24); // 12-byte GCM nonce
  assert.strictEqual(parts[3].length, 32); // 16-byte tag
  assert.ok(!file.includes('mock_access_token'));
  assert.strictEqual((await accounts(s.base)).length, 1);
});

test('a store written in the previous format is read and migrated', async (t) => {
  const dir = tmpDir();
  fs.writeFileSync(path.join(dir, 'tokens.json'), legacyEncrypt(JSON.stringify(TOKENS), KEY));
  const s = await startServer({ ENCRYPTION_KEY: KEY, DATA_DIR: dir });
  t.after(() => s.stop());
  assert.deepStrictEqual(await accounts(s.base), ['person@example.com']);
  const migrated = fs.readFileSync(path.join(dir, 'tokens.json'), 'utf8');
  assert.ok(migrated.startsWith('v2:'));
  assert.ok(!migrated.includes('secret-refresh-value'));
  assert.deepStrictEqual(await accounts(s.base), ['person@example.com']);
});

test('a migrated store survives a restart', async (t) => {
  const dir = tmpDir();
  fs.writeFileSync(path.join(dir, 'tokens.json'), legacyEncrypt(JSON.stringify(TOKENS), KEY));
  const first = await startServer({ ENCRYPTION_KEY: KEY, DATA_DIR: dir });
  await accounts(first.base);
  await first.stop();
  const second = await startServer({ ENCRYPTION_KEY: KEY, DATA_DIR: dir });
  t.after(() => second.stop());
  assert.deepStrictEqual(await accounts(second.base), ['person@example.com']);
});

test('tampered ciphertext and a wrong key are rejected', async (t) => {
  const seed = await startServer({ ENCRYPTION_KEY: KEY });
  await fetch(`${seed.base}/oauth2callback?code=mock_demo_auth_code`);
  await seed.stop();
  const file = path.join(seed.dataDir, 'tokens.json');
  const good = fs.readFileSync(file, 'utf8');

  const parts = good.split(':');
  const flipped = (parts[4][0] === '0' ? '1' : '0') + parts[4].slice(1);
  fs.writeFileSync(file, [...parts.slice(0, 4), flipped].join(':'));
  const tampered = await startServer({ ENCRYPTION_KEY: KEY, DATA_DIR: seed.dataDir });
  assert.deepStrictEqual(await accounts(tampered.base), []);
  await tampered.stop();

  fs.writeFileSync(file, good);
  const wrongKey = await startServer({ ENCRYPTION_KEY: 'a-completely-different-key-value', DATA_DIR: seed.dataDir });
  t.after(() => wrongKey.stop());
  assert.deepStrictEqual(await accounts(wrongKey.base), []);
});
