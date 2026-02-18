# Phase 2: Admin Role-Based Routing - User Journey Examples

## Visual Example 1: Admin User Journey

### Admin Signs In

```
┌────────────────────────────────────────────────────────┐
│ RedVerse First Contact Page                           │
│                                                        │
│ [SIGN IN WITH GOOGLE]                                │
└────────────────────────────────────────────────────────┘

User: admin@example.com
Clicks: [SIGN IN WITH GOOGLE]
    ↓

┌────────────────────────────────────────────────────────┐
│ Google OAuth Flow                                     │
│                                                        │
│ "admin@example.com wants to access RedVerse"         │
│ [ALLOW]                                              │
└────────────────────────────────────────────────────────┘

    ↓ Returns to backend /api/auth/validate_google_token

┌────────────────────────────────────────────────────────┐
│ Backend Processing:                                    │
│                                                        │
│ ✓ Email: admin@example.com                           │
│ ✓ Check: is_admin_email("admin@example.com")?        │
│ ✓ ADMIN_EMAILS = ["admin@example.com", "staff@x"]   │
│ ✓ Result: YES → is_admin = True                      │
│ ✓ Create JWT with is_admin: true                     │
│ ✓ Return session_token to frontend                   │
└────────────────────────────────────────────────────────┘

    ↓ Frontend receives JWT

┌────────────────────────────────────────────────────────┐
│ Browser Storage:                                      │
│                                                        │
│ sessionStorage.aurora_session_jwt =                  │
│ "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJtZW1iZXJ..." │
│                                                        │
│ (contains: is_admin: true)                           │
└────────────────────────────────────────────────────────┘

    ↓ Page initializes

┌────────────────────────────────────────────────────────┐
│ RedVerse First Contact Page (Rendered)               │
│                                                        │
│ Welcome, admin@example.com (Admin)                   │
│ Your tier: Wanderer                                   │
│                                                        │
│ Main Menu:                                            │
│ [📚 My Memories] [🔴 Control Hall] [📋 Settings]    │
│                  ↑ VISIBLE (only for admins)         │
│                 (hidden for regular users)           │
│                                                        │
│ Ready to explore...                                  │
└────────────────────────────────────────────────────────┘

    ↓ Admin clicks [🔴 Control Hall]

┌────────────────────────────────────────────────────────┐
│ Crimson Control Hall - Admin Dashboard               │
│                                                        │
│ 🔴 CRIMSON CONTROL HALL                              │
│ ADMIN: admin@example.com                             │
│ TIER: Wanderer                                        │
│ [LOGOUT]                                              │
│                                                        │
│ ┌─────────────────┐  ┌──────────────────────────────┐│
│ │ OPERATIONS      │  │ SYSTEM OVERVIEW              ││
│ │ 📊 Overview     │  │ Total Users: 42              ││
│ │ 👥 Users        │  │ Total Memories: 5,247        ││
│ │ 📝 Timeline     │  │ Avg per User: 124.9          ││
│ │ 🔍 Search      │  │ 💚 Emotion: 67% neutral      ││
│ │ 💚 Emotions     │  └──────────────────────────────┘│
│ │ 🕸️ Network      │                                  │
│ └─────────────────┘                                  │
│                                                        │
│ ✓ Full admin access granted                          │
│ ✓ Can view user timelines                            │
│ ✓ Can search memories                                │
│ ✓ Can add flags & observations                       │
│ ✓ Can analyze emotions & sharing graph               │
└────────────────────────────────────────────────────────┘
```

---

## Visual Example 2: Regular User Journey

### Regular User Signs In

```
┌────────────────────────────────────────────────────────┐
│ RedVerse First Contact Page                           │
│                                                        │
│ [SIGN IN WITH GOOGLE]                                │
└────────────────────────────────────────────────────────┘

User: student@gmail.com (NOT in ADMIN_EMAILS)
Clicks: [SIGN IN WITH GOOGLE]
    ↓

┌────────────────────────────────────────────────────────┐
│ Google OAuth Flow                                     │
│                                                        │
│ "student@gmail.com wants to access RedVerse"        │
│ [ALLOW]                                              │
└────────────────────────────────────────────────────────┘

    ↓ Returns to backend /api/auth/validate_google_token

┌────────────────────────────────────────────────────────┐
│ Backend Processing:                                    │
│                                                        │
│ ✓ Email: student@gmail.com                          │
│ ✓ Check: is_admin_email("student@gmail.com")?       │
│ ✓ ADMIN_EMAILS = ["admin@example.com", "staff@x"]  │
│ ✓ Result: NO → is_admin = False                     │
│ ✓ Create JWT with is_admin: false                   │
│ ✓ Return session_token to frontend                  │
└────────────────────────────────────────────────────────┘

    ↓ Frontend receives JWT

┌────────────────────────────────────────────────────────┐
│ Browser Storage:                                      │
│                                                        │
│ sessionStorage.aurora_session_jwt =                  │
│ "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJtZW1iZXJ..." │
│                                                        │
│ (contains: is_admin: false)                          │
└────────────────────────────────────────────────────────┘

    ↓ Page initializes

┌────────────────────────────────────────────────────────┐
│ RedVerse First Contact Page (Rendered)               │
│                                                        │
│ Welcome, student@gmail.com                           │
│ Your tier: Wanderer                                   │
│                                                        │
│ Main Menu:                                            │
│ [📚 My Memories] [Settings]                          │
│          ↑ VISIBLE (for all users)                   │
│                                                        │
│ Note: 🔴 Control Hall link is HIDDEN                 │
│ (user doesn't see it at all)                         │
│                                                        │
│ Ready to explore...                                  │
└────────────────────────────────────────────────────────┘

    ↓ Regular user tries to manually access Control Hall
      by typing in address bar: crimson-control-hall.html

┌────────────────────────────────────────────────────────┐
│ Crimson Control Hall - Admin Only                    │
│                                                        │
│ 🔴 CRIMSON CONTROL HALL                              │
│                                                        │
│ [ALERT BOX]                                          │
│ ✗ Admin access required                              │
│ [OK]                                                  │
│                                                        │
│ (automatically redirects to first_contact.html)      │
└────────────────────────────────────────────────────────┘

    ↓ API Protection (if they try to hack the API)

┌────────────────────────────────────────────────────────┐
│ Attempting: GET /api/admin/users                     │
│                                                        │
│ Request JWT has: is_admin: false                    │
│                                                        │
│ Response:                                             │
│ ✗ 403 Forbidden                                      │
│ {"error": "Admin privileges required"}               │
│                                                        │
│ (Even if they have a valid JWT, wrong role = blocked)│
└────────────────────────────────────────────────────────┘

    ↓ Regular user continues with normal features

┌────────────────────────────────────────────────────────┐
│ E-Drive Page (Regular User View)                    │
│                                                        │
│ My Conversations                                      │
│ 📚 Previously asked: "What is quantum computing?"   │
│ 📚 Previously asked: "How do I learn Python?"       │
│                                                        │
│ Ask E-Drive:                                          │
│ [Tell me about particle physics...]                  │
│ [SEND]                                                │
│                                                        │
│ ✓ Can save conversations                             │
│ ✓ Can view memory                                    │
│ ✓ Cannot access admin features                       │
└────────────────────────────────────────────────────────┘
```

---

## Three-Way Comparison: Different User Types

### Layout Changes by User Type

```
╔══════════════════════════════════════════════════════════════════════╗
║                         REGULAR USER                                 ║
╠══════════════════════════════════════════════════════════════════════╣
║ RedVerse Main Page                                                   ║
║                                                                      ║
║ Welcome, user@gmail.com                                             ║
║ [📚 My Memories]  [Settings]                                        ║
║                                                                      ║
║ • Can access: Tier 1-3 content                                      ║
║ • Cannot see: Control Hall link                                     ║
║ • Cannot access: /api/admin/* endpoints                             ║
║ • Last login: 2 hours ago                                           ║
╚══════════════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════════════╗
║                         TIER 4+ USER                                 ║
╠══════════════════════════════════════════════════════════════════════╣
║ RedVerse Main Page                                                   ║
║                                                                      ║
║ Welcome, sage@example.com (Sage)                                    ║
║ [📚 My Memories]  [⚡ Memory Sharing]  [Settings]                   │
║                                                                      ║
║ • Can access: Tier 4 content (memory sharing)                       ║
║ • Cannot see: Control Hall link                                     ║
║ • Cannot access: /api/admin/* endpoints                             ║
║ • Memory Mode: Trusted sharing with 3 users                         ║
║ • Last login: Just now                                              ║
╚══════════════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════════════╗
║                         ADMIN USER                                   ║
╠══════════════════════════════════════════════════════════════════════╣
║ RedVerse Main Page                                                   ║
║                                                                      ║
║ Welcome, admin@example.com (Admin)                                  ║
║ [📚 My Memories]  [🔴 Control Hall]  [Settings]                    │
║                                                                      ║
║ • Can access: Tier 1-7 content                                      ║
║ • CAN SEE: Control Hall link (emphasized)                           ║
║ • CAN ACCESS: /api/admin/* endpoints                                ║
║ • Admin Role: System administrator                                  ║
║ • Last login: Just now                                              ║
║ • Active Sessions: 2 admin users online                             ║
╚══════════════════════════════════════════════════════════════════════╝
```

---

## Authentication Flow Sequence Diagram

```
┌──────────┐                    ┌──────────┐                ┌──────────┐
│ Frontend │                    │ Backend  │                │ Database │
└──────────┘                    └──────────┘                └──────────┘
     │                               │                            │
     │──── Google Sign-In ───────────→│                           │
     │    (email: admin@example.com)  │                           │
     │                               │                           │
     │                               │─────Check ADMIN_EMAILS───→│
     │                               │    in .env settings       │
     │                               │←─────is_admin: true────────│
     │                               │                           │
     │←──────JWT response────────────│                           │
     │(is_admin: true in payload)    │                           │
     │                               │                           │
     │ Decode JWT                   │                           │
     │ Extract is_admin: true       │                           │
     │ Store in currentProfile      │                           │
     │                               │                           │
     │ Call _updateAuthUI()         │                           │
     │ Show [data-auth-show="admin"]│                           │
     │                               │                           │
     │──[🔴 Control Hall link visible]                          │
     │                               │                           │
     │─────Click Control Hall───────→│                           │
     │                               │                           │
     │←──crimson-control-hall.html──│                           │
     │    (validate on page load)    │                           │
     │                               │                           │
     │ validateAdmin() decodes JWT  │                           │
     │ Checks: is_admin === true    │                           │
     │ Access granted!              │                           │
     │                               │                           │
     │ Load dashboard               │                           │
     │                               │                           │
     │─────GET /api/admin/users────→│                           │
     │                               │─────@require_admin check──│
     │                               │────is_admin in DB: true───│
     │                               │←────Access granted────────│
     │←────[User list data]──────────│                           │
     │                               │                           │
     ▼                               ▼                            ▼
```

---

## Configuration Examples

### Example 1: Single Admin

**.env**:
```env
ADMIN_EMAILS=me@gmail.com
JWT_SECRET_KEY=eB7k_pqX9nW2mL5qR8vY3uJ2wZ4xGhK1jM6pQ0sT9uV
```

**Result**: Only `me@gmail.com` gets admin access.

### Example 2: Team of Admins

**.env**:
```env
ADMIN_EMAILS=alice@company.com,bob@company.com,charlie@company.com
JWT_SECRET_KEY=eB7k_pqX9nW2mL5qR8vY3uJ2wZ4xGhK1jM6pQ0sT9uV
```

**Result**: Alice, Bob, and Charlie all get admin access. Everyone else is regular users.

### Example 3: Mixed Domains

**.env**:
```env
ADMIN_EMAILS=admin@example.com,staff@university.edu,moderator@company.org
JWT_SECRET_KEY=eB7k_pqX9nW2mL5qR8vY3uJ2wZ4xGhK1jM6pQ0sT9uV
```

**Result**: Three admins from different email domains.

### Example 4: No Admins (All Regular Users)

**.env**:
```env
ADMIN_EMAILS=
JWT_SECRET_KEY=eB7k_pqX9nW2mL5qR8vY3uJ2wZ4xGhK1jM6pQ0sT9uV
```

**Result**: No one gets admin access. Control Hall is hidden from all users.

---

## Browser Developer Tools: JWT Inspection

### How to Inspect Your JWT

**Step 1**: Open browser DevTools
```
F12 → Application/Storage tab → Session Storage
```

**Step 2**: Find the JWT
```
Key: aurora_session_jwt
Value: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJtZW1iZXJfaWQ...
```

**Step 3**: Decode it (in Console tab)
```javascript
const token = sessionStorage.getItem('aurora_session_jwt');
const parts = token.split('.');
const payload = JSON.parse(atob(parts[1]));
console.log(payload);
```

**Step 4**: Check is_admin claim
```javascript
console.log("Is admin?", payload.is_admin);  // true or false
```

**Output for Admin**:
```javascript
{
  member_id: "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  thread_id: "f0e1d2c3-b4a5-9876-5432-109876543210",
  email: "admin@example.com",
  display_name: "Admin User",
  access_tier: 1,
  tier_name: "Wanderer",
  google_sub: "118329874562908347",
  is_admin: true,  // ← Admin flag
  iat: 1708406421,
  exp: 1708492821
}
```

**Output for Regular User**:
```javascript
{
  member_id: "x1y2z3a4-b5c6-7890-uvwx-yz1234567890",
  thread_id: "z0y1x2w3-v4u5-9876-5432-109876543210",
  email: "user@gmail.com",
  display_name: "Regular User",
  access_tier: 1,
  tier_name: "Wanderer",
  google_sub: "987654321098765432",
  is_admin: false,  // ← Regular user (no admin)
  iat: 1708406421,
  exp: 1708492821
}
```

---

## Error Message Reference

### When Things Go Wrong

**Error 1: "Admin access required"**
```
Cause: User clicked Control Hall but is_admin=false
Fix:   Add user email to ADMIN_EMAILS in .env
       Restart Aurora server
       User re-signs in
```

**Error 2: "Admin privileges required" (403)**
```
Cause: User tried to call /api/admin/* endpoint without is_admin=true
Fix:   User emails not in ADMIN_EMAILS
       @require_admin decorator blocked them
       Non-admin users cannot access these endpoints
```

**Error 3: Control Hall link not visible**
```
Cause: is_admin=false in JWT
Fix:   Check console:
       JSON.parse(atob(sessionStorage.getItem('aurora_session_jwt').split('.')[1]))
       Verify: is_admin should be true
       If false: User email not in ADMIN_EMAILS
```

**Error 4: "Not authenticated"**
```
Cause: No JWT in sessionStorage (not logged in)
Fix:   User must sign in with Google first
       Control Hall requires authentication
```

---

## Summary: What Users See

| Feature | Tier 1 User | Tier 4 User | Admin User |
|---------|:----------:|:----------:|:---------:|
| Sign in with Google | ✓ | ✓ | ✓ |
| Save conversations | ✓ | ✓ | ✓ |
| View own memories | ✓ | ✓ | ✓ |
| Share memories | ✗ | ✓ | ✓ |
| See Control Hall link | ✗ | ✗ | ✓ |
| Access Control Hall | ✗ | ✗ | ✓ |
| View all users | ✗ | ✗ | ✓ |
| View user timelines | ✗ | ✗ | ✓ |
| Search all memories | ✗ | ✗ | ✓ |
| Add admin flags | ✗ | ✗ | ✓ |
| View sharing graph | ✗ | ✗ | ✓ |
| Analyze emotions | ✗ | ✗ | ✓ |

---

## Complete Implementation: Ready for Deployment

✅ Code changes made
✅ Python syntax verified
✅ JWT payload includes is_admin
✅ Frontend routing respects is_admin
✅ Backend endpoints protected
✅ Configuration template provided
✅ .env excluded from git
✅ Documentation complete

**Status: READY FOR PRODUCTION**

Configure your `.env` file with admin emails, restart the server, and your admin role-based routing is live!
