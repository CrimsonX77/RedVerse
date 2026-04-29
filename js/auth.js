/* ═══════════════════════════════════════════════════════════════
   js/auth.js — RedVerse WaifuAuth client helper
   ═══════════════════════════════════════════════════════════════
   Usage (all pages that include js/config.js first):

     WaifuAuth.isAuthenticated()       → bool (sync)
     WaifuAuth.getUser()               → Promise<user|null>
     WaifuAuth.requireAuth()           → redirect to login.html when not authed
     WaifuAuth.logout()                → clear session + redirect
     WaifuAuth.setToken(token)         → store a server-issued token
     WaifuAuth.getStoredAuth()         → raw sessionStorage object (or null)
   ═══════════════════════════════════════════════════════════════ */

var WaifuAuth = (function () {
  'use strict';

  var SESSION_KEY = 'rv_auth';
  var TOKEN_KEY   = 'rv_token';

  function _base() {
    return (typeof API_BASE !== 'undefined') ? API_BASE : '';
  }

  // ── Storage helpers ───────────────────────────────────────────

  function getStoredAuth() {
    try {
      return JSON.parse(sessionStorage.getItem(SESSION_KEY) || 'null');
    } catch (e) {
      return null;
    }
  }

  function _saveAuth(obj) {
    sessionStorage.setItem(SESSION_KEY, JSON.stringify(obj));
  }

  // ── Public API ────────────────────────────────────────────────

  /**
   * Synchronous check — returns true if any auth record exists in
   * sessionStorage (including guest sessions).
   */
  function isAuthenticated() {
    var auth = getStoredAuth();
    return !!(auth && auth.auth_method);
  }

  /**
   * Async — resolves with a user object that has at minimum:
   *   { name, email, auth_method, display_name, access_tier }
   * Attempts to refresh from /auth/status if a server session exists.
   * Falls back gracefully to the sessionStorage data.
   */
  function getUser() {
    return new Promise(function (resolve) {
      var stored = getStoredAuth();
      if (!stored) { resolve(null); return; }

      fetch(_base() + '/auth/status', {
        credentials: 'include',
        signal: AbortSignal.timeout(3000),
      })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          var user;
          if (data.authenticated && data.user) {
            user = Object.assign({}, stored, data.user);
          } else {
            user = Object.assign({}, stored);
          }
          user.display_name = user.display_name ?? user.name ?? user.email ?? 'Wanderer';
          user.access_tier  = user.access_tier  ?? stored.access_tier ?? 1;
          resolve(user);
        })
        .catch(function () {
          var user = Object.assign({}, stored);
          user.display_name = user.display_name ?? user.name ?? user.email ?? 'Wanderer';
          user.access_tier  = user.access_tier  ?? 1;
          resolve(user);
        });
    });
  }

  /**
   * Store a server-issued token (called after OAuth backend verification).
   */
  function setToken(token) {
    sessionStorage.setItem(TOKEN_KEY, token);
    var auth = getStoredAuth() || {};
    auth.token = token;
    _saveAuth(auth);
  }

  /**
   * Retrieve the stored token (Bearer) for authenticated API calls.
   */
  function getToken() {
    return sessionStorage.getItem(TOKEN_KEY) || (getStoredAuth() || {}).token || null;
  }

  /**
   * Redirect to login.html if the user is not authenticated.
   * Should be called early in pages that require sign-in.
   */
  function requireAuth() {
    if (!isAuthenticated()) {
      window.location.href = 'login.html';
    }
  }

  /**
   * Sign out: clear sessionStorage, call the backend logout endpoint,
   * then redirect to login.html.
   */
  function logout() {
    sessionStorage.removeItem(SESSION_KEY);
    sessionStorage.removeItem(TOKEN_KEY);
    fetch(_base() + '/auth/logout', {
      method: 'POST',
      credentials: 'include',
    }).catch(function () {}).finally(function () {
      window.location.href = 'login.html';
    });
  }

  return {
    isAuthenticated : isAuthenticated,
    getUser         : getUser,
    setToken        : setToken,
    getToken        : getToken,
    requireAuth     : requireAuth,
    logout          : logout,
    getStoredAuth   : getStoredAuth,
  };
})();
