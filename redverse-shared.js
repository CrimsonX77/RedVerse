/**
 * redverse-shared.js — RedVerse Platform Utilities
 * Include this in any page: <script src="/redverse-shared.js"></script>
 *
 * Exports on window.RV:
 *   RV.authGuard()          – redirect to login if not authenticated
 *   RV.getUser()            – cached current user { id, email, name, picture }
 *   RV.apiCall()            – fetch wrapper with auth + JSON helpers
 *   RV.gdm.remember()       – store a memory in the user's GDM field
 *   RV.gdm.recall()         – probabilistic recall from GDM field
 *   RV.gdm.status()         – field stats
 *   RV.trace()              – fire a trace event to Control Hall backend
 *   RV.nav.init()           – inject shared nav dropdowns from redverse-nav-dropdowns.html
 */

(function () {
  'use strict';

  /* ── Config ─────────────────────────────────── */
  const API_BASE         = '';          // same-origin Flask app
  const CONTROL_BASE     = 'http://127.0.0.1:8933'; // Control Hall backend
  const LOGIN_URL        = '/login.html';

  /* ── Internal cache ─────────────────────────── */
  let _userCache = null;

  /* ── Auth ───────────────────────────────────── */

  /**
   * Fetch the current authenticated user.
   * Returns null if not logged in (does NOT redirect).
   */
  async function getUser(force = false) {
    if (_userCache && !force) return _userCache;
    try {
      const r = await fetch(`${API_BASE}/api/me`, { credentials: 'include' });
      if (!r.ok) { _userCache = null; return null; }
      _userCache = await r.json();
      return _userCache;
    } catch {
      return null;
    }
  }

  /**
   * If the user is not authenticated, redirect to login immediately.
   * Optionally pass a returnUrl; defaults to current page.
   */
  async function authGuard(returnUrl) {
    const user = await getUser();
    if (!user) {
      const dest = returnUrl || window.location.href;
      window.location.href = `${LOGIN_URL}?next=${encodeURIComponent(dest)}`;
    }
    return user;
  }

  /* ── Generic API Caller ─────────────────────── */

  /**
   * Wrapper around fetch for the Flask API.
   * @param {string}  endpoint  e.g. '/api/gdm/status'
   * @param {string}  method    'GET' | 'POST' | 'PUT' | 'DELETE'
   * @param {object}  body      JSON payload (for POST/PUT)
   * @param {object}  options   Extra fetch options
   * @returns {Promise<any>}    Parsed JSON or throws
   */
  async function apiCall(endpoint, method = 'GET', body = null, options = {}) {
    const init = {
      method,
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      ...options,
    };
    if (body && method !== 'GET') init.body = JSON.stringify(body);
    const r = await fetch(`${API_BASE}${endpoint}`, init);
    if (!r.ok) {
      const text = await r.text().catch(() => '');
      throw Object.assign(new Error(`API ${method} ${endpoint} → ${r.status}`), { status: r.status, body: text });
    }
    return r.json();
  }

  /* ── GDM Helpers ─────────────────────────────── */

  const gdm = {
    /**
     * Get field stats for the current user's GDM instance.
     */
    status() {
      return apiCall('/api/gdm/status');
    },

    /**
     * Store a memory.
     * @param {string} content   The text to remember
     * @param {string} [role]    'user' | 'assistant' | 'system'
     * @param {object} [meta]    Arbitrary metadata
     */
    remember(content, role = 'user', meta = {}) {
      return apiCall('/api/gdm/remember', 'POST', { content, role, metadata: meta });
    },

    /**
     * Recall memories similar to a query.
     * @param {string} query     Search query
     * @param {number} [k]       Max results (default 5)
     * @param {number} [threshold] Min similarity 0-1 (default 0.0)
     */
    recall(query, k = 5, threshold = 0.0) {
      return apiCall('/api/gdm/recall', 'POST', { query, k, threshold });
    },
  };

  /* ── Trace Helper ────────────────────────────── */

  /**
   * Fire a trace event to the Control Hall backend (best-effort, never throws).
   * @param {string} level     'INFO' | 'WARN' | 'ERROR' | 'DEBUG'
   * @param {string} category  e.g. 'ui', 'auth', 'gdm', 'omnisensor'
   * @param {string} message   Human-readable description
   * @param {object} [data]    Optional structured payload
   */
  async function trace(level = 'INFO', category = 'ui', message = '', data = {}) {
    try {
      await fetch(`${CONTROL_BASE}/trace/event`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ level, category, message, data }),
        signal: AbortSignal.timeout(2000),
      });
    } catch { /* silent */ }
  }

  /* ── Nav Loader ──────────────────────────────── */

  const nav = {
    /**
     * Inject shared nav dropdowns into an element.
     * @param {string} selector CSS selector of target container (default '#nav-dropdowns')
     * @param {string} [src]    URL to fetch (default '/redverse-nav-dropdowns.html')
     */
    async init(selector = '#nav-dropdowns', src = '/redverse-nav-dropdowns.html') {
      const el = document.querySelector(selector);
      if (!el) return;
      try {
        const r = await fetch(src);
        if (!r.ok) return;
        el.innerHTML = await r.text();
      } catch { /* silent */ }
    },
  };

  /* ── OmniSensor Helpers ───────────────────────── */

  const omnisensor = {
    async status() {
      const r = await fetch(`${CONTROL_BASE}/omnisensor/status`, {
        signal: AbortSignal.timeout(2000),
      });
      if (!r.ok) throw new Error('omnisensor offline');
      return r.json();
    },
    async start() {
      const r = await fetch(`${CONTROL_BASE}/omnisensor/start`, {
        method: 'POST',
        signal: AbortSignal.timeout(5000),
      });
      if (!r.ok) throw new Error('start failed');
      return r.json();
    },
    async stop() {
      const r = await fetch(`${CONTROL_BASE}/omnisensor/stop`, {
        method: 'POST',
        signal: AbortSignal.timeout(5000),
      });
      if (!r.ok) throw new Error('stop failed');
      return r.json();
    },
  };

  /* ── Toast Notifications ────────────────────── */

  /**
   * Show a brief toast notification on screen.
   * Injects its own style + DOM element, no deps.
   * @param {string} message
   * @param {'info'|'success'|'error'|'warn'} [type]
   * @param {number} [duration] ms (default 3000)
   */
  function toast(message, type = 'info', duration = 3000) {
    if (!document.getElementById('rv-toast-style')) {
      const s = document.createElement('style');
      s.id = 'rv-toast-style';
      s.textContent = `
        #rv-toast-wrap{position:fixed;bottom:20px;right:20px;z-index:99999;display:flex;flex-direction:column;gap:8px;pointer-events:none;}
        .rv-toast{background:#1a0f1f;border:1px solid rgba(220,38,38,0.35);color:#e8dfe8;padding:10px 16px;border-radius:6px;
          font-family:'JetBrains Mono',monospace;font-size:12px;letter-spacing:0.04em;
          box-shadow:0 4px 20px rgba(0,0,0,0.5);opacity:0;transform:translateY(8px);
          transition:opacity 0.25s ease,transform 0.25s ease;pointer-events:none;}
        .rv-toast.show{opacity:1;transform:translateY(0);}
        .rv-toast.success{border-color:rgba(22,163,74,0.5);color:#4ade80;}
        .rv-toast.error  {border-color:rgba(220,38,38,0.7);color:#f87171;}
        .rv-toast.warn   {border-color:rgba(249,115,22,0.5);color:#fb923c;}
      `;
      document.head.appendChild(s);
    }
    let wrap = document.getElementById('rv-toast-wrap');
    if (!wrap) {
      wrap = document.createElement('div');
      wrap.id = 'rv-toast-wrap';
      document.body.appendChild(wrap);
    }
    const el = document.createElement('div');
    el.className = `rv-toast ${type}`;
    el.textContent = message;
    wrap.appendChild(el);
    requestAnimationFrame(() => { requestAnimationFrame(() => el.classList.add('show')); });
    setTimeout(() => {
      el.classList.remove('show');
      setTimeout(() => el.remove(), 300);
    }, duration);
  }

  /* ── Public API ─────────────────────────────── */
  window.RV = { authGuard, getUser, apiCall, gdm, trace, nav, omnisensor, toast };

})();
