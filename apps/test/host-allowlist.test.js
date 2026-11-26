const test = require('node:test');
const assert = require('node:assert');
const os = require('os');
const { createHostCheck, machineHostNames } = require('../lib/host-allowlist');

const LOOPBACK = new Set(['127.0.0.1', 'localhost', '::1', '[::1]']);

function run(check, host) {
  const req = { get: (h) => (h === 'host' ? host : undefined) };
  const res = {
    code: null,
    body: null,
    status(c) { this.code = c; return this; },
    json(b) { this.body = b; return this; },
  };
  let called = false;
  check(req, res, () => { called = true; });
  return { res, called };
}

test('loopback hosts are always allowed', () => {
  const { hostCheck, allowedHosts } = createHostCheck({ loopbackHosts: LOOPBACK, isLoopbackBind: true });
  for (const host of ['localhost', '127.0.0.1', '[::1]']) {
    assert.strictEqual(run(hostCheck, host).called, true, host);
    assert.ok(allowedHosts.has(host));
  }
});

test('the port is stripped and matching is case-insensitive', () => {
  const { hostCheck } = createHostCheck({ loopbackHosts: LOOPBACK, isLoopbackBind: true });
  assert.strictEqual(run(hostCheck, 'localhost:3000').called, true);
  assert.strictEqual(run(hostCheck, 'LocalHost').called, true);
});

test('unknown and empty hosts get a 403 with the ALLOWED_HOSTS hint', () => {
  const { hostCheck } = createHostCheck({ loopbackHosts: LOOPBACK, isLoopbackBind: true });
  for (const host of ['evil.example', '', undefined]) {
    const { res, called } = run(hostCheck, host);
    assert.strictEqual(called, false);
    assert.strictEqual(res.code, 403);
    assert.match(res.body.error, /ALLOWED_HOSTS/);
  }
});

test('ALLOWED_HOSTS entries are trimmed, lower-cased and empties dropped', () => {
  const { allowedHosts } = createHostCheck({
    loopbackHosts: LOOPBACK,
    isLoopbackBind: true,
    allowedHostsEnv: ' Foo.example , ,bar.example',
  });
  assert.deepStrictEqual([...allowedHosts].filter((h) => !LOOPBACK.has(h)), ['foo.example', 'bar.example']);
});

test('machine names are included only for a non-loopback bind with no configured hosts', () => {
  const machineNames = () => ['box.local', '10.0.0.5'];
  const open = createHostCheck({ loopbackHosts: LOOPBACK, isLoopbackBind: false, machineNames });
  assert.ok(open.allowedHosts.has('box.local'));
  assert.ok(open.allowedHosts.has('10.0.0.5'));

  const loopbackBind = createHostCheck({ loopbackHosts: LOOPBACK, isLoopbackBind: true, machineNames });
  assert.ok(!loopbackBind.allowedHosts.has('box.local'));

  const configured = createHostCheck({
    loopbackHosts: LOOPBACK,
    isLoopbackBind: false,
    allowedHostsEnv: 'app.example',
    machineNames,
  });
  assert.ok(!configured.allowedHosts.has('box.local'));
  assert.ok(configured.allowedHosts.has('app.example'));
});

test('machineHostNames returns an array containing the lower-cased host name', () => {
  const names = machineHostNames();
  assert.ok(Array.isArray(names));
  assert.ok(names.includes(os.hostname().toLowerCase()));
});
