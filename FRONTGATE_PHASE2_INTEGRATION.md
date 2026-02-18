# FrontGate + Phase 2 Aurora Integration Guide

## Overview
The FrontGate authentication system has been **completely integrated** with Phase 2 Aurora, replacing Supabase with:
- **JWT Session Tokens** (server-signed, client-stored)
- **Google OAuth 2.0** (primary auth method)
- **Aurora Memory API** (per-user JSONL memory system)
- **Tier System 1-7** (Wanderer → Archon)
- **Admin Oversight** (Crimson Control Hall)

## File Structure

```
frontgate/
├── redverse-auth.js      # Phase 2 adapter (replaced Supabase)
└── redverse-gate.css     # Cathedral UI styling (unchanged)
```

## How It Works

### 1. Authentication Flow

**Page Load → Google OAuth → JWT Token → Gates Unlocked**

```javascript
// User clicks "Sign In"
RedVerseAuth.showRegistryModal()
// → Modal shows Google button
// → User clicks → redirects to google_auth.html
// → google_auth.html handles Google OAuth
// → Calls /api/auth/validate_google_token
// → Aurora returns JWT + user data
// → JWT stored in sessionStorage.aurora_session_jwt
// → Pages reload, RedVerseAuth.init() validates JWT
// → Gates automatically unlock based on tier
```

### 2. Tier System Comparison

**Old System (Supabase)**
```javascript
wanderer   (0)
acolyte    (1)
devotee    (2)
crimson_circle (3)
```

**New System (Phase 2)**
```javascript
Tier 1: Wanderer        (public access)
Tier 2: Seeker          (basic features)
Tier 3: Acolyte         (standard user)
Tier 4: Sage            (memory sharing enabled)
Tier 5: Oracle          (cross-site memory)
Tier 6: Sentinel        (pooled memory)
Tier 7: Archon          (unlimited memory + admin)
```

**Backward Compatibility**
Old tier names still work! The system automatically maps:
- `gate-acolyte` → `gate-3` (Tier 3)
- `gate-devotee` → `gate-4` (Tier 4)
- `gate-crimson_circle` → `gate-5` (Tier 5)

### 3. Usage in HTML

**OLD (Supabase-based)**
```html
<div class="gate-acolyte">
  <p>Only acolytes can see this</p>
</div>
```

**NEW (Works the same!)**
```html
<!-- Old syntax still works -->
<div class="gate-acolyte">
  <p>Only Acolytes (Tier 3+) can see this</p>
</div>

<!-- Or use explicit tier numbers -->
<div class="gate-4">
  <p>Only Sages (Tier 4+) can see this</p>
</div>
```

**Auth-dependent content**
```html
<!-- Show only to authenticated users -->
<button data-auth-show="authenticated" onclick="RedVerseAuth.showRegistryModal()">
  Manage Memory
</button>

<!-- Show only to admins -->
<a data-auth-show="admin" href="crimson-control-hall.html">
  🔴 Control Hall
</a>

<!-- Show user's tier badge -->
<span class="tier-badge"></span>
```

### 4. Memory Integration

The frontgate now automatically records memories when users interact:

```javascript
// Record a message
await RedVerseAuth.recordMemory(
  'user',
  'What can you tell me?',
  { primary: 'curiosity', intensity: 0.7 }
)

// Load recent conversation history
const history = await RedVerseAuth.getConversationHistory(limit: 50)

// Get memory stats for current user
const stats = await RedVerseAuth.getMemoryStats()
// → { exists: true, event_count: 150, tier_limit: 25, ... }
```

## API Reference

### Authentication Methods

```javascript
// Initialize (called automatically)
await RedVerseAuth.init()

// Check authentication status
RedVerseAuth.isAuthenticated()        // → true/false
RedVerseAuth.isAdmin()                // → true/false
RedVerseAuth.getProfile()             // → user object
RedVerseAuth.getJWT()                 // → JWT token string

// Sign operations
RedVerseAuth.signOut()                // Clear JWT & logout
RedVerseAuth.showRegistryModal()      // Show Google signin
RedVerseAuth.showUpgradeModal(4)      // Show tier upgrade prompt
```

### Tier Management

```javascript
RedVerseAuth.getTier()                // → 1-7
RedVerseAuth.getTierTitle()           // → "Wanderer", "Acolyte", etc.
RedVerseAuth.getTierLevel()           // → numeric tier (1-7)
RedVerseAuth.hasAccess(4)             // → true if tier >= 4
```

### Memory Methods

```javascript
// Store a memory
await RedVerseAuth.recordMemory(role, content, emotionalState)

// Retrieve memories
await RedVerseAuth.getRecentMemory(limit)           // Raw events
await RedVerseAuth.getConversationHistory(limit)    // Formatted for AI
await RedVerseAuth.getMemoryStats()                  // User's memory stats

// Get formatted prompt for LLM injection
const prompt = RedVerseAuth.getSableMemoryPrompt()
// "[RELATIONAL MEMORY — This visitor has history with the Cathedral]
//  Visitor: John Doe (Acolyte)
//  Tier: 3 | Thread: a1b2c3d4..."
```

### Admin Functions

```javascript
// Get link to Control Hall if user is admin
const adminLink = RedVerseAuth.createAdminLink()  // → "crimson-control-hall.html"

// Check if user can access admin area
if (RedVerseAuth.isAdmin()) {
  window.location.href = RedVerseAuth.createAdminLink()
}
```

## Event Listening

The system dispatches custom events for auth state changes:

```javascript
window.addEventListener('cathedral:auth', (e) => {
  switch (e.detail.event) {
    case 'signed_in':
      console.log('User logged in:', e.detail.profile)
      break
    case 'session_restored':
      console.log('Existing session loaded')
      break
    case 'signed_out':
      console.log('User logged out')
      break
  }
})
```

## Integration Checklist

### For Each Page Using Gates

1. **Include the scripts**
   ```html
   <link rel="stylesheet" href="frontgate/redverse-gate.css">
   <script src="frontgate/redverse-auth.js"></script>
   ```

2. **Add gated content**
   ```html
   <div class="gate-3">Protected content for Tier 3+</div>
   <button data-auth-show="authenticated">My Profile</button>
   ```

3. **Record memories (optional)**
   ```javascript
   // When user does something
   RedVerseAuth.recordMemory('user', 'Asked about memory system')
   ```

4. **Load previous context (optional)**
   ```javascript
   // Before showing AI response
   const history = await RedVerseAuth.getConversationHistory(50)
   // Inject into LLM prompt
   ```

## Key Differences from Supabase Version

| Feature | Old | New |
|---------|-----|-----|
| Auth Backend | Supabase | Google OAuth + Aurora JWT |
| Memory Storage | Supabase postgres | JSONL files per user |
| Tier System | 4 levels | 7 levels |
| Admin Access | None | Crimson Control Hall |
| Authorization | Database RLS | JWT + Server validation |
| Session Storage | localStorage | sessionStorage |
| Memory API | Supabase REST | Aurora HTTP API |

## Security Improvements

✅ **JWT Verification**: All requests must include valid JWT
✅ **Tier Spoofing Prevention**: Server re-validates tier on every request
✅ **Memory Isolation**: User can only access own thread_id
✅ **Admin Oversight**: Read-only observation, never modification
✅ **Per-User Threads**: JSONL files are UUID-based, not guessable

## Troubleshooting

### Gates not unlocking after login?
- Check: `sessionStorage.getItem('aurora_session_jwt')` in console
- Verify: JWT was returned from `/api/auth/validate_google_token`
- Clear: `sessionStorage.clear()` and reload

### Memory not being saved?
- Check: User is authenticated (`RedVerseAuth.isAuthenticated()`)
- Verify: Aurora API is running on `http://localhost:5000`
- Check: JWT is valid (not expired)

### Admin link not showing?
- Verify: User has `is_admin: true` in database
- Check: JWT includes `is_admin` claim
- Use: `RedVerseAuth.isAdmin()` to verify

## Next Steps

1. ✅ Test gates on a page with mixed tier requirements
2. ✅ Add memory recording to AI interaction pages
3. ✅ Create `/admin/` pages that check `data-auth-show="admin"`
4. ✅ Link to Crimson Control Hall from admin UI

## Files Modified

- ✅ `frontgate/redverse-auth.js` → Phase 2 adapter (661 lines)
- ✅ `frontgate/redverse-gate.css` → Same cathedral styling (intact)

---

**Phase 2 Status**: ✅ Complete
**Integration**: ✅ Wrapped around existing FrontGate design
**Ready for**: E-Drive, Oracle, Redverse pages with memory integration
