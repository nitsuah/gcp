const { spawn } = require('child_process');
const fs = require('fs');
const http = require('http');
const net = require('net');
const os = require('os');
const path = require('path');

function freePort() {
  return new Promise((resolve, reject) => {
    const srv = net.createServer();
    srv.listen(0, '127.0.0.1', () => {
      const { port } = srv.address();
      srv.close(() => resolve(port));
    });
    srv.on('error', reject);
  });
}

function spawnServer(env) {
  const dataDir = env.DATA_DIR || fs.mkdtempSync(path.join(os.tmpdir(), 'gcp-test-'));
  const merged = {
    PATH: process.env.PATH,
    DATA_DIR: dataDir,
    ENCRYPTION_KEY: 'test-encryption-key-for-unit-tests-only',
    // Keep every spawned test server out of developer-local OAuth credentials.
    GOOGLE_CLIENT_SECRETS_PATH: path.join(dataDir, 'missing-client-secrets.json'),
    ...env
  };
  for (const k of Object.keys(merged)) if (merged[k] === undefined) delete merged[k];
  const child = spawn(process.execPath, [path.join(__dirname, '..', 'server.js')], {
    env: merged,
    cwd: dataDir
  });
  let output = '';
  child.stdout.on('data', (d) => { output += d; });
  child.stderr.on('data', (d) => { output += d; });
  return { child, dataDir, getOutput: () => output };
}

/** Starts the server on a free loopback port and resolves once it is listening. */
async function startServer(env = {}) {
  const port = await freePort();
  const s = spawnServer({ PORT: String(port), ...env });
  await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('server did not start: ' + s.getOutput())), 10000);
    const check = setInterval(() => {
      if (/listening on/.test(s.getOutput())) { clearTimeout(timer); clearInterval(check); resolve(); }
    }, 25);
    s.child.on('exit', () => { clearTimeout(timer); clearInterval(check); reject(new Error('server exited: ' + s.getOutput())); });
  });
  return {
    port,
    base: `http://127.0.0.1:${port}`,
    dataDir: s.dataDir,
    getOutput: s.getOutput,
    stop: () => new Promise((resolve) => { s.child.once('exit', resolve); s.child.kill(); })
  };
}

/** Runs the server expecting it to exit on its own; resolves with exit code and output. */
async function runUntilExit(env = {}) {
  const port = await freePort();
  const s = spawnServer({ PORT: String(port), ...env });
  return new Promise((resolve) => {
    const timer = setTimeout(() => { s.child.kill(); resolve({ code: null, output: s.getOutput() }); }, 8000);
    s.child.on('exit', (code) => { clearTimeout(timer); resolve({ code, output: s.getOutput() }); });
  });
}

/** Minimal request helper that allows overriding the Host header (fetch forbids it). */
function request(base, urlPath, { method = 'GET', headers = {}, body } = {}) {
  return new Promise((resolve, reject) => {
    const u = new URL(urlPath, base);
    const req = http.request({ hostname: u.hostname, port: u.port, path: u.pathname + u.search, method, headers }, (res) => {
      let data = '';
      res.on('data', (d) => { data += d; });
      res.on('end', () => resolve({ status: res.statusCode, headers: res.headers, body: data }));
    });
    req.on('error', reject);
    if (body) req.write(body);
    req.end();
  });
}

module.exports = { startServer, runUntilExit, request };
