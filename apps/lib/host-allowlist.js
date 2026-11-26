const os = require('os');

function machineHostNames() {
  const names = [os.hostname().toLowerCase()];
  for (const addrs of Object.values(os.networkInterfaces())) {
    for (const a of addrs || []) {
      names.push(a.family === 'IPv6' || a.family === 6 ? `[${a.address.toLowerCase()}]` : a.address);
    }
  }
  return names;
}

/**
 * Build the Host-header allow-list and its Express middleware (DNS-rebinding guard).
 * @param {object} opts
 * @param {Set<string>} opts.loopbackHosts
 * @param {boolean} opts.isLoopbackBind
 * @param {string} [opts.allowedHostsEnv] comma-separated extra host names
 * @param {() => string[]} [opts.machineNames]
 */
function createHostCheck({ loopbackHosts, isLoopbackBind, allowedHostsEnv = '', machineNames = () => [] }) {
  const configuredHosts = (allowedHostsEnv || '').split(',').map(h => h.trim().toLowerCase()).filter(Boolean);
  const allowedHosts = new Set([
    ...loopbackHosts,
    ...configuredHosts,
    ...(!isLoopbackBind && !configuredHosts.length ? machineNames() : [])
  ]);
  function hostCheck(req, res, next) {
    const host = (req.get('host') || '').toLowerCase().replace(/:\d+$/, '');
    if (allowedHosts.has(host)) return next();
    res.status(403).json({ error: 'Host not allowed. Add the host name clients use to ALLOWED_HOSTS.' });
  }
  return { allowedHosts, hostCheck };
}

module.exports = { createHostCheck, machineHostNames };
