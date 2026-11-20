const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');

const root = path.join(__dirname, '..');

test('Dockerfile does not copy env or credential files into the image', () => {
  const dockerfile = fs.readFileSync(path.join(root, 'Dockerfile'), 'utf8');
  const copyLines = dockerfile.split('\n').filter((l) => /^\s*(COPY|ADD)\b/i.test(l));
  for (const line of copyLines) {
    assert.ok(!/\.env/.test(line), `unexpected env copy: ${line}`);
    assert.ok(!/client_secret/.test(line), `unexpected credential copy: ${line}`);
  }
});

test('.dockerignore excludes env files and credentials from the build context', () => {
  const entries = fs.readFileSync(path.join(root, '.dockerignore'), 'utf8')
    .split('\n').map((l) => l.trim()).filter(Boolean);
  for (const required of ['.env', '.env.*', 'client_secrets.json', 'data/']) {
    assert.ok(entries.includes(required), `.dockerignore is missing ${required}`);
  }
});
