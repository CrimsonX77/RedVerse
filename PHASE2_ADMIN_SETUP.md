# Phase 2: Admin Setup Quick Start

## 1. Create your `.env` file

Copy the template:
```bash
cp .env.example .env
```

## 2. Configure Admin Emails

Edit `.env` and find the line with `ADMIN_EMAILS`. Add your email addresses:

```env
# ─── ADMIN CONFIGURATION ───────────────────────────────────
# Email addresses of admin users (comma-separated)
# These users get access to Crimson Control Hall
ADMIN_EMAILS=your-email@gmail.com,admin@example.com
```

## 3. Generate a Secure JWT Secret

Run this command to generate a strong random key:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

Output will look like:
```
eB7k_pqX9nW2mL5qR8vY3uJ2wZ4xGhK1jM6pQ0sT9uV
```

## 4. Add the JWT Secret to `.env`

Find the JWT line:
```env
# ─── JWT AUTHENTICATION (Phase 2) ───────────────────────
JWT_SECRET_KEY=your-super-secret-jwt-key-change-this-in-production
```

Replace with your generated key:
```env
JWT_SECRET_KEY=eB7k_pqX9nW2mL5qR8vY3uJ2wZ4xGhK1jM6pQ0sT9uV
```

## 5. Verify `.env` is Hidden from Git

```bash
# Check that .env is not tracked
git status | grep .env

# Should show: nothing (or "nothing to commit")
# Should NOT show: .env (in green/red)
```

If `.env` is tracked, remove it:
```bash
git rm --cached .env
git commit -m "Remove .env from tracking (add to gitignore)"
```

## 6. Test Admin Access

Start the Aurora API server:
```bash
cd /home/crimson/Desktop/Redverse
python3 Aurora/memory_api_server.py
```

Expected output:
```
Admin emails configured: 1 admins
```

Sign in with your admin email, then:

1. **Check JWT in browser console**:
   ```javascript
   // In browser DevTools Console:
   sessionStorage.getItem('aurora_session_jwt')

   // Decode to verify is_admin claim:
   JSON.parse(atob(
     sessionStorage.getItem('aurora_session_jwt').split('.')[1]
   ))

   // Should show:
   // { member_id: "...", is_admin: true, ... }
   ```

2. **Verify Control Hall Link Appears**:
   - If `is_admin: true` → See "🔴 Control Hall" link
   - If `is_admin: false` → Link is hidden

3. **Click Control Hall**:
   - Should load dashboard
   - Shows your name and tier
   - Access to all admin tabs

## 7. Add More Admins

Simply add more emails to `.env`:

```env
ADMIN_EMAILS=admin1@gmail.com,admin2@gmail.com,admin3@gmail.com
```

No code changes needed! Admins are determined entirely by the environment variable.

## 8. Troubleshooting

### Admin email not being recognized

**Problem**: You signed up with `admin@gmail.com` but it's not showing admin features.

**Check 1**: Verify `.env` has the email:
```bash
grep ADMIN_EMAILS .env
```

**Check 2**: Check the format (case doesn't matter, but no extra spaces):
```env
# ✓ Correct
ADMIN_EMAILS=admin@gmail.com,staff@gmail.com

# ✗ Wrong (extra space)
ADMIN_EMAILS=admin@gmail.com, staff@gmail.com

# ✗ Wrong (case doesn't matter but format does)
ADMIN_EMAILS=admin@Gmail.com  ← Database stores lowercase, but this works
```

**Check 3**: Restart the Aurora server:
```bash
# Kill the old server (Ctrl+C)
# Then restart:
python3 Aurora/memory_api_server.py
```

**Check 4**: Clear browser storage and re-login:
```javascript
// In DevTools Console:
sessionStorage.clear()
localStorage.clear()
// Then reload the page and sign in again
```

### Control Hall link not appearing

**Problem**: You're logged in as admin but don't see the 🔴 Control Hall link.

**Check 1**: Verify you're actually admin in JWT:
```javascript
const token = sessionStorage.getItem('aurora_session_jwt');
if (!token) console.log("No JWT found - are you logged in?");
const payload = JSON.parse(atob(token.split('.')[1]));
console.log("is_admin:", payload.is_admin);
```

**Check 2**: Verify the HTML has the admin element:
```html
<!-- In your HTML file, look for: -->
<a data-auth-show="admin" href="crimson-control-hall.html">
  🔴 Control Hall
</a>
```

If not present, add it manually to the header/menu.

**Check 3**: Check browser console for errors:
```
F12 → Console tab
Look for any red errors or warnings
```

### "Admin access required" when opening Control Hall

**Problem**: You click Control Hall but get redirected with error.

**Check 1**: Verify JWT has is_admin claim:
```javascript
const token = sessionStorage.getItem('aurora_session_jwt');
console.log(JSON.parse(atob(token.split('.')[1])));
```

**Check 2**: Check database has the is_admin flag:
```bash
# In Aurora logs, look for:
# "Created new member from Google OAuth: your-email@gmail.com (..., PROMOTED TO ADMIN)"

# Or check the database directly:
cat data/members_database.json | grep is_admin
```

**Check 3**: Restart the server: the database manager loads ADMIN_EMAILS on initialization
```bash
# Kill old server
# Check your .env has the right email
# Restart server
python3 Aurora/memory_api_server.py
```

## Complete Setup Checklist

- [ ] `.env` file created from `.env.example`
- [ ] `ADMIN_EMAILS` configured with your email(s)
- [ ] `JWT_SECRET_KEY` generated and added to `.env`
- [ ] `.env` is in `.gitignore` (already done)
- [ ] Aurora server restarted after `.env` changes
- [ ] Signed in with email from `ADMIN_EMAILS`
- [ ] JWT in browser shows `is_admin: true`
- [ ] Control Hall link visible in UI
- [ ] Control Hall loads without redirect warning
- [ ] Can view user list, timelines, analytics in dashboard

Once all boxes checked, admin role-based routing is complete! 🎉
