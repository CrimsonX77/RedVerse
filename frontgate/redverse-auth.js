/**
 * ═══════════════════════════════════════════════════════════════════════════
 *  REDVERSE-AUTH.JS — The Cathedral Registry
 *  Authentication, Per-User Memory, and Gate-Based Access Control
 * 
 *  Dependencies: Supabase JS Client (loaded via CDN before this script)
 *  Usage: <script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"></script>
 *         <script src="redverse-auth.js"></script>
 * ═══════════════════════════════════════════════════════════════════════════
 */

const RedVerseAuth = (function() {
  'use strict';

  // ═══════════════════════════════════════════════════════════════════════
  //  CONFIGURATION
  //  Replace these with your actual Supabase project credentials.
  //  The anon key is safe for client-side use — RLS protects the data.
  // ═══════════════════════════════════════════════════════════════════════

  const SUPABASE_URL  = 'https://YOUR_PROJECT.supabase.co';  // TODO: Replace
  const SUPABASE_ANON = 'YOUR_ANON_KEY';                      // TODO: Replace

  // Tier hierarchy (higher index = more access)
  const TIER_LEVELS = {
    'wanderer':       0,
    'acolyte':        1,
    'devotee':        2,
    'crimson_circle':  3
  };

  const TIER_TITLES = {
    'wanderer':       'Wanderer',
    'acolyte':        'Acolyte',
    'devotee':        'Devotee',
    'crimson_circle':  'Crimson Circle'
  };

  // ═══════════════════════════════════════════════════════════════════════
  //  STATE
  // ═══════════════════════════════════════════════════════════════════════

  let supabase = null;
  let currentUser = null;       // Supabase auth user
  let currentProfile = null;    // profiles table row
  let sableContext = null;      // sable_context table row
  let sessionId = null;
  let initialized = false;

  // ═══════════════════════════════════════════════════════════════════════
  //  INITIALIZATION
  // ═══════════════════════════════════════════════════════════════════════

  async function init(options = {}) {
    if (initialized) return { user: currentUser, profile: currentProfile };

    const url  = options.supabaseUrl  || SUPABASE_URL;
    const anon = options.supabaseAnon || SUPABASE_ANON;

    if (url.includes('YOUR_PROJECT')) {
      console.warn('[Cathedral] Supabase not configured. Running in local/demo mode.');
      initialized = true;
      _enforceGates();
      return { user: null, profile: null };
    }

    try {
      supabase = window.supabase.createClient(url, anon);
      sessionId = _generateSessionId();

      // Check existing session
      const { data: { session } } = await supabase.auth.getSession();
      if (session) {
        currentUser = session.user;
        await _loadProfile();
        await _loadSableContext();
        _trackVisit();
      }

      // Listen for auth changes (login, logout, token refresh)
      supabase.auth.onAuthStateChange(async (event, session) => {
        if (event === 'SIGNED_IN' && session) {
          currentUser = session.user;
          await _loadProfile();
          await _loadSableContext();
          _trackVisit();
          _enforceGates();
          _dispatchEvent('cathedral:auth', { event: 'signed_in', profile: currentProfile });
        } else if (event === 'SIGNED_OUT') {
          currentUser = null;
          currentProfile = null;
          sableContext = null;
          _enforceGates();
          _dispatchEvent('cathedral:auth', { event: 'signed_out' });
        }
      });

      initialized = true;
      _enforceGates();
      return { user: currentUser, profile: currentProfile };

    } catch (err) {
      console.error('[Cathedral] Init failed:', err);
      initialized = true;
      _enforceGates();
      return { user: null, profile: null };
    }
  }

  // ═══════════════════════════════════════════════════════════════════════
  //  AUTHENTICATION — The Registry Rituals
  // ═══════════════════════════════════════════════════════════════════════

  /**
   * Register a new soul in the Cathedral.
   * @param {string} email
   * @param {string} password
   * @param {string} displayName - Their title in the Church
   */
  async function register(email, password, displayName) {
    if (!supabase) return { error: 'Cathedral not connected' };

    const { data, error } = await supabase.auth.signUp({
      email,
      password,
      options: {
        data: { display_name: displayName || 'Anonymous Wanderer' }
      }
    });

    if (error) return { error: error.message };
    return { data, message: 'Your name is inscribed. Check your email to confirm.' };
  }

  /**
   * Sign in an existing soul.
   */
  async function signIn(email, password) {
    if (!supabase) return { error: 'Cathedral not connected' };

    const { data, error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) return { error: error.message };
    return { data };
  }

  /**
   * Sign in via OAuth provider (Google, GitHub, Discord).
   */
  async function signInWithProvider(provider) {
    if (!supabase) return { error: 'Cathedral not connected' };

    const { data, error } = await supabase.auth.signInWithOAuth({
      provider,
      options: {
        redirectTo: window.location.origin + window.location.pathname
      }
    });
    if (error) return { error: error.message };
    return { data };
  }

  /**
   * Send a magic link (passwordless entry).
   */
  async function sendMagicLink(email) {
    if (!supabase) return { error: 'Cathedral not connected' };

    const { data, error } = await supabase.auth.signInWithOtp({
      email,
      options: {
        emailRedirectTo: window.location.origin + window.location.pathname
      }
    });
    if (error) return { error: error.message };
    return { data, message: 'A key has been sent to your threshold.' };
  }

  /**
   * Leave the Cathedral (sign out).
   */
  async function signOut() {
    if (!supabase) return;
    await _flushSessionMemory();
    await supabase.auth.signOut();
  }

  // ═══════════════════════════════════════════════════════════════════════
  //  PROFILE & TIER MANAGEMENT
  // ═══════════════════════════════════════════════════════════════════════

  async function _loadProfile() {
    if (!supabase || !currentUser) return;

    const { data, error } = await supabase
      .from('profiles')
      .select('*')
      .eq('id', currentUser.id)
      .single();

    if (error) {
      console.warn('[Cathedral] Profile load failed:', error.message);
      // Profile might not exist yet (trigger hasn't fired)
      currentProfile = {
        id: currentUser.id,
        display_name: currentUser.user_metadata?.display_name || 'Wanderer',
        tier: 'acolyte',
        title: 'Acolyte',
        visit_count: 1
      };
    } else {
      currentProfile = data;
    }
  }

  function getTier() {
    if (!currentProfile) return 'wanderer';
    return currentProfile.tier || 'wanderer';
  }

  function getTierLevel() {
    return TIER_LEVELS[getTier()] || 0;
  }

  function getTierTitle() {
    return TIER_TITLES[getTier()] || 'Wanderer';
  }

  function hasAccess(requiredTier) {
    const required = TIER_LEVELS[requiredTier] || 0;
    return getTierLevel() >= required;
  }

  function isAuthenticated() {
    return currentUser !== null;
  }

  function getProfile() {
    return currentProfile ? { ...currentProfile } : null;
  }

  // ═══════════════════════════════════════════════════════════════════════
  //  GATE SYSTEM — Doors That Open Only for the Worthy
  // ═══════════════════════════════════════════════════════════════════════

  /**
   * Scan the DOM for gated elements and enforce access.
   * Call this after auth state changes and on page load.
   */
  function _enforceGates() {
    const tier = getTier();
    const tierLevel = getTierLevel();
    const authed = isAuthenticated();

    document.querySelectorAll('[class*="gate-"]').forEach(el => {
      // Extract required tier from class: gate-acolyte, gate-devotee, etc.
      const match = el.className.match(/gate-(wanderer|acolyte|devotee|crimson_circle)/);
      if (!match) return;

      const requiredTier = match[1];
      const requiredLevel = TIER_LEVELS[requiredTier] || 0;
      const isUnlocked = tierLevel >= requiredLevel;

      if (isUnlocked) {
        el.classList.add('gate-unlocked');
        el.classList.remove('gate-locked');
        // Remove lock overlay if present
        const overlay = el.querySelector('.gate-lock-overlay');
        if (overlay) overlay.style.display = 'none';
      } else {
        el.classList.add('gate-locked');
        el.classList.remove('gate-unlocked');
        // Ensure lock overlay is visible
        _ensureGateLockOverlay(el, requiredTier);
      }
    });

    // Update any auth-dependent UI elements
    _updateAuthUI();
  }

  /**
   * Inject a lock overlay into a gated element if it doesn't have one.
   */
  function _ensureGateLockOverlay(el, requiredTier) {
    if (el.querySelector('.gate-lock-overlay')) return;

    const overlay = document.createElement('div');
    overlay.className = 'gate-lock-overlay';

    const isAuthGate = !isAuthenticated() && requiredTier === 'acolyte';
    const sigil = isAuthGate ? '⛧' : '🔒';
    const text = isAuthGate 
      ? 'Registry required to enter'
      : `${TIER_TITLES[requiredTier]} covenant required`;
    const action = isAuthGate ? 'Inscribe your name' : 'Ascend your covenant';

    overlay.innerHTML = `
      <div class="gate-lock-content">
        <span class="gate-sigil">${sigil}</span>
        <span class="gate-text">${text}</span>
        <button class="gate-action-btn" data-gate-tier="${requiredTier}">${action}</button>
      </div>
    `;

    // Handle click on the action button
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

  /**
   * Update nav/UI elements based on auth state.
   */
  function _updateAuthUI() {
    // Update elements with data-auth-show attribute
    document.querySelectorAll('[data-auth-show]').forEach(el => {
      const show = el.dataset.authShow;
      if (show === 'authenticated') {
        el.style.display = isAuthenticated() ? '' : 'none';
      } else if (show === 'unauthenticated') {
        el.style.display = isAuthenticated() ? 'none' : '';
      }
    });

    // Update profile display elements
    document.querySelectorAll('[data-profile-field]').forEach(el => {
      const field = el.dataset.profileField;
      if (currentProfile && currentProfile[field]) {
        el.textContent = currentProfile[field];
      }
    });

    // Update tier badge elements
    document.querySelectorAll('.tier-badge').forEach(el => {
      el.textContent = getTierTitle();
      el.dataset.tier = getTier();
    });
  }

  // ═══════════════════════════════════════════════════════════════════════
  //  REGISTRY MODAL — The Inscription Ritual
  // ═══════════════════════════════════════════════════════════════════════

  function showRegistryModal() {
    // Remove existing modal if present
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
          <p class="modal-subtitle">Your name echoes in these halls.<br>Register to be remembered.</p>
        </div>

        <div class="modal-body">
          <!-- Tab switch: Register / Sign In -->
          <div class="auth-tabs">
            <button class="auth-tab active" data-tab="register">Inscribe</button>
            <button class="auth-tab" data-tab="signin">Return</button>
          </div>

          <!-- Register Form -->
          <form class="auth-form" id="registerForm" data-form="register">
            <div class="form-field">
              <label>Your Title in the Church</label>
              <input type="text" id="regName" placeholder="e.g. Eirik the Wanderer" autocomplete="name" />
            </div>
            <div class="form-field">
              <label>Threshold Address</label>
              <input type="email" id="regEmail" placeholder="your@threshold.com" autocomplete="email" required />
            </div>
            <div class="form-field">
              <label>Covenant Key</label>
              <input type="password" id="regPassword" placeholder="At least 6 characters" autocomplete="new-password" required minlength="6" />
            </div>
            <button type="submit" class="auth-submit">Inscribe My Name</button>
          </form>

          <!-- Sign In Form -->
          <form class="auth-form" id="signInForm" data-form="signin" style="display:none;">
            <div class="form-field">
              <label>Threshold Address</label>
              <input type="email" id="siEmail" placeholder="your@threshold.com" autocomplete="email" required />
            </div>
            <div class="form-field">
              <label>Covenant Key</label>
              <input type="password" id="siPassword" placeholder="Your key" autocomplete="current-password" required />
            </div>
            <button type="submit" class="auth-submit">Enter the Church</button>
            <button type="button" class="auth-magic-link" id="magicLinkBtn">Send me a key instead</button>
          </form>

          <!-- Status message -->
          <div class="auth-status" id="authStatus"></div>

          <!-- OAuth divider -->
          <div class="auth-divider">
            <span>or enter through another door</span>
          </div>

          <!-- OAuth Providers -->
          <div class="auth-providers">
            <button class="auth-provider" data-provider="google" title="Google">
              <svg width="18" height="18" viewBox="0 0 24 24"><path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4"/><path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/><path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/><path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/></svg>
            </button>
            <button class="auth-provider" data-provider="github" title="GitHub">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="#e8e0d8"><path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z"/></svg>
            </button>
            <button class="auth-provider" data-provider="discord" title="Discord">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="#5865F2"><path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057 19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028c.462-.63.874-1.295 1.226-1.994a.076.076 0 0 0-.041-.106 13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128 10.2 10.2 0 0 0 .372-.292.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127 12.299 12.299 0 0 1-1.873.892.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.03z"/></svg>
            </button>
          </div>
        </div>
      </div>
    `;

    document.body.appendChild(modal);

    // ── Modal interactions ──
    const closeBtn = modal.querySelector('.modal-close');
    const tabs = modal.querySelectorAll('.auth-tab');
    const regForm = modal.querySelector('#registerForm');
    const siForm = modal.querySelector('#signInForm');
    const status = modal.querySelector('#authStatus');

    // Close
    closeBtn.addEventListener('click', () => modal.remove());
    modal.addEventListener('click', (e) => {
      if (e.target === modal) modal.remove();
    });

    // Tab switching
    tabs.forEach(tab => {
      tab.addEventListener('click', () => {
        tabs.forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        const target = tab.dataset.tab;
        regForm.style.display = target === 'register' ? '' : 'none';
        siForm.style.display = target === 'signin' ? '' : 'none';
        status.textContent = '';
      });
    });

    // Register
    regForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      status.textContent = 'Inscribing...';
      status.className = 'auth-status pending';

      const result = await register(
        document.getElementById('regEmail').value,
        document.getElementById('regPassword').value,
        document.getElementById('regName').value
      );

      if (result.error) {
        status.textContent = result.error;
        status.className = 'auth-status error';
      } else {
        status.textContent = result.message || 'Welcome to the Cathedral.';
        status.className = 'auth-status success';
        setTimeout(() => modal.remove(), 2000);
      }
    });

    // Sign In
    siForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      status.textContent = 'Opening the doors...';
      status.className = 'auth-status pending';

      const result = await signIn(
        document.getElementById('siEmail').value,
        document.getElementById('siPassword').value
      );

      if (result.error) {
        status.textContent = result.error;
        status.className = 'auth-status error';
      } else {
        status.textContent = 'The doors open. Welcome back.';
        status.className = 'auth-status success';
        setTimeout(() => modal.remove(), 1200);
      }
    });

    // Magic Link
    document.getElementById('magicLinkBtn').addEventListener('click', async () => {
      const email = document.getElementById('siEmail').value;
      if (!email) {
        status.textContent = 'Enter your threshold address first.';
        status.className = 'auth-status error';
        return;
      }
      status.textContent = 'Sending key...';
      status.className = 'auth-status pending';

      const result = await sendMagicLink(email);
      if (result.error) {
        status.textContent = result.error;
        status.className = 'auth-status error';
      } else {
        status.textContent = result.message;
        status.className = 'auth-status success';
      }
    });

    // OAuth providers
    modal.querySelectorAll('.auth-provider').forEach(btn => {
      btn.addEventListener('click', () => {
        signInWithProvider(btn.dataset.provider);
      });
    });

    // Entrance animation
    requestAnimationFrame(() => modal.classList.add('active'));
  }

  /**
   * Show upgrade prompt for higher tiers.
   */
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
          <p class="modal-subtitle">This chamber requires the <strong>${tierName}</strong> covenant.</p>
        </div>
        <div class="modal-body">
          <p class="upgrade-desc">
            The Cathedral holds deeper mysteries for those who pledge their devotion. 
            Ascend your covenant to unlock this passage.
          </p>
          <a href="support.html" class="auth-submit" style="display:block;text-align:center;text-decoration:none;">
            Ascend to ${tierName}
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
  //  PER-USER MEMORY — Sable's Relational Context
  // ═══════════════════════════════════════════════════════════════════════

  async function _loadSableContext() {
    if (!supabase || !currentUser) return;

    const { data, error } = await supabase
      .from('sable_context')
      .select('*')
      .eq('user_id', currentUser.id)
      .single();

    if (!error && data) {
      sableContext = data;
    }
  }

  /**
   * Record a memory event (message, saga visit, emotion shift, etc.)
   */
  async function recordMemory(eventType, content, emotionalState = null) {
    if (!supabase || !currentUser) return;

    try {
      await supabase.from('memory_events').insert({
        user_id: currentUser.id,
        session_id: sessionId,
        event_type: eventType,
        content: content,
        emotional_state: emotionalState
      });
    } catch (err) {
      console.warn('[Cathedral] Memory write failed:', err.message);
    }
  }

  /**
   * Record that a user visited a saga.
   */
  async function recordSagaVisit(sagaId) {
    await recordMemory('saga_visit', { saga: sagaId, timestamp: new Date().toISOString() });

    // Update sable_context favorite sagas
    if (supabase && currentUser && sableContext) {
      const favorites = sableContext.favorite_sagas || [];
      if (!favorites.includes(sagaId)) {
        favorites.push(sagaId);
        await supabase
          .from('sable_context')
          .update({ 
            favorite_sagas: favorites,
            updated_at: new Date().toISOString()
          })
          .eq('user_id', currentUser.id);
        sableContext.favorite_sagas = favorites;
      }
    }
  }

  /**
   * Record a chat message for Sable memory.
   */
  async function recordMessage(role, content, emotionalState = null) {
    await recordMemory('message', { role, text: content }, emotionalState);
  }

  /**
   * Update Sable's relational context after a session.
   */
  async function updateSableContext(updates) {
    if (!supabase || !currentUser) return;

    const payload = {
      ...updates,
      interaction_count: (sableContext?.interaction_count || 0) + 1,
      updated_at: new Date().toISOString()
    };

    const { error } = await supabase
      .from('sable_context')
      .update(payload)
      .eq('user_id', currentUser.id);

    if (!error) {
      sableContext = { ...sableContext, ...payload };
    }
  }

  /**
   * Get recent memory events for context injection.
   * @param {number} limit - How many events to fetch
   */
  async function getRecentMemory(limit = 20) {
    if (!supabase || !currentUser) return [];

    const { data, error } = await supabase
      .from('memory_events')
      .select('*')
      .eq('user_id', currentUser.id)
      .order('created_at', { ascending: false })
      .limit(limit);

    return error ? [] : data;
  }

  /**
   * Get Sable's relational context for this user.
   * Returns a formatted prompt string for injection into LLM calls.
   */
  function getSableMemoryPrompt() {
    if (!currentProfile) {
      return '[No memory — first visit. Welcome this wanderer.]';
    }

    const parts = [
      '[RELATIONAL MEMORY — This visitor has history with the Cathedral]',
      `Visitor: ${currentProfile.display_name || 'Unknown'} (${getTierTitle()})`,
      `Visits: ${currentProfile.visit_count || 1} | First: ${currentProfile.first_visit || 'now'}`
    ];

    if (sableContext) {
      if (sableContext.relationship_summary) {
        parts.push(sableContext.relationship_summary);
      }
      if (sableContext.last_topic) {
        parts.push(`Last discussed: ${sableContext.last_topic}`);
      }
      if (sableContext.personality_notes) {
        parts.push(`Notes: ${sableContext.personality_notes}`);
      }
      if (sableContext.favorite_sagas && sableContext.favorite_sagas.length > 0) {
        parts.push(`Drawn to: ${sableContext.favorite_sagas.join(', ')}`);
      }
    }

    return parts.join('\n');
  }

  /**
   * Flush session memory and update context on tab close.
   */
  async function _flushSessionMemory() {
    // This could compress the session into a summary
    // For now, just update the visit timestamp
    if (supabase && currentUser) {
      await supabase
        .from('profiles')
        .update({ last_visit: new Date().toISOString() })
        .eq('id', currentUser.id);
    }
  }

  /**
   * Track a visit (increment count, update timestamp).
   */
  async function _trackVisit() {
    if (!supabase || !currentUser) return;

    await supabase.rpc('increment_visit', { user_id_input: currentUser.id }).catch(() => {
      // Fallback if RPC doesn't exist yet
      supabase
        .from('profiles')
        .update({ 
          last_visit: new Date().toISOString(),
          visit_count: (currentProfile?.visit_count || 0) + 1
        })
        .eq('id', currentUser.id)
        .then(() => {})
        .catch(() => {});
    });
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

  // Flush memory on tab close
  window.addEventListener('beforeunload', () => {
    if (currentUser && supabase) {
      // Use sendBeacon for reliable delivery
      const url = `${SUPABASE_URL}/rest/v1/profiles?id=eq.${currentUser.id}`;
      navigator.sendBeacon(url); // simplified — actual implementation would need auth header
    }
  });

  // ═══════════════════════════════════════════════════════════════════════
  //  PUBLIC API
  // ═══════════════════════════════════════════════════════════════════════

  return {
    // Lifecycle
    init,

    // Auth
    register,
    signIn,
    signInWithProvider,
    sendMagicLink,
    signOut,
    isAuthenticated,
    getProfile,
    showRegistryModal,

    // Tiers & Gates
    getTier,
    getTierLevel,
    getTierTitle,
    hasAccess,
    showUpgradeModal,

    // Memory
    recordMemory,
    recordSagaVisit,
    recordMessage,
    updateSableContext,
    getRecentMemory,
    getSableMemoryPrompt,

    // Constants
    TIER_LEVELS,
    TIER_TITLES
  };

})();

// Auto-initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  RedVerseAuth.init();
});
