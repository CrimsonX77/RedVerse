/**
 * ═══════════════════════════════════════════════════════════════════════════
 *  REDVERSE-AUTH.JS — Phase 2 Aurora Integration
 *  JWT-based Authentication, Per-User Memory, and Gate-Based Access Control
 *
 *  Replaces Supabase with Aurora Memory API (Phase 2A/2B/2C)
 *  Integrates: Google OAuth, JWT Tokens, Tier 1-7 System, Admin Oversight
 *
 *  Usage: <script src="frontgate/redverse-auth.js"></script>
 * ═══════════════════════════════════════════════════════════════════════════
 */

const RedVerseAuth = (function() {
  'use strict';

  // ═══════════════════════════════════════════════════════════════════════
  //  CONFIGURATION — Phase 2 Aurora System
  // ═══════════════════════════════════════════════════════════════════════

  const API_BASE = 'http://localhost:5000/api';
  const GOOGLE_CLIENT_ID = '23326348224-utv5ng3jq4u21ort7of2hgaed6hkql3u.apps.googleusercontent.com';

  // NEW Tier System (1-7 instead of old tier names)
  const TIER_LEVELS = {
    'wanderer':       1,    // Tier 1
    'seeker':         2,    // Tier 2
    'acolyte':        3,    // Tier 3
    'sage':           4,    // Tier 4
    'oracle':         5,    // Tier 5
    'sentinel':       6,    // Tier 6
    'archon':         7     // Tier 7
  };

  const TIER_TITLES = {
    1: 'Wanderer',
    2: 'Seeker',
    3: 'Acolyte',
    4: 'Sage',
    5: 'Oracle',
    6: 'Sentinel',
    7: 'Archon'
  };

  // Map old names to new tiers for backward compatibility
  const LEGACY_TIER_MAP = {
    'wanderer':       1,
    'acolyte':        3,
    'devotee':        4,
    'crimson_circle': 5
  };

  // ═══════════════════════════════════════════════════════════════════════
  //  STATE
  // ═══════════════════════════════════════════════════════════════════════

  let jwtToken = null;             // JWT session token from Aurora
  let currentUser = null;          // { member_id, thread_id, access_tier, display_name, email }
  let currentProfile = null;       // User profile data
  let sessionId = null;
  let initialized = false;

  // ═══════════════════════════════════════════════════════════════════════
  //  INITIALIZATION
  // ═══════════════════════════════════════════════════════════════════════

  async function init(options = {}) {
    if (initialized) return { user: currentUser, profile: currentProfile };

    try {
      // Check for JWT in sessionStorage (from google_auth.html or login)
      jwtToken = sessionStorage.getItem('aurora_session_jwt');

      if (jwtToken) {
        // Validate and load existing session
        const valid = await _validateSession();
        if (valid) {
          _enforceGates();
          return { user: currentUser, profile: currentProfile };
        } else {
          sessionStorage.removeItem('aurora_session_jwt');
          jwtToken = null;
        }
      }

      sessionId = _generateSessionId();
      initialized = true;
      _enforceGates();
      return { user: null, profile: null };

    } catch (err) {
      console.error('[RedVerse] Init failed:', err);
      initialized = true;
      _enforceGates();
      return { user: null, profile: null };
    }
  }

  // ═══════════════════════════════════════════════════════════════════════
  //  JWT & SESSION MANAGEMENT
  // ═══════════════════════════════════════════════════════════════════════

  async function _validateSession() {
    if (!jwtToken) return false;

    try {
      // Decode JWT to extract user data (client-side only, no verification needed)
      const payload = JSON.parse(atob(jwtToken.split('.')[1]));

      // Check expiry
      if (payload.exp && Date.now() >= payload.exp * 1000) {
        return false;
      }

      // Load user data from decoded JWT
      currentUser = {
        member_id: payload.member_id,
        thread_id: payload.thread_id,
        access_tier: payload.access_tier,
        tier_name: payload.tier_name,
        display_name: payload.display_name,
        email: payload.email,
        is_admin: payload.is_admin || false,
        google_sub: payload.google_sub
      };

      currentProfile = { ...currentUser };
      _dispatchEvent('cathedral:auth', { event: 'session_restored', profile: currentProfile });
      return true;

    } catch (err) {
      console.warn('[RedVerse] JWT validation failed:', err);
      return false;
    }
  }

  function getAuthHeader() {
    return {
      'Authorization': `Bearer ${jwtToken}`,
      'Content-Type': 'application/json'
    };
  }

  // ═══════════════════════════════════════════════════════════════════════
  //  AUTHENTICATION — Google OAuth & Magic Links
  // ═══════════════════════════════════════════════════════════════════════

  /**
   * Initiate Google OAuth flow
   */
  async function signInWithGoogle(googleToken, email, name) {
    try {
      const response = await fetch(`${API_BASE}/auth/validate_google_token`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          google_token: googleToken,
          email: email,
          name: name
        })
      });

      if (!response.ok) {
        const err = await response.json();
        return { error: err.error || 'Google authentication failed' };
      }

      const data = await response.json();

      // Store JWT in sessionStorage
      jwtToken = data.session_token;
      sessionStorage.setItem('aurora_session_jwt', jwtToken);

      // Load user profile
      currentUser = {
        member_id: data.member_id,
        thread_id: data.thread_id,
        access_tier: data.access_tier,
        tier_name: data.tier_name,
        display_name: data.display_name,
        email: email,
        is_admin: data.is_admin || false
      };

      currentProfile = { ...currentUser };
      _enforceGates();
      _dispatchEvent('cathedral:auth', { event: 'signed_in', profile: currentProfile });

      return { data, success: true };

    } catch (err) {
      console.error('[RedVerse] Google auth error:', err);
      return { error: err.message };
    }
  }

  /**
   * Legacy password registration (if needed)
   */
  async function register(email, password, displayName) {
    // In Phase 2, we primarily use Google OAuth
    // Password registration could be added later if needed
    return { error: 'Use Google Sign-In to create an account' };
  }

  /**
   * Legacy password sign-in (if needed)
   */
  async function signIn(email, password) {
    return { error: 'Use Google Sign-In to access RedVerse' };
  }

  /**
   * Sign out — clear JWT and redirect
   */
  async function signOut() {
    sessionStorage.removeItem('aurora_session_jwt');
    jwtToken = null;
    currentUser = null;
    currentProfile = null;
    _enforceGates();
    _dispatchEvent('cathedral:auth', { event: 'signed_out' });
  }

  // ═══════════════════════════════════════════════════════════════════════
  //  PROFILE & TIER MANAGEMENT
  // ═══════════════════════════════════════════════════════════════════════

  function getTier() {
    if (!currentProfile) return 1;
    return currentProfile.access_tier || 1;
  }

  function getTierLevel() {
    return getTier();  // Direct numeric tier (1-7)
  }

  function getTierTitle() {
    return TIER_TITLES[getTier()] || 'Wanderer';
  }

  function hasAccess(requiredTier) {
    const required = typeof requiredTier === 'string'
      ? LEGACY_TIER_MAP[requiredTier] || TIER_LEVELS[requiredTier] || 1
      : requiredTier;
    return getTierLevel() >= required;
  }

  function isAuthenticated() {
    return currentUser !== null && jwtToken !== null;
  }

  function isAdmin() {
    return isAuthenticated() && (currentProfile?.is_admin || false);
  }

  function getProfile() {
    return currentProfile ? { ...currentProfile } : null;
  }

  function getJWT() {
    return jwtToken;
  }

  // ═══════════════════════════════════════════════════════════════════════
  //  GATE SYSTEM — Doors That Open Only for the Worthy
  // ═══════════════════════════════════════════════════════════════════════

  function _enforceGates() {
    const tierLevel = getTierLevel();
    const authed = isAuthenticated();

    document.querySelectorAll('[class*="gate-"]').forEach(el => {
      // Support both old names and new tier numbers
      let match = el.className.match(/gate-(wanderer|seeker|acolyte|sage|oracle|sentinel|archon)/);
      let requiredTier = null;

      if (match) {
        const tierName = match[1];
        requiredTier = LEGACY_TIER_MAP[tierName] || TIER_LEVELS[tierName] || 1;
      } else {
        // Also support numeric gates: gate-4, gate-5, etc.
        match = el.className.match(/gate-(\d+)/);
        if (match) {
          requiredTier = parseInt(match[1], 10);
        }
      }

      if (requiredTier === null) return;

      const isUnlocked = tierLevel >= requiredTier;

      if (isUnlocked) {
        el.classList.add('gate-unlocked');
        el.classList.remove('gate-locked');
        const overlay = el.querySelector('.gate-lock-overlay');
        if (overlay) overlay.style.display = 'none';
      } else {
        el.classList.add('gate-locked');
        el.classList.remove('gate-unlocked');
        _ensureGateLockOverlay(el, requiredTier);
      }
    });

    _updateAuthUI();
  }

  function _ensureGateLockOverlay(el, requiredTier) {
    if (el.querySelector('.gate-lock-overlay')) return;

    const overlay = document.createElement('div');
    overlay.className = 'gate-lock-overlay';

    const isAuthGate = !isAuthenticated() && requiredTier <= 3;  // Tiers 1-3 are entry level
    const sigil = isAuthGate ? '⛧' : '🔒';
    const tierName = TIER_TITLES[requiredTier] || 'Tier ' + requiredTier;
    const text = isAuthGate
      ? 'Sign in to enter'
      : `${tierName} covenant required`;
    const action = isAuthGate ? 'Sign In with Google' : 'Ascend your covenant';

    overlay.innerHTML = `
      <div class="gate-lock-content">
        <span class="gate-sigil">${sigil}</span>
        <span class="gate-text">${text}</span>
        <button class="gate-action-btn" data-gate-tier="${requiredTier}">${action}</button>
      </div>
    `;

    overlay.querySelector('.gate-action-btn').addEventListener('click', (e) => {
      e.stopPropagation();
      if (isAuthGate) {
        showRegistryModal();
      } else {
        showUpgradeModal(requiredTier);
      }
    });

    el.style.position = 'relative';
    el.appendChild(overlay);
  }

  function _updateAuthUI() {
    document.querySelectorAll('[data-auth-show]').forEach(el => {
      const show = el.dataset.authShow;
      if (show === 'authenticated') {
        el.style.display = isAuthenticated() ? '' : 'none';
      } else if (show === 'unauthenticated') {
        el.style.display = isAuthenticated() ? 'none' : '';
      } else if (show === 'admin') {
        el.style.display = isAdmin() ? '' : 'none';
      }
    });

    document.querySelectorAll('[data-profile-field]').forEach(el => {
      const field = el.dataset.profileField;
      if (currentProfile && currentProfile[field]) {
        el.textContent = currentProfile[field];
      }
    });

    document.querySelectorAll('.tier-badge').forEach(el => {
      el.textContent = getTierTitle();
      el.dataset.tier = getTier();
    });
  }

  // ═══════════════════════════════════════════════════════════════════════
  //  REGISTRY MODAL — Google OAuth
  // ═══════════════════════════════════════════════════════════════════════

  function showRegistryModal() {
    const existing = document.getElementById('cathedralRegistryModal');
    if (existing) existing.remove();

    const modal = document.createElement('div');
    modal.id = 'cathedralRegistryModal';
    modal.className = 'cathedral-modal-backdrop';
    modal.innerHTML = `
      <div class="cathedral-modal">
        <button class="modal-close" aria-label="Close">&times;</button>

        <div class="modal-header">
          <div class="modal-sigil">
            <svg viewBox="0 0 60 60" fill="none" xmlns="http://www.w3.org/2000/svg">
              <circle cx="30" cy="30" r="28" stroke="#c41230" stroke-width="0.8" opacity="0.5"/>
              <circle cx="30" cy="30" r="18" stroke="#c41230" stroke-width="0.5" opacity="0.3"/>
              <circle cx="30" cy="30" r="3" fill="#c41230" opacity="0.7"/>
              <line x1="30" y1="2" x2="30" y2="58" stroke="#c41230" stroke-width="0.3" opacity="0.2"/>
              <line x1="2" y1="30" x2="58" y2="30" stroke="#c41230" stroke-width="0.3" opacity="0.2"/>
            </svg>
          </div>
          <h2>The Cathedral Registry</h2>
          <p class="modal-subtitle">Your name echoes in these halls.<br>Sign in to be remembered.</p>
        </div>

        <div class="modal-body">
          <!-- Status message -->
          <div class="auth-status" id="authStatus"></div>

          <!-- Google OAuth Provider (Primary) -->
          <div class="auth-providers">
            <button class="auth-provider google-btn" id="googleSignInBtn" title="Google">
              <svg width="18" height="18" viewBox="0 0 24 24"><path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4"/><path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/><path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/><path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/></svg>
              <span>Sign In with Google</span>
            </button>
          </div>

          <div class="auth-divider">
            <span>Secured by Google & Aurora</span>
          </div>

          <p style="text-align: center; color: #7b6e68; font-size: 0.75rem; margin-top: 1rem;">
            Your memories are protected by per-user encrypted threads.<br>
            No third-party access. Your cathedral, your secrets.
          </p>
        </div>
      </div>
    `;

    document.body.appendChild(modal);

    const closeBtn = modal.querySelector('.modal-close');
    const googleBtn = modal.querySelector('#googleSignInBtn');
    const status = modal.querySelector('#authStatus');

    closeBtn.addEventListener('click', () => modal.remove());
    modal.addEventListener('click', (e) => {
      if (e.target === modal) modal.remove();
    });

    googleBtn.addEventListener('click', () => {
      status.textContent = 'Connecting to Google...';
      status.className = 'auth-status pending';

      // Redirect to Google OAuth flow
      // Note: In production, this would use Google Sign-In button or redirect to backend
      window.location.href = 'google_auth.html';
    });

    requestAnimationFrame(() => modal.classList.add('active'));
  }

  function showUpgradeModal(requiredTier) {
    const tierName = TIER_TITLES[requiredTier] || requiredTier;

    const existing = document.getElementById('cathedralUpgradeModal');
    if (existing) existing.remove();

    const modal = document.createElement('div');
    modal.id = 'cathedralUpgradeModal';
    modal.className = 'cathedral-modal-backdrop';
    modal.innerHTML = `
      <div class="cathedral-modal cathedral-modal-sm">
        <button class="modal-close" aria-label="Close">&times;</button>
        <div class="modal-header">
          <div class="modal-sigil-sm">🔒</div>
          <h2>Deeper Rites Await</h2>
          <p class="modal-subtitle">This chamber requires the <strong>${tierName}</strong> covenant (Tier ${requiredTier}).</p>
        </div>
        <div class="modal-body">
          <p class="upgrade-desc">
            The Cathedral holds deeper mysteries for those who pledge their devotion.
            Contact the Archivists to ascend your covenant.
          </p>
          <a href="mailto:support@redverse.local" class="auth-submit" style="display:block;text-align:center;text-decoration:none;">
            Request Access to Tier ${requiredTier}
          </a>
        </div>
      </div>
    `;

    document.body.appendChild(modal);

    modal.querySelector('.modal-close').addEventListener('click', () => modal.remove());
    modal.addEventListener('click', (e) => { if (e.target === modal) modal.remove(); });
    requestAnimationFrame(() => modal.classList.add('active'));
  }

  // ═══════════════════════════════════════════════════════════════════════
  //  PER-USER MEMORY — Aurora Memory System
  // ═══════════════════════════════════════════════════════════════════════

  /**
   * Store a memory event (message, emotion, etc.) to Aurora
   */
  async function recordMemory(role, content, emotionalState = null) {
    if (!isAuthenticated()) return;

    try {
      const response = await fetch(`${API_BASE}/memory/store`, {
        method: 'POST',
        headers: getAuthHeader(),
        body: JSON.stringify({
          role: role,
          content: content,
          source: 'frontgate',  // Track source
          emotion_state: emotionalState,
          metadata: { session_id: sessionId }
        })
      });

      if (!response.ok) {
        console.warn('[RedVerse] Memory store failed');
      }
    } catch (err) {
      console.warn('[RedVerse] Memory write failed:', err.message);
    }
  }

  /**
   * Load recent conversation history from Aurora
   */
  async function getRecentMemory(limit = 20) {
    if (!isAuthenticated()) return [];

    try {
      const response = await fetch(`${API_BASE}/memory/load`, {
        method: 'POST',
        headers: getAuthHeader(),
        body: JSON.stringify({ limit })
      });

      if (!response.ok) return [];

      const data = await response.json();
      return data.events || [];
    } catch (err) {
      console.warn('[RedVerse] Memory load failed:', err);
      return [];
    }
  }

  /**
   * Get conversation history formatted for AI injection
   */
  async function getConversationHistory(limit = 50) {
    if (!isAuthenticated()) return [];

    try {
      const response = await fetch(`${API_BASE}/memory/conversation_history`, {
        method: 'POST',
        headers: getAuthHeader(),
        body: JSON.stringify({ limit })
      });

      if (!response.ok) return [];

      const data = await response.json();
      return data.history || [];
    } catch (err) {
      console.warn('[RedVerse] History load failed:', err);
      return [];
    }
  }

  /**
   * Get memory stats for current user
   */
  async function getMemoryStats() {
    if (!isAuthenticated()) return null;

    try {
      const response = await fetch(`${API_BASE}/memory/stats`, {
        method: 'POST',
        headers: getAuthHeader(),
        body: JSON.stringify({})
      });

      if (!response.ok) return null;
      return await response.json();
    } catch (err) {
      console.warn('[RedVerse] Stats load failed:', err);
      return null;
    }
  }

  /**
   * Get memory prompt for LLM context injection
   */
  function getSableMemoryPrompt() {
    if (!currentProfile) {
      return '[No memory — first visit. Welcome this wanderer.]';
    }

    const parts = [
      '[RELATIONAL MEMORY — This visitor has history with the Cathedral]',
      `Visitor: ${currentProfile.display_name} (${getTierTitle()})`,
      `Tier: ${getTier()} | Thread: ${currentProfile.thread_id?.substring(0, 8)}...`
    ];

    return parts.join('\n');
  }

  // ═══════════════════════════════════════════════════════════════════════
  //  ADMIN FUNCTIONS
  // ═══════════════════════════════════════════════════════════════════════

  async function createAdminLink() {
    if (!isAdmin()) return null;
    return 'crimson-control-hall.html';
  }

  // ═══════════════════════════════════════════════════════════════════════
  //  UTILITIES
  // ═══════════════════════════════════════════════════════════════════════

  function _generateSessionId() {
    return 'rv-' + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 8);
  }

  function _dispatchEvent(name, detail) {
    window.dispatchEvent(new CustomEvent(name, { detail }));
  }

  // ═══════════════════════════════════════════════════════════════════════
  //  PUBLIC API
  // ═══════════════════════════════════════════════════════════════════════

  return {
    // Lifecycle
    init,

    // Auth
    signInWithGoogle,
    signOut,
    isAuthenticated,
    isAdmin,
    getProfile,
    getJWT,
    showRegistryModal,

    // Tiers & Gates
    getTier,
    getTierLevel,
    getTierTitle,
    hasAccess,
    showUpgradeModal,

    // Memory
    recordMemory,
    getRecentMemory,
    getConversationHistory,
    getMemoryStats,
    getSableMemoryPrompt,

    // Admin
    createAdminLink,

    // Constants
    TIER_LEVELS,
    TIER_TITLES,
    API_BASE
  };

})();

// Auto-initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  RedVerseAuth.init();
});

