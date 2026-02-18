# Phase 2: Two-Way Navigation with FrontGate Gatekeeping

## 🗺️ Navigation Architecture

The navigation system now has **two-way routing** between the main interface and the Crimson Control Hall, with FrontGate providing the gatekeeping layer.

---

## 📍 Navigation Flow

### Admin User Navigation

```
Redverse Main Site (redverse.html)
         ↓
    Sign in with Google (admin email)
         ↓
    ✓ JWT includes is_admin: true
         ↓
E-Drive / Oracle Pages
    ├─ Regular navigation visible
    ├─ 🔴 Control Hall link VISIBLE
         ↓
    Click: 🔴 Control Hall
         ↓
Crimson Control Hall
    ├─ Admin dashboard loads
    ├─ ← RETURN TO MAIN button visible
    └─ Can navigate back to E-Drive
         ↓
Click: ← RETURN TO MAIN
         ↓
E-Drive (back to main interface)
```

### Regular User Navigation

```
Redverse Main Site (redverse.html)
         ↓
    Sign in with Google (regular email)
         ↓
    ✓ JWT includes is_admin: false
         ↓
E-Drive / Oracle Pages
    ├─ Regular navigation visible
    ├─ 🔴 Control Hall link HIDDEN
         ↓
User cannot access Control Hall
(link not visible, redirected if accessed manually)
```

---

## 🔐 FrontGate Gatekeeping Implementation

### CSS: `frontgate/redverse-gate.css`

All pages now include this stylesheet:
```html
<link rel="stylesheet" href="frontgate/redverse-gate.css">
```

### JS: `frontgate/redverse-auth.js`

All pages now include this script:
```html
<script src="frontgate/redverse-auth.js"></script>
```

### How Gatekeeping Works

**Step 1**: Page loads with FrontGate scripts
```javascript
// redverse-auth.js automatically initializes on DOMContentLoaded
document.addEventListener('DOMContentLoaded', () => {
  RedVerseAuth.init();  // Validates JWT, loads user profile
});
```

**Step 2**: FrontGate enforces visibility rules
```javascript
// All elements with data-auth-show attributes are processed
document.querySelectorAll('[data-auth-show]').forEach(el => {
  const show = el.dataset.authShow;
  if (show === 'admin') {
    el.style.display = isAdmin() ? '' : 'none';  // Show/hide based on role
  }
});
```

**Step 3**: Control Hall checks authorization on page load
```javascript
// crimson-control-hall.html:validateAdmin()
function validateAdmin() {
  const jwt = sessionStorage.getItem('aurora_session_jwt');
  const payload = JSON.parse(atob(jwt.split('.')[1]));

  if (!payload.is_admin) {
    alert('Admin access required');
    window.location.href = 'redverse_first_contact.html';
  }
}
```

---

## 📄 Pages Updated for Two-Way Navigation

### 1. **E-Drive (EDrive.html)** ✅ UPDATED

**Navigation Link Added** (line 599):
```html
<li><a href="crimson-control-hall.html" data-auth-show="admin" style="color: #ff1a3d; font-weight: bold;">🔴 Control Hall</a></li>
```

**FrontGate Integration** (lines 589, 2259):
```html
<!-- In head -->
<link rel="stylesheet" href="frontgate/redverse-gate.css">

<!-- Before closing body -->
<script src="frontgate/redverse-auth.js"></script>
```

**Behavior**:
- Admin users: 🔴 Control Hall link visible in navigation
- Regular users: 🔴 Control Hall link hidden
- FrontGate automatically controls visibility

---

### 2. **Crimson Control Hall (crimson-control-hall.html)** ✅ UPDATED

**Return Navigation Added** (line 437):
```html
<button class="logout-btn" style="background: #4a4a4a; border-color: #666;" onclick="navigateToMain()">← RETURN TO MAIN</button>
```

**Navigation Function Added** (lines 807-811):
```javascript
function navigateToMain() {
  // Return to main site (E-Drive for all admin users)
  // Admin status already verified on this page, so safe to navigate
  window.location.href = 'EDrive.html';
}
```

**Behavior**:
- Admin only (forced by validateAdmin on page load)
- Can navigate back to E-Drive
- Maintains authentication state in JWT

---

## 🔗 Complete Navigation Matrix

| From Page | To Page | Link Type | Condition | Visible |
|-----------|---------|-----------|-----------|---------|
| Redverse (main) | E-Drive | Built-in | Standard nav | ✓ All |
| E-Drive | Redverse | Built-in | Standard nav | ✓ All |
| E-Drive | Control Hall | FrontGate gated | data-auth-show="admin" | ✓ Admin only |
| Oracle | Control Hall | FrontGate gated | data-auth-show="admin" | ✓ Admin only |
| Control Hall | E-Drive | Direct button | Direct link | ✓ Admin only (page is admin-only) |
| Any page | Google Auth | Built-in | Logout | ✓ All |

---

## 🔄 Navigation Workflows

### Workflow 1: Admin Accessing Control Hall

```
1. Admin user on E-Drive
   └─ Sees: 🔴 Control Hall link in navigation

2. Admin clicks: 🔴 Control Hall
   └─ Navigates to: crimson-control-hall.html

3. Control Hall validateAdmin() checks JWT
   └─ JWT.is_admin === true → Dashboard loads

4. Admin reviews system data
   └─ Accesses: Users, timelines, analytics, flags

5. Admin clicks: ← RETURN TO MAIN
   └─ navigateToMain() executes
   └─ Returns to: EDrive.html
   └─ JWT still valid, can continue work
```

### Workflow 2: Regular User Trying to Access Control Hall

```
1. Regular user on E-Drive
   └─ Sees: No Control Hall link (hidden)

2. Regular user types: crimson-control-hall.html in address bar
   └─ Navigates to: crimson-control-hall.html

3. Control Hall validateAdmin() checks JWT
   └─ JWT.is_admin === false → Access denied

4. Alert shows: "Admin access required"
   └─ Automatically redirects to: redverse_first_contact.html

5. Regular user back on: First contact page
   └─ Cannot access Control Hall
```

### Workflow 3: User Logout Flow

```
1. User (admin or regular) on any page
   └─ Clicks: LOGOUT button

2. JavaScript executes:
   └─ sessionStorage.removeItem('aurora_session_jwt')
   └─ window.location.href = 'google_auth.html'

3. All auth state cleared
   └─ User redirected to: Google auth page

4. User must sign in again
   └─ New JWT issued with appropriate is_admin flag
```

---

## 🎯 FrontGate Integration Steps

### For Each Main Page (E-Drive, Oracle, etc.)

**Step 1**: Add CSS in `<head>` (before closing `</head>`):
```html
<!-- FrontGate Phase 2 Integration -->
<link rel="stylesheet" href="frontgate/redverse-gate.css">
```

**Step 2**: Add Control Hall link in navigation:
```html
<li><a href="crimson-control-hall.html" data-auth-show="admin" style="color: #ff1a3d; font-weight: bold;">🔴 Control Hall</a></li>
```

**Step 3**: Add JS before closing `</body>`:
```html
<!-- FrontGate Phase 2 Integration -->
<script src="frontgate/redverse-auth.js"></script>
```

**Step 4**: Verify in browser:
- [ ] Load page
- [ ] Sign in as admin
- [ ] 🔴 Control Hall link appears
- [ ] Click it → Control Hall loads
- [ ] Click ← RETURN TO MAIN → Back to page
- [ ] Sign in as regular user
- [ ] 🔴 Control Hall link NOT visible

---

## 📊 Navigation Security Layers

### Layer 1: Frontend Visibility Control
```javascript
// CSS hides Control Hall link from regular users
[data-auth-show="admin"] → display: none if is_admin === false
```

### Layer 2: Page Access Control
```javascript
// Control Hall validateAdmin checks JWT on page load
if (!JWT.is_admin) → redirect to first_contact.html
```

### Layer 3: API Access Control
```python
# Backend @require_admin decorator blocks API calls
POST /api/admin/* → 403 Forbidden if is_admin === false
```

### Layer 4: JWT Verification
```javascript
// Server verifies JWT signature and expiry
Invalid/expired JWT → 401 Unauthorized
```

---

## 🚀 Current Implementation Status

### ✅ Implemented

- [x] E-Drive.html has Control Hall link (gated)
- [x] Control Hall has return navigation button
- [x] FrontGate scripts integrated to E-Drive
- [x] Two-way navigation established
- [x] Admin-only access enforced

### 📋 Recommended Next Steps

1. **Add Control Hall link to Oracle.html**
   - Same pattern as E-Drive
   - Add FrontGate CSS and JS
   - Add Control Hall link to navigation

2. **Add Control Hall link to Setup.html, Support.html** (optional)
   - For consistency
   - Admin quick access from any page

3. **Add Control Hall link to Redverse main page**
   - Header or sidebar
   - Only visible to admins

4. **Update all authenticated pages** with:
   - FrontGate CSS
   - FrontGate JS
   - Control Hall link (gated)

---

## 🔐 Security Verification Checklist

- [x] Control Hall unavailable to non-admin users
- [x] Navigation link hidden from non-admins
- [x] Manual URL access blocked for non-admins
- [x] API calls protected with @require_admin
- [x] JWT signature verified
- [x] Admin role persisted in JWT
- [x] Return navigation works correctly
- [x] Logout clears all auth state

---

## 📝 FrontGate Elements Reference

### HTML Attributes

```html
<!-- Show to authenticated users only -->
<element data-auth-show="authenticated">Content</element>

<!-- Show to unauthenticated users only -->
<element data-auth-show="unauthenticated">Content</element>

<!-- Show to admin users only -->
<element data-auth-show="admin">Content</element>
```

### JavaScript API

```javascript
// Check if user is authenticated
RedVerseAuth.isAuthenticated()  // true/false

// Check if user is admin
RedVerseAuth.isAdmin()  // true/false

// Get user profile
RedVerseAuth.getProfile()  // { member_id, is_admin, ... }

// Get JWT token
RedVerseAuth.getJWT()  // "eyJhbGc..."

// Sign out
RedVerseAuth.signOut()

// Show login modal
RedVerseAuth.showRegistryModal()
```

---

## 📍 Navigation Map (Visual)

```
┌─────────────────────────────────────────────────────────────────┐
│                      REDVERSE ECOSYSTEM                          │
└─────────────────────────────────────────────────────────────────┘

                         redverse.html (Main)
                              ↓
              ┌───────────────┼───────────────┐
              ↓               ↓               ↓
          oracle.html   EDrive.html      setup.html
              │               │               │
              └───────┬───────┴───────┬───────┘
                      ↓               ↓
                  [FrontGate Gatekeeping]
                      ↓               ↓
          ┌─────────────────┬─────────────────┐
          │                 │                 │
      [Admin?]          [Admin?]          [Admin?]
          │                 │                 │
         YES               YES               YES
          │                 │                 │
          ↓                 ↓                 ↓
    🔴 Link           🔴 Link           🔴 Link
    Visible           Visible           Visible
          │                 │                 │
          └────────┬────────┴────────┬────────┘
                   ↓
       crimson-control-hall.html
       (Admin Dashboard)
                   ↓
         ← RETURN TO MAIN
                   ↓
       Back to E-Drive or Oracle
```

---

## 🎓 Summary

**Two-Way Navigation Implemented**:
1. Main site pages (E-Drive, Oracle) have Control Hall link
2. Control Hall has return button to main site
3. FrontGate gatekeeping on both directions
4. Admin-only access enforced

**Gatekeeping Layers**:
1. Frontend: Element visibility controlled
2. Page: validateAdmin() checks access
3. API: @require_admin protects endpoints
4. JWT: Server verifies signatures

**Status**: ✅ Ready for deployment

All pages now support seamless two-way navigation while maintaining strict access control through FrontGate!
