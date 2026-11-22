const test = require('node:test');
const assert = require('node:assert');
const crypto = require('crypto');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { startServer } = require('./helpers');

const KEY = 'test-encryption-key-for-unit-tests-only';
// Real-credential fixtures: the real (non-demo) token store is tokens.json.
const REAL = { ENCRYPTION_KEY: KEY, GOOGLE_CLIENT_ID: 'test-client.apps.example', GOOGLE_CLIENT_SECRET: 'test-secret' };
const TOKENS = { 'person@example.com': { access_token: 'secret-access-value', refresh_token: 'secret-refresh-value', expiry_date: 1 } };

// The format used by earlier versions, kept here to build fixtures.
function legacyEncrypt(text, secret) {
  const key = crypto.createHash('sha256').update(secret).digest();
  const iv = crypto.randomBytes(16);
  const cipher = crypto.createCipheriv('aes-256-cbc', key, iv);
  return iv.toString('hex') + ':' + Buffer.concat([cipher.update(text), cipher.final()]).toString('hex');
}

function seededDir() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'gcp-store-'));
  fs.writeFileSync(path.join(dir, 'tokens.json'), legacyEncrypt(JSON.stringify(TOKENS), KEY));
  return dir;
}

async function accounts(base) {
  return (await (await fetch(`${base}/api/config`)).json()).connectedAccounts.map((a) => a.email);
}

// Starts against a legacy store, lets it migrate, and returns the directory.
async function migratedDir() {
  const dir = seededDir();
  const s = await startServer({ ...REAL, DATA_DIR: dir });
  try {
    assert.deepStrictEqual(await accounts(s.base), ['person@example.com']);
  } finally {
    await s.stop();
  }
  return dir;
}

// Runs fn against a server and always stops it, even if an assertion fails.
async function withServer(env, fn) {
  const s = await startServer(env);
  try {
    return await fn(s);
  } finally {
    await s.stop();
  }
}

test('a legacy store is read and rewritten in the authenticated format', async (t) => {
  const dir = seededDir();
  const s = await startServer({ ...REAL, DATA_DIR: dir });
  t.after(() => s.stop());
  assert.deepStrictEqual(await accounts(s.base), ['person@example.com']);
  assert.match(s.getOutput(), /Migrated the token store/);

  const file = fs.readFileSync(path.join(dir, 'tokens.json'), 'utf8');
  const parts = file.split(':');
  assert.strictEqual(parts[0], 'v2');
  assert.strictEqual(parts.length, 5);
  assert.strictEqual(parts[1].length, 32); // 16-byte salt
  assert.strictEqual(parts[2].length, 24); // 12-byte GCM nonce
  assert.strictEqual(parts[3].length, 32); // 16-byte tag
  assert.ok(!file.includes('secret-refresh-value'));
  // Atomic write leaves no temporary files behind.
  assert.deepStrictEqual(fs.readdirSync(dir).filter((f) => f.endsWith('.tmp')), []);
  assert.ok(fs.existsSync(path.join(dir, 'tokens.json.v2')));
});

test('a migrated store survives a restart', async (t) => {
  const dir = await migratedDir();
  const s = await startServer({ ...REAL, DATA_DIR: dir });
  t.after(() => s.stop());
  assert.deepStrictEqual(await accounts(s.base), ['person@example.com']);
  assert.doesNotMatch(s.getOutput(), /Migrated the token store/);
});

test('legacy data is refused once the store has been migrated', async (t) => {
  const dir = await migratedDir();
  // Simulate a downgrade: the store is replaced by data in the old format.
  fs.writeFileSync(path.join(dir, 'tokens.json'), legacyEncrypt(JSON.stringify(TOKENS), KEY));
  const s = await startServer({ ...REAL, DATA_DIR: dir });
  t.after(() => s.stop());
  assert.deepStrictEqual(await accounts(s.base), []);
  assert.match(s.getOutput(), /refusing to read/);
});

test('tampered ciphertext, a short tag and a wrong key are rejected', async (t) => {
  const dir = await migratedDir();
  const file = path.join(dir, 'tokens.json');
  const good = fs.readFileSync(file, 'utf8');
  const parts = good.split(':');

  const flipped = (parts[4][0] === '0' ? '1' : '0') + parts[4].slice(1);
  fs.writeFileSync(file, [...parts.slice(0, 4), flipped].join(':'));
  await withServer({ ...REAL, DATA_DIR: dir }, async (s) => {
    assert.deepStrictEqual(await accounts(s.base), []);
  });

  fs.writeFileSync(file, [parts[0], parts[1], parts[2], parts[3].slice(0, 16), parts[4]].join(':'));
  await withServer({ ...REAL, DATA_DIR: dir }, async (s) => {
    assert.deepStrictEqual(await accounts(s.base), []);
    assert.match(s.getOutput(), /malformed encrypted data/);
  });

  fs.writeFileSync(file, good);
  await withServer({ ...REAL, ENCRYPTION_KEY: 'a-completely-different-key-value', DATA_DIR: dir }, async (s) => {
    assert.deepStrictEqual(await accounts(s.base), []);
  });
});

test('a missing marker is restored after a successful read', async () => {
  const dir = await migratedDir();
  const marker = path.join(dir, 'tokens.json.v2');
  fs.rmSync(marker);
  await withServer({ ...REAL, DATA_DIR: dir }, async (s) => {
    assert.deepStrictEqual(await accounts(s.base), ['person@example.com']);
  });
  assert.ok(fs.existsSync(marker), 'marker recreated');
  // ...so a later downgrade is refused again.
  fs.writeFileSync(path.join(dir, 'tokens.json'), legacyEncrypt(JSON.stringify(TOKENS), KEY));
  await withServer({ ...REAL, DATA_DIR: dir }, async (s) => {
    assert.deepStrictEqual(await accounts(s.base), []);
  });
});
