/* ═══════════════════════════════════════════════════════════════
   js/config.js — RedVerse shared API configuration
   ═══════════════════════════════════════════════════════════════ */

// Base URL for API requests — always matches the server that served this page.
// Sub-pages that talk to a *separate* backend (e.g. Ollama on :8666) define
// their own local constant and never rely on this one.
var API_BASE = (function () {
  return window.location.origin;
})();
