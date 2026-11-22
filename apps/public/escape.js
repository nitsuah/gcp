// HTML-escaping helper shared by the dashboard (browser) and its tests (Node).
(function (root) {
  function escapeHtml(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = { escapeHtml };
  else root.escapeHtml = escapeHtml;
})(typeof window !== 'undefined' ? window : globalThis);
