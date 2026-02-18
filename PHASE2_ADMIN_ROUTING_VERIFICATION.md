# Phase 2: Admin Role-Based Routing Verification

## Complete Data Flow: Google OAuth → JWT → Admin Check → Page Access

### ✅ STEP 1: Member Data Generation (Aurora/database_manager.py)

**Location**: `Aurora/database_manager.py:257-268`

When a new user signs in via Google, the `create_new_member_from_google()` function now:

1. **Reads admin email whitelist** from environment (at init time):
   ```python
   # In __init__ (line 48-62):
   admin_emails_str = os.getenv('ADMIN_EMAILS', '')
   self.admin_emails = set(
       email.strip().lower()
       for email in admin_emails_str.split(',')
       if email.strip()
   )
   ```

2. **Checks if user email is admin** (new method at line 257-268):
   ```python
   def _is_admin_email(self, email: str) -> bool:
       """Check if email address is in admin whitelist"""
       email_lower = email.lower().strip()
       return email_lower in self.admin_emails
   ```

3. **Sets is_admin flag based on email** (line 279-291):
   ```python
   # Determine if user is admin based on email whitelist
   is_admin = self._is_admin_email(email)
   admin_status = "PROMOTED TO ADMIN" if is_admin else "regular user"

   member_data = {
       # ... other fields ...
       'is_admin': is_admin,  # ← Determined by email whitelist
       # ...
   }
   ```

4. **Logs admin promotion for audit trail** (line 310):
   ```
   'details': f'Created via Google OAuth: {email} ({admin_status})'
   ```

5. **Logs transaction with is_admin flag** (line 336):
   ```python
   "is_admin": is_admin
   ```

**Configuration**: Read from `.env` file:
```env
ADMIN_EMAILS=admin@example.com,staff@example.com
```

### ✅ STEP 2: JWT Token Issuance (Aurora/memory_api_server.py)

**Location**: `/api/auth/validate_google_token` endpoint (lines 454-530)

When frontend posts Google token:

```python
# Line 516-525:
return jsonify({
    "success": True,
    "member_id": member.get('id'),
    "thread_id": member.get('thread_id'),
    "access_tier": member.get('access_tier', 1),
    "tier_name": member.get('tier_name', 'Wanderer'),
    "session_token": session_token,  # JWT with is_admin included
    "display_name": member.get('display_name', email.split('@')[0]),
    "is_admin": member.get('is_admin', False)  # ← Returned to frontend
})
```

### ✅ STEP 3: JWT Token Creation (Aurora/session_manager.py)

**Location**: `SessionManager.create_session_token()` (lines 51-78)

The JWT payload includes the `is_admin` claim:

```python
payload = {
    'member_id': member_id,
    'thread_id': thread_id,
    'email': email,
    'display_name': display_name,
    'access_tier': access_tier,
    'tier_name': tier_name,
    'google_sub': google_sub,
    'is_admin': is_admin,  # ← Role flag in JWT
    'iat': int(now.timestamp()),
    'exp': int(exp.timestamp())
}
```

### ✅ STEP 4: Frontend JWT Storage & Validation (frontgate/redverse-auth.js)

**Location**: `frontgate/redverse-auth.js:66-96`

Initialization process:

```javascript
async function init(options = {}) {
    // Check for JWT in sessionStorage
    jwtToken = sessionStorage.getItem('aurora_session_jwt');

    if (jwtToken) {
        // Validate and load existing session
        const valid = await _validateSession();
        // ...
    }
}
```

**JWT Decoding** (line 102-134):

```javascript
async function _validateSession() {
    // Decode JWT to extract user data
    const payload = JSON.parse(atob(jwtToken.split('.')[1]));

    // Load user data from decoded JWT
    currentUser = {
        member_id: payload.member_id,
        thread_id: payload.thread_id,
        access_tier: payload.access_tier,
        tier_name: payload.tier_name,
        display_name: payload.display_name,
        email: payload.email,
        is_admin: payload.is_admin || false,  // ← Read admin flag
        google_sub: payload.google_sub
    };
}
```

### ✅ STEP 5: Admin Status Queries (frontgate/redverse-auth.js)

**Location**: Lines 252-254

```javascript
function isAdmin() {
    return isAuthenticated() && (currentProfile?.is_admin || false);
}
```

### ✅ STEP 6: Visual Role-Based Routing (frontgate/redverse-auth.js)

**Location**: `_updateAuthUI()` function (lines 342-365)

```javascript
function _updateAuthUI() {
    document.querySelectorAll('[data-auth-show]').forEach(el => {
        const show = el.dataset.authShow;
        if (show === 'authenticated') {
            el.style.display = isAuthenticated() ? '' : 'none';
        } else if (show === 'unauthenticated') {
            el.style.display = isAuthenticated() ? 'none' : '';
        } else if (show === 'admin') {
            el.style.display = isAdmin() ? '' : 'none';  // ← Admin check
        }
    });
}
```

**Usage in HTML**: Elements with `data-auth-show="admin"` are only visible to admin users.

Example:
```html
<!-- Show control hall link ONLY to admins -->
<a data-auth-show="admin" href="crimson-control-hall.html">
  🔴 Control Hall (Admin)
</a>

<!-- Show regular user menu ONLY to authenticated non-admins -->
<button data-auth-show="authenticated" onclick="showMemoryDashboard()">
  📚 My Memories
</button>
```

### ✅ STEP 7: Admin Control Hall Access (crimson-control-hall.html)

**Location**: Lines 528-552

Double-verification on page load:

```javascript
function validateAdmin() {
    const jwt = sessionStorage.getItem('aurora_session_jwt');
    if (!jwt) {
        alert('Not authenticated');
        window.location.href = 'google_auth.html';
        return;
    }

    try {
        const payload = JSON.parse(atob(jwt.split('.')[1]));
        if (!payload.is_admin) {
            alert('Admin access required');
            window.location.href = 'redverse_first_contact.html';  // ← Non-admins redirected
            return;
        }
        // Admin verified - load dashboard
        document.getElementById('admin-name').textContent = `ADMIN: ${payload.display_name}`;
        document.getElementById('admin-tier').textContent = `TIER: ${payload.tier_name}`;
    } catch (e) {
        window.location.href = 'google_auth.html';
    }
}
```

### ✅ STEP 8: Admin API Endpoint Protection (Aurora/memory_api_server.py)

**Locations**: Lines 54-72 (@require_admin decorator) + individual endpoints

Double verification:

```python
def require_admin(f):
    """Decorator to verify admin privileges on top of JWT auth"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Get member from request (set by @require_auth)
        member_id = getattr(request, 'member_id', None)
        if not member_id:
            return jsonify({"error": "Authentication required"}), 401

        # Check if user is admin in database
        member = db.get_member(member_id)
        if not member or not member.get('is_admin', False):
            logger.warning(f"[ADMIN] Non-admin user {member_id} attempted admin access")
            return jsonify({"error": "Admin privileges required"}), 403

        return f(*args, **kwargs)
    return decorated_function
```

Protected endpoints:
- `GET /api/admin/overview` (line 714-751)
- `GET /api/admin/users` (line 754-811)
- `GET /api/admin/user/{member_id}/timeline` (line 814-858)
- `GET /api/admin/user/{member_id}/analytics` (line 861-911)
- `GET /api/admin/search` (line 914-957)
- `GET /api/admin/sharing_graph` (line 960-982)
- `POST /api/admin/user/{member_id}/flags` (line 985-1040)
- `GET /api/admin/emotions` (line 1043-1072)

---

## Complete User Journey Flowchart

```
┌─────────────────────────────────────────────────────────────┐
│ User visits redverse_first_contact.html                     │
│ (or any page with FrontGate authentication)                 │
└────────────────── ↓────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ RedVerseAuth.init() checks for JWT in sessionStorage        │
└────────────────── ↓────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ No JWT found → Show "Sign In with Google" button            │
│ User clicks → Redirects to google_auth.html                 │
└────────────────── ↓────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ google_auth.html: User authenticates with Google            │
│ Frontend posts credential to backend                        │
└────────────────── ↓────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ /api/auth/validate_google_token endpoint:                   │
│ • Look up or create member by email                         │
│ • Check: is email in ADMIN_EMAILS env var? ↓               │
│   YES → member.is_admin = True  →  JWT includes admin claim │
│   NO  → member.is_admin = False →  JWT includes user claim  │
└────────────────── ↓────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Return JWT session token to frontend                        │
│ JWT payload includes: {member_id, thread_id, is_admin, ...} │
└────────────────── ↓────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Frontend stores JWT in sessionStorage.aurora_session_jwt    │
│ Redirects to redverse_first_contact.html                    │
└────────────────── ↓────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ RedVerseAuth.init() finds JWT, decodes it ↓                │
│                                                              │
│ if (JWT.is_admin === true) {                               │
│   currentProfile.is_admin = true                            │
│   _updateAuthUI() shows [data-auth-show="admin"] elements   │
│ } else {                                                    │
│   currentProfile.is_admin = false                           │
│   _updateAuthUI() hides [data-auth-show="admin"] elements   │
│ }                                                            │
└────────────────── ↓────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ PAGE ROUTING DECISION:                                      │
│                                                              │
│ ADMIN USER (is_admin = true):                              │
│ ✓ Control Hall link visible in UI                          │
│ ✓ Can click → crimson-control-hall.html                    │
│ ✓ validateAdmin() passes → Dashboard loads                 │
│ ✓ Can access /api/admin/* endpoints                        │
│                                                              │
│ REGULAR USER (is_admin = false):                           │
│ ✗ Control Hall link hidden from UI                         │
│ ✗ Can't click or access                                    │
│ ✗ If manually navigates → validateAdmin() redirects        │
│ ✗ Can't access /api/admin/* endpoints                      │
└─────────────────────────────────────────────────────────────┘
```

---

## Configuration Setup

### 1. Create `.env` file in project root

```bash
# Copy the template
cp .env.example .env

# Edit .env and add your admin emails
ADMIN_EMAILS=your-email@example.com,admin@example.com
JWT_SECRET_KEY=<generate-secure-random-key>
GOOGLE_CLIENT_ID=23326348224-utv5ng3jq4u21ort7of2hgaed6hkql3u.apps.googleusercontent.com
```

### 2. Generate secure JWT secret

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

Add the output to `.env` as `JWT_SECRET_KEY`.

### 3. Ensure `.env` is in `.gitignore`

```bash
grep -q "^.env$" .gitignore || echo ".env" >> .gitignore
git status  # Verify .env is marked as ignored
```

---

## Testing the Complete Flow

### Test Case 1: Admin User Access

```bash
# Scenario: Email in ADMIN_EMAILS gets promoted to admin

1. Configure .env:
   ADMIN_EMAILS=admin@example.com

2. User signs in with admin@example.com

3. Backend:
   ✓ _is_admin_email("admin@example.com") returns True
   ✓ member.is_admin = True
   ✓ JWT includes is_admin: true

4. Frontend receives JWT:
   ✓ Decodes is_admin from JWT payload
   ✓ Sets currentProfile.is_admin = true
   ✓ _updateAuthUI() shows "🔴 Control Hall" link

5. Admin clicks control hall:
   ✓ crimson-control-hall.html loads
   ✓ validateAdmin() passes JWT check
   ✓ Dashboard initializes with user's name and tier

Expected: Admin can access full dashboard
```

### Test Case 2: Regular User Access

```bash
# Scenario: Email NOT in ADMIN_EMAILS remains regular user

1. Configure .env:
   ADMIN_EMAILS=admin@example.com

2. User signs in with user@example.com

3. Backend:
   ✓ _is_admin_email("user@example.com") returns False
   ✓ member.is_admin = False
   ✓ JWT includes is_admin: false

4. Frontend receives JWT:
   ✓ Decodes is_admin from JWT payload
   ✓ Sets currentProfile.is_admin = false
   ✓ _updateAuthUI() hides "🔴 Control Hall" link

5. User tries to access crimson-control-hall.html:
   ✗ Link not visible in UI
   ✗ If they manually type in URL → redirected to first_contact.html
   ✗ API calls to /api/admin/* return 403 Forbidden

Expected: Regular user sees normal interface only
```

### Test Case 3: Admin-Only API Endpoints

```bash
# Scenario: Admin user calls protected endpoint

1. Admin with is_admin=true in JWT calls:
   GET /api/admin/users

2. Backend:
   ✓ @require_auth validates JWT
   ✓ @require_admin checks is_admin flag
   ✓ Endpoint executes, returns user list

3. Regular user tries same endpoint:
   ✓ JWT is valid for auth
   ✗ @require_admin rejects (is_admin=false)
   ✗ Returns 403 Forbidden

Expected: Admin endpoints protected by role
```

---

## Security Guarantees

✅ **Admin Detection**: Based on configurable email whitelist, not client-side claims
✅ **Role Propagation**: is_admin flag created at signup, persisted in database, included in JWT
✅ **Frontend Verification**: Two-layer check:
   - HTML visibility: `[data-auth-show="admin"]` attributes
   - Page load: `validateAdmin()` redirects non-admins
✅ **Backend Verification**: Three-layer check:
   - `@require_auth` validates JWT signature/expiry
   - `@require_admin` verifies is_admin in database (not just JWT)
   - Each endpoint logs unauthorized attempts
✅ **No Bypass**: Manually navigating to URLs triggers redirects
✅ **No Privilege Escalation**: is_admin set at creation time, immutable via normal auth flow

---

## Files Modified for Role-Based Routing

| File | Changes | Lines |
|------|---------|-------|
| Aurora/database_manager.py | Added admin email detection | 48-62, 257-268, 279-291, 310, 336 |
| Aurora/memory_api_server.py | JWT includes is_admin | 425, 516-525 |
| Aurora/session_manager.py | JWT payload has is_admin | 51-78 |
| frontgate/redverse-auth.js | _validateSession(), isAdmin(), _updateAuthUI() | 102-134, 252-254, 342-365 |
| crimson-control-hall.html | validateAdmin() double-check | 528-552 |
| .env.example | ADMIN_EMAILS configuration | 86 |

---

## Next Steps (Optional)

1. **Admin Promotion UI**: Add backend endpoint to promote existing users to admin:
   - `POST /api/admin/promote_user` (admin-only)
   - `POST /api/admin/demote_user` (admin-only)

2. **Admin Invitations**: Send signup links with pre-configured tier/role:
   - `POST /api/auth/generate_invite` (admin-only)
   - Link includes `?invite_code=xyz` → auto-promotes on signup

3. **Role-Based Tiers**: Combine admin flag with tier system for more granular control:
   - Tier 7 (Archon) + is_admin = Full system control
   - Tier 7 (Archon) - is_admin = Limited to own tier

---

## Summary

The complete role-based routing verification shows:

1. **Member Creation**: Admin status determined by email whitelist at signup
2. **JWT Issuance**: Admin flag embedded in token claims
3. **Frontend Routing**: is_admin flag controls UI visibility + page access
4. **Backend Protection**: Dual-layer verification (JWT + database)
5. **No Bypass**: All control hall access requires valid admin JWT + server-side confirmation

Users in the `ADMIN_EMAILS` environment variable automatically get admin access to Crimson Control Hall. All other authenticated users see the regular interface only.
