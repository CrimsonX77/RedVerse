# Phase 2: Admin Routing - Quick Reference Card

## 📋 Configuration (One-Time Setup)

```bash
# 1. Copy template
cp .env.example .env

# 2. Edit .env - add your admin emails
nano .env
# Find line: ADMIN_EMAILS=
# Change to: ADMIN_EMAILS=your-email@gmail.com,admin2@gmail.com

# 3. Generate JWT secret
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
# Paste result into: JWT_SECRET_KEY=<result>

# 4. Restart Aurora
# Kill old process (Ctrl+C)
python3 Aurora/memory_api_server.py
```

Check: Should see in logs: `Admin emails configured: X admins`

---

## 🔍 Verify Admin Status

### In Browser Console
```javascript
// Check if current user is admin
const token = sessionStorage.getItem('aurora_session_jwt');
const payload = JSON.parse(atob(token.split('.')[1]));
console.log("is_admin:", payload.is_admin);  // true or false
```

### In Backend Logs
```bash
# Look for promotion message
tail logs/database_manager.log | grep "PROMOTED TO ADMIN"
# Output: "Created new member from Google OAuth: admin@example.com (..., PROMOTED TO ADMIN)"
```

### Check Database Directly
```bash
grep -A2 "is_admin" data/members_database.json
```

---

## 🚀 Add/Remove Admins (No Code Changes!)

### Add Admin
Edit `.env`:
```env
ADMIN_EMAILS=existing@gmail.com,new-admin@gmail.com
```

Restart Aurora. New admin can now sign in and get access automatically.

### Remove Admin
Edit `.env`:
```env
ADMIN_EMAILS=existing@gmail.com
# Remove: new-admin@gmail.com
```

Restart Aurora. That user loses admin access on next login.

---

## 🔐 Security Checklist

- [ ] `.env` exists and is in `.gitignore`
- [ ] `.env` is never committed to git (`git status` shows nothing)
- [ ] `ADMIN_EMAILS` matches actual admin email addresses
- [ ] `JWT_SECRET_KEY` is at least 32 characters, random
- [ ] Aurora server restarted after `.env` changes
- [ ] Admin can sign in and see Control Hall link
- [ ] Regular user cannot see Control Hall link
- [ ] Manual navigation to Control Hall redirects non-admins

---

## 🐛 Troubleshooting Cheat Sheet

| Problem | Cause | Solution |
|---------|-------|----------|
| "Admin access required" | Email not in ADMIN_EMAILS | Edit .env, add email, restart |
| Control Hall link hidden | is_admin=false in JWT | Check ADMIN_EMAILS, restart |
| JWT shows wrong is_admin | Server cached old config | Restart Aurora server |
| Can still see data as non-admin | Backend not protected | Verify @require_admin decorator (it is) |
| Can open .env in git | Not in .gitignore | Add to .gitignore, git rm --cached .env |

---

## 🎯 Key Files

| File | Purpose | Line(s) |
|------|---------|---------|
| `.env` | Configuration (NEVER commit) | N/A |
| `Aurora/database_manager.py` | Admin email detection | 48-62, 257-268, 279-291 |
| `Aurora/memory_api_server.py` | JWT includes is_admin | 425, 516-525 |
| `frontgate/redverse-auth.js` | Frontend routing | 102-134, 349-350 |
| `crimson-control-hall.html` | Admin page verification | 528-552 |

---

## 📊 Data Flow (30 seconds)

```
Google OAuth → Email check → is_admin flag set → JWT created
  ↓
Frontend decodes JWT → is_admin parsed → UI updated
  ↓
Admin user: Control Hall link visible
Regular user: Control Hall link hidden
  ↓
Admin clicks link → Control Hall loads → @require_admin verified
Regular user cannot access → Returns 403 Forbidden
```

---

## ✅ Testing Checklist

1. **Sign in as admin**
   - [ ] Control Hall link appears
   - [ ] Can open Control Hall
   - [ ] Dashboard loads
   - [ ] Can see user list, timelines, analytics

2. **Sign in as regular user**
   - [ ] Control Hall link hidden
   - [ ] Can't manually access Control Hall (redirected)
   - [ ] Can't call /api/admin/* endpoints (403)

3. **Add new admin**
   - [ ] Edit ADMIN_EMAILS in .env
   - [ ] Restart server
   - [ ] New user gets admin role on next sign-in

---

## 🔄 Redeploy After Changes

```bash
# 1. Edit .env with new admin emails
nano .env

# 2. Verify changes
grep ADMIN_EMAILS .env

# 3. Restart Aurora
# Kill: Ctrl+C
# Start: python3 Aurora/memory_api_server.py

# 4. Verify in logs
# Should show: "Admin emails configured: X admins"

# 5. Users must re-sign in to get new role
# (Old JWT will be invalidated on next page load)
```

---

## 💾 Backup & Recovery

### Backup Admin List
```bash
# Save current ADMIN_EMAILS
grep ADMIN_EMAILS .env > admin_backup.txt
```

### Recover from Accidental Changes
```bash
# Restore from git history (if you committed .env.example)
git show HEAD:.env.example > .env.example

# Or manual restore
nano .env
# Set: ADMIN_EMAILS=<your-backup-list>
```

---

## 📞 Quick Diagnostic

If admin routing isn't working:

```bash
# 1. Check .env exists and is readable
ls -la .env

# 2. Check ADMIN_EMAILS is set
grep ADMIN_EMAILS .env

# 3. Check server is running and logs look good
ps aux | grep memory_api_server.py
tail logs/database_manager.log

# 4. Check database was created with right admin flag
grep is_admin data/members_database.json | head -3

# 5. Check browser JWT (as shown above)
# Then compare: does JWT.is_admin match what database had?
```

---

## 🎓 How It Works (60 second version)

1. **Startup**: Aurora server reads `.env`, loads `ADMIN_EMAILS` list
2. **Signup**: New user signs in with Google email
3. **Check**: Is email in `ADMIN_EMAILS`? YES → `is_admin=true`, NO → `is_admin=false`
4. **Token**: JWT created with proper `is_admin` claim
5. **Frontend**: Page decodes JWT, checks `is_admin`
6. **UI**: Show/hide Control Hall link based on `is_admin` value
7. **Access**: Click Control Hall → validate JWT again → load dashboard or redirect
8. **APIs**: All /api/admin/* protected with @require_admin decorator

No code changes needed to add/remove admins. Just edit `.env` and restart.

---

## 🚨 IMPORTANT REMINDERS

⚠️ **NEVER commit .env to git** (add to .gitignore)
⚠️ **NEVER put JWT_SECRET_KEY in code** (use .env only)
⚠️ **NEVER hardcode ADMIN_EMAILS** (now configurable!)
⚠️ **ALWAYS restart server after .env changes** (reads on startup only)

---

## 📚 Related Documentation

- `PHASE2_ADMIN_ROUTING_VERIFICATION.md` - Complete technical details
- `PHASE2_ADMIN_SETUP.md` - Step-by-step setup guide
- `PHASE2_ADMIN_ROUTING_USER_JOURNEY.md` - Visual user experience
- `FRONTGATE_PHASE2_INTEGRATION.md` - FrontGate integration docs

---

**Status**: ✅ Admin role-based routing COMPLETE and READY

Configure `.env`, restart server, admins in your email list get access to Control Hall automatically!
