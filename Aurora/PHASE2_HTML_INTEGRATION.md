# Phase 2: HTML Integration Guide
## Per-User JSONL Memory System

This guide shows how to integrate the Phase 2 memory system into your HTML pages (EDrive.html, oracle.html, redverse.html).

---

## Quick Start

### 1. Start the Memory API Server

```bash
cd Aurora
python memory_api_server.py
```

Server will start on `http://localhost:5000`

### 2. Include Memory Client in Your HTML

Add this to the `<head>` section of your HTML pages:

```html
<script src="Aurora/memory_client.js"></script>
```

### 3. Initialize Memory Client

Add this JavaScript to your page:

```javascript
// Create memory client instance
const memoryClient = new AuroraMemoryClient('http://localhost:5000/api');

// Initialize session on page load
document.addEventListener('DOMContentLoaded', async () => {
    const sessionActive = await memoryClient.initSession();

    if (sessionActive) {
        console.log('Memory session active!');

        // Load conversation history
        const history = await memoryClient.loadContext();
        console.log(`Loaded ${history.length} previous messages`);

        // Display cross-site summary (Tier 4+)
        const summary = await memoryClient.getCrossSiteSummary();
        if (summary) {
            displayContinuityMessage(summary);
        }
    } else {
        console.log('No active session - guest mode');
    }
});
```

---

## API Methods

### Session Management

```javascript
// Set session manually (after Obelisk authentication)
memoryClient.setSession(threadId, accessTier, tierName);

// Check if session is active
if (memoryClient.isSessionActive()) {
    // User is logged in
}

// Get tier information
const tierInfo = memoryClient.getTierInfo();
console.log(`User tier: ${tierInfo.name} (${tierInfo.tier})`);
```

### Storing Events

```javascript
// Store user message
await memoryClient.storeEvent(
    'user',                    // role
    'Hello, I need help!',     // content
    'edrive',                  // source: edrive|oracle|redverse
    { primary: 'curiosity', intensity: 0.7 },  // emotion (optional)
    { page: 'main' }          // metadata (optional)
);

// Store assistant response
await memoryClient.storeEvent(
    'assistant',
    'Of course! How can I assist you?',
    'edrive',
    { primary: 'joy', intensity: 0.8 }
);
```

### Loading Memory

```javascript
// Load conversation context (uses tier limit)
const events = await memoryClient.loadContext();

// Load specific number of events
const lastTen = await memoryClient.loadContext(10);

// Get conversation history for AI prompt
const history = await memoryClient.getConversationHistory(20);
// Returns: [{role: 'user', content: '...'}, {role: 'assistant', content: '...'}]
```

### Cross-Site Continuity (Tier 4+)

```javascript
// Get cross-site summary
const summary = await memoryClient.getCrossSiteSummary(10);

// Example output:
// "Recent activity (8 events):
//   - EDRIVE: 5 interactions
//   - ORACLE: 3 interactions
// Last interaction: ORACLE at 2026-02-17T10:30:00Z"
```

### Emotion Tracking

```javascript
// Get emotional trajectory
const emotions = await memoryClient.getEmotionTrajectory(20);

console.log(emotions);
// {
//   primary_emotion: "joy",
//   intensity_avg: 0.75,
//   trend: "positive",
//   event_count: 15
// }
```

### Memory Statistics

```javascript
// Get memory stats for current user
const stats = await memoryClient.getMemoryStats();

console.log(stats);
// {
//   exists: true,
//   event_count: 150,
//   file_size_bytes: 45678,
//   first_event: "2026-01-15T12:00:00Z",
//   last_event: "2026-02-17T10:30:00Z",
//   tier: 3,
//   tier_name: "Acolyte",
//   memory_depth_limit: 25
// }
```

---

## Integration Examples

### Example 1: E-Drive Chat Integration

```javascript
// When user sends a message
async function sendMessage() {
    const userInput = document.getElementById('chatInput').value;

    // Display user message
    appendMessage('user', userInput);

    // Store to memory
    await memoryClient.storeEvent('user', userInput, 'edrive');

    // Send to AI (your existing logic)
    const response = await sendToAI(userInput);

    // Display AI response
    appendMessage('assistant', response);

    // Store AI response to memory
    await memoryClient.storeEvent('assistant', response, 'edrive');
}

// On page load: inject conversation history into AI context
async function loadPreviousContext() {
    const history = await memoryClient.getConversationHistory(10);

    // Add to your AI system prompt
    const systemPrompt = `
[CONTINUITY CONTEXT]
User: ${memoryClient.tierName} (Tier ${memoryClient.accessTier})
Previous conversation:
${history.map(h => `${h.role}: ${h.content}`).join('\n')}

Continue the conversation naturally, referencing prior topics when relevant.
    `;

    return systemPrompt;
}
```

### Example 2: Oracle Page with Cross-Site Awareness

```javascript
// On Oracle page load
document.addEventListener('DOMContentLoaded', async () => {
    await memoryClient.initSession();

    if (memoryClient.isSessionActive()) {
        // Check if user came from another page
        const summary = await memoryClient.getCrossSiteSummary();

        if (summary) {
            // Show continuity message
            showNotification(`I remember you from our previous conversation. ${summary}`);
        }

        // Load Oracle-specific history
        const oracleEvents = await memoryClient.loadContext();
        const oracleHistory = oracleEvents.filter(e => e.source === 'oracle');

        // Inject into Oracle AI context
        initializeOracleWithContext(oracleHistory);
    }
});
```

### Example 3: Emotion-Based UI

```javascript
// Update UI based on emotional state
async function updateEmotionalTheme() {
    const emotions = await memoryClient.getEmotionTrajectory(10);

    if (emotions.trend === 'positive') {
        document.body.classList.add('theme-uplifting');
    } else if (emotions.trend === 'negative') {
        document.body.classList.add('theme-supportive');
    }

    // Display emotion indicator
    document.getElementById('emotionIndicator').textContent =
        `Current mood: ${emotions.primary_emotion || 'neutral'}`;
}
```

---

## Tier-Based Feature Gating

```javascript
// Check user tier and enable/disable features
function applyTierGating() {
    const tier = memoryClient.accessTier;

    // Tier 1 (Wanderer): No memory access
    if (tier === 1) {
        document.getElementById('historyPanel').style.display = 'none';
    }

    // Tier 4+ (Keeper): Enable cross-site features
    if (tier >= 4) {
        document.getElementById('crossSitePanel').style.display = 'block';
    }

    // Tier 5+ (Sentinel): Custom soul configurations
    if (tier >= 5) {
        document.getElementById('advancedSettings').style.display = 'block';
    }

    // Tier 7 (Inner Sanctum): Full access
    if (tier === 7) {
        document.getElementById('adminPanel').style.display = 'block';
    }
}
```

---

## Obelisk Authentication Flow

When a user logs in via Obelisk Customs:

```javascript
// After Obelisk validates card
async function onObeliskSuccess(cardData) {
    // Extract member data from card
    const memberId = cardData.member_id;

    // Validate with backend
    const memberData = await memoryClient.validateMember(memberId);

    if (memberData && memberData.valid) {
        // Session auto-set by validateMember()
        console.log(`Welcome, ${memberData.member_profile.name}!`);

        // Redirect to index_entrance.html
        window.location.href = 'index_entrance.html';
    } else {
        alert('Invalid credentials');
    }
}
```

---

## Testing Without Obelisk

For development/testing, you can set a test session:

```javascript
// Test session (Tier 3 - Acolyte)
memoryClient.setSession(
    '123e4567-e89b-12d3-a456-426614174000',  // test thread_id
    3,                                        // Tier 3
    'Acolyte'                                 // Tier name
);

// Now you can test memory features
await memoryClient.storeEvent('user', 'Test message', 'edrive');
const history = await memoryClient.loadContext();
console.log(history);
```

---

## Error Handling

```javascript
try {
    const events = await memoryClient.loadContext();

    if (events.length === 0) {
        console.log('No previous conversations');
    }
} catch (error) {
    console.error('Memory system error:', error);
    // Fall back to non-memory mode
}
```

---

## Full Page Example

See `memory_example.html` for a complete working example integrating:
- Session initialization
- Chat message storage
- Conversation history loading
- Cross-site summaries
- Emotion tracking
- Tier-based UI gating

---

## Flask Server Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/health` | GET | Health check |
| `/api/memory/store` | POST | Store event |
| `/api/memory/load` | POST | Load context |
| `/api/memory/conversation_history` | POST | Get history for AI |
| `/api/memory/cross_site_summary` | POST | Cross-site summary |
| `/api/memory/emotions` | POST | Emotion trajectory |
| `/api/memory/stats` | POST | Memory statistics |
| `/api/member/validate` | POST | Validate member |

---

## Next Steps

1. Start the Flask server: `python memory_api_server.py`
2. Add `<script src="Aurora/memory_client.js"></script>` to your HTML pages
3. Initialize memory client in your JavaScript
4. Store events when users chat
5. Load context to provide AI continuity
6. Test with different tiers to see memory limits

**Phase 2 is now integrated into your HTML interfaces!** 🎉
