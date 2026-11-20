const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const { escapeHtml } = require('../public/escape.js');

test('escapeHtml neutralises markup and quotes', () => {
  assert.strictEqual(
    escapeHtml(`<img src=x onerror="a('b')">&`),
    '&lt;img src=x onerror=&quot;a(&#39;b&#39;)&quot;&gt;&amp;'
  );
  assert.strictEqual(escapeHtml(null), '');
  assert.strictEqual(escapeHtml(42), '42');
});

test('every dynamic value interpolated into innerHTML in app.js is escaped', () => {
  const src = fs.readFileSync(path.join(__dirname, '..', 'public', 'app.js'), 'utf8');
  const dynamic = [
    ...src.matchAll(/innerHTML\s*\+?=\s*`([\s\S]*?)`/g),
  ].flatMap((m) => [...m[1].matchAll(/\$\{([^}]*)\}/g)].map((x) => x[1].trim()));
  assert.ok(dynamic.length > 0);
  for (const expr of dynamic) {
    // colorClass is built from fixed strings; everything else must go through escapeHtml.
    assert.ok(expr === 'colorClass' || expr.startsWith('escapeHtml('), `unescaped interpolation: ${expr}`);
  }
  // The account card template is built with createElement + innerHTML, so check it too.
  assert.match(src, /escapeHtml\(account\.email\)/);
});

test('index.html loads the escape helper before the dashboard script', () => {
  const html = fs.readFileSync(path.join(__dirname, '..', 'public', 'index.html'), 'utf8');
  assert.ok(html.indexOf('escape.js') !== -1 && html.indexOf('escape.js') < html.indexOf('app.js'));
});
