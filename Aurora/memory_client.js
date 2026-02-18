/**
 * Aurora Archive - Memory Client
 * JavaScript client for per-user JSONL memory system
 *
 * Phase 2 Integration for HTML interfaces (E-Drive, Oracle, RedVerse)
 * Works with memory_api_server.py Flask backend
 */

class AuroraMemoryClient {
    constructor(apiBaseUrl = 'http://localhost:5000/api') {
        this.apiBaseUrl = apiBaseUrl;
        this.threadId = null;
        this.accessTier = 1;
        this.tierName = 'Wanderer';
        this.sessionLoaded = false;
    }

    /**
     * Initialize session from sessionStorage or login
     * Call this on page load
     */
    async initSession() {
        // Check sessionStorage for existing session
        const sessionData = sessionStorage.getItem('aurora_session');

        if (sessionData) {
            try {
                const session = JSON.parse(sessionData);
                this.threadId = session.thread_id;
                this.accessTier = session.access_tier || 1;
                this.tierName = session.tier_name || 'Wanderer';
                this.sessionLoaded = true;

                console.log(`[Aurora Memory] Session loaded: ${this.tierName} (Tier ${this.accessTier})`);
                return true;
            } catch (e) {
                console.error('[Aurora Memory] Failed to parse session data:', e);
            }
        }

        return false;
    }

    /**
     * Set session manually (e.g., after Obelisk authentication)
     * @param {string} threadId - User's thread ID
     * @param {number} accessTier - User's access tier (1-7)
     * @param {string} tierName - Tier name (e.g., "Acolyte")
     */
    setSession(threadId, accessTier = 1, tierName = 'Wanderer') {
        this.threadId = threadId;
        this.accessTier = accessTier;
        this.tierName = tierName;
        this.sessionLoaded = true;

        // Save to sessionStorage
        sessionStorage.setItem('aurora_session', JSON.stringify({
            thread_id: threadId,
            access_tier: accessTier,
            tier_name: tierName
        }));

        console.log(`[Aurora Memory] Session set: ${tierName} (Tier ${accessTier})`);
    }

    /**
     * Store a conversation event
     * @param {string} role - "user" or "assistant" or "system"
     * @param {string} content - Message content
     * @param {string} source - "edrive", "oracle", or "redverse"
     * @param {Object} emotionState - { primary: "joy", intensity: 0.8 }
     * @param {Object} metadata - Additional metadata
     */
    async storeEvent(role, content, source = 'edrive', emotionState = null, metadata = {}) {
        if (!this.sessionLoaded) {
            console.warn('[Aurora Memory] Session not loaded, skipping event storage');
            return null;
        }

        try {
            const response = await fetch(`${this.apiBaseUrl}/memory/store`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    thread_id: this.threadId,
                    access_tier: this.accessTier,
                    role: role,
                    content: content,
                    source: source,
                    emotion_state: emotionState,
                    metadata: metadata
                })
            });

            const data = await response.json();

            if (response.ok) {
                console.log(`[Aurora Memory] Event stored: ${role} (${source})`);
                return data;
            } else {
                console.error('[Aurora Memory] Failed to store event:', data.error);
                return null;
            }
        } catch (error) {
            console.error('[Aurora Memory] Error storing event:', error);
            return null;
        }
    }

    /**
     * Load user conversation context
     * @param {number} limit - Number of events to load (null uses tier default)
     * @returns {Array} Array of events
     */
    async loadContext(limit = null) {
        if (!this.sessionLoaded) {
            console.warn('[Aurora Memory] Session not loaded, returning empty context');
            return [];
        }

        try {
            const response = await fetch(`${this.apiBaseUrl}/memory/load`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    thread_id: this.threadId,
                    access_tier: this.accessTier,
                    limit: limit
                })
            });

            const data = await response.json();

            if (response.ok) {
                console.log(`[Aurora Memory] Loaded ${data.count} events (Tier ${data.tier}: ${data.tier_name})`);
                return data.events || [];
            } else {
                console.error('[Aurora Memory] Failed to load context:', data.error);
                return [];
            }
        } catch (error) {
            console.error('[Aurora Memory] Error loading context:', error);
            return [];
        }
    }

    /**
     * Get conversation history formatted for AI
     * @param {number} limit - Number of messages to include
     * @returns {Array} Array of {role, content} objects
     */
    async getConversationHistory(limit = null) {
        if (!this.sessionLoaded) {
            return [];
        }

        try {
            const response = await fetch(`${this.apiBaseUrl}/memory/conversation_history`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    thread_id: this.threadId,
                    access_tier: this.accessTier,
                    limit: limit
                })
            });

            const data = await response.json();

            if (response.ok) {
                return data.history || [];
            } else {
                console.error('[Aurora Memory] Failed to get conversation history:', data.error);
                return [];
            }
        } catch (error) {
            console.error('[Aurora Memory] Error getting conversation history:', error);
            return [];
        }
    }

    /**
     * Get cross-site summary (Tier 4+ only)
     * @param {number} limit - Number of events to summarize
     * @returns {string} Summary text
     */
    async getCrossSiteSummary(limit = 10) {
        if (!this.sessionLoaded) {
            return '';
        }

        try {
            const response = await fetch(`${this.apiBaseUrl}/memory/cross_site_summary`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    thread_id: this.threadId,
                    access_tier: this.accessTier,
                    limit: limit
                })
            });

            const data = await response.json();

            if (response.ok) {
                if (data.cross_site_enabled) {
                    console.log('[Aurora Memory] Cross-site summary generated');
                    return data.summary;
                } else {
                    console.log(`[Aurora Memory] Cross-site disabled for ${this.tierName}`);
                    return '';
                }
            } else {
                console.error('[Aurora Memory] Failed to get cross-site summary:', data.error);
                return '';
            }
        } catch (error) {
            console.error('[Aurora Memory] Error getting cross-site summary:', error);
            return '';
        }
    }

    /**
     * Get emotional trajectory
     * @param {number} limit - Number of events to analyze
     * @returns {Object} Emotion statistics
     */
    async getEmotionTrajectory(limit = 20) {
        if (!this.sessionLoaded) {
            return null;
        }

        try {
            const response = await fetch(`${this.apiBaseUrl}/memory/emotions`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    thread_id: this.threadId,
                    access_tier: this.accessTier,
                    limit: limit
                })
            });

            const data = await response.json();

            if (response.ok) {
                console.log(`[Aurora Memory] Emotion: ${data.primary_emotion} (${data.trend})`);
                return data;
            } else {
                console.error('[Aurora Memory] Failed to get emotion trajectory:', data.error);
                return null;
            }
        } catch (error) {
            console.error('[Aurora Memory] Error getting emotion trajectory:', error);
            return null;
        }
    }

    /**
     * Get memory statistics
     * @returns {Object} Memory stats
     */
    async getMemoryStats() {
        if (!this.sessionLoaded) {
            return null;
        }

        try {
            const response = await fetch(`${this.apiBaseUrl}/memory/stats`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    thread_id: this.threadId,
                    access_tier: this.accessTier
                })
            });

            const data = await response.json();

            if (response.ok) {
                return data;
            } else {
                console.error('[Aurora Memory] Failed to get memory stats:', data.error);
                return null;
            }
        } catch (error) {
            console.error('[Aurora Memory] Error getting memory stats:', error);
            return null;
        }
    }

    /**
     * Validate member credentials
     * @param {string} memberId - Member ID
     * @param {string} email - Email (optional)
     * @returns {Object} Member validation result
     */
    async validateMember(memberId, email = null) {
        try {
            const response = await fetch(`${this.apiBaseUrl}/member/validate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    member_id: memberId,
                    email: email
                })
            });

            const data = await response.json();

            if (response.ok && data.valid) {
                // Auto-set session if validation succeeds
                this.setSession(data.thread_id, data.access_tier, data.tier_name);
                return data;
            } else {
                console.error('[Aurora Memory] Member validation failed:', data.error);
                return null;
            }
        } catch (error) {
            console.error('[Aurora Memory] Error validating member:', error);
            return null;
        }
    }

    /**
     * Check if session is loaded
     * @returns {boolean}
     */
    isSessionActive() {
        return this.sessionLoaded && this.threadId !== null;
    }

    /**
     * Get current tier info
     * @returns {Object} Tier information
     */
    getTierInfo() {
        return {
            tier: this.accessTier,
            name: this.tierName,
            memory_depth: this._getMemoryDepthForTier(this.accessTier)
        };
    }

    /**
     * Get memory depth limit for tier
     * @private
     */
    _getMemoryDepthForTier(tier) {
        const limits = {
            1: 0,
            2: 10,
            3: 25,
            4: 50,
            5: 100,
            6: 500,
            7: -1  // Unlimited
        };
        return limits[tier] || 0;
    }
}

// Export for use in HTML pages
if (typeof module !== 'undefined' && module.exports) {
    module.exports = AuroraMemoryClient;
}
