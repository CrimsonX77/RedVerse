# Google Auth Troubleshooting Guide

Complete reference for diagnosing and fixing common authentication issues.

## Quick Diagnostics

### Server won't start

**Error:** `ModuleNotFoundError: No module named 'flask'`

```bash
# Solution: Activate virtual environment
source venv/bin/activate

# Then run:
pip install -r requirements.txt
python app.py
```

**Error:** `Port 8800 already in use`

```bash
# Find process using port
lsof -i :8800

# Kill process
kill -9 <PID>

# Or use different port
PORT=9000 python app.py
```

**Error:** `FileNotFoundError: client_secret_*.json`

```bash
# Verify credentials file exists
ls -la client_secret_*.json

# If missing:
# 1. Go to https://console.cloud.google.com/apis/credentials
# 2. Download OAuth 2.0 Client ID (Web application)
# 3. Rename to: client_secret_999940301372-lsv85hnhe6ucju10uhhg2u36k1j8is9f.apps.googleusercontent.com.json
# 4. Place in project root: /home/crimson/Desktop/Laptop/
```

---

## Authentication Issues

### Google Sign-In button not appearing

**Problem:** Page loads but no Google Sign-In button visible

**Diagnosis:**
```bash
# Check browser console (F12) for errors
# Look for: "Uncaught TypeError" or "Cannot find GSI client"
```

**Solution:**
```html
<!-- Ensure this is in HEAD or before closing BODY -->
<script src="https://accounts.google.com/gsi/client" async defer></script>

<!-- Check Client ID is correct -->
<script src="js/auth-client.js" 
  data-client-id="999940301372-lsv85hnhe6ucju10uhhg2u36k1j8is9f.apps.googleusercontent.com">
</script>

<!-- Verify auth-client.js loads without errors -->
<!-- Open Network tab in F12 and check js/auth-client.js loads with 200 status -->
```

### "Redirect URI mismatch" error

**Error:** `redirect_uri_mismatch: The redirect URI in the request does not match the registered one`

**Cause:** Your OAuth redirect URL doesn't match Google Console settings

**Solution:**
1. Check current `GOOGLE_REDIRECT_URI` in `.env`:
```bash
grep GOOGLE_REDIRECT_URI .env
# Should show: http://localhost:8800/auth/google/callback
```

2. Update Google Cloud Console:
   - Go to https://console.cloud.google.com/apis/credentials
   - Click your OAuth 2.0 Client ID
   - Under "Authorized redirect URIs", ensure these exist:
     - `http://localhost:8800/auth/google/callback`
     - `http://127.0.0.1:8800/auth/google/callback`

3. Restart server:
```bash
python app.py
```

### "Invalid client" error

**Error:** `invalid_client: The OAuth client was not found`

**Cause:** Client ID in code doesn't match Google Console or credentials file is wrong

**Solution:**
```bash
# 1. Verify Client ID in credentials file
cat client_secret_*.json | grep client_id

# 2. Update .env with correct GOOGLE_CLIENT_SECRETS path
echo "GOOGLE_CLIENT_SECRETS=/home/crimson/Desktop/Laptop/client_secret_999940301372-lsv85hnhe6ucju10uhhg2u36k1j8is9f.apps.googleusercontent.com.json" >> .env

# 3. Verify Client ID in auth-client.js script tag matches
grep data-client-id login.html
# Should be: 999940301372-lsv85hnhe6ucju10uhhg2u36k1j8is9f.apps.googleusercontent.com

# 4. Restart server
python app.py
```

### Token verification fails

**Error:** `invalid_token: Token is not valid or expired`

**Cause:** Session expired, invalid Client ID, or token verification issue

**Debug:**
```python
# In auth.py, add debugging to verify_oauth2_token():
import logging
logging.basicConfig(level=logging.DEBUG)

# Then check logs for:
# - Token issuer verification failures
# - Client ID mismatches
# - Token expiration
```

**Solution:**
```bash
# Clear cookies and session
# 1. Open DevTools (F12) → Application → Cookies → Delete all
# 2. Clear localStorage (Console tab):
localStorage.clear()

# 3. Refresh page and try signing in again
```

---

## Session & Authentication State

### User stays logged in after page refresh (expected behavior)

**Expected:** User should remain authenticated across page reloads

**Verification:**
```bash
# Open browser console and check:
localStorage.getItem('user')
# Should return user object

# Or check with curl:
curl -b cookies.txt http://localhost:8800/auth/status
# Should return: {"authenticated": true, "user": {...}}
```

### Session expires too quickly

**Problem:** User logged out after few minutes of inactivity

**Cause:** Session timeout configured too short

**Solution:**
```python
# In auth.py, adjust SESSION_PERMANENT:
app.config['SESSION_PERMANENT'] = True  # Don't expire with browser

# Or set custom timeout (24 hours):
from datetime import timedelta
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=1)
```

### Cannot access protected routes

**Error:** 401 Unauthorized when accessing `/api/protected`

**Cause:** @require_auth decorator preventing access without valid session

**Debug:**
```bash
# Check session status
curl http://localhost:8800/auth/status

# If not authenticated, sign in first via browser

# Then try API call:
curl -b cookies.txt http://localhost:8800/api/protected
```

---

## CORS Issues

### "CORS policy: Response to preflight request" error

**Error:** `Access to XMLHttpRequest blocked by CORS policy`

**Cause:** Frontend making requests from different origin than backend

**Solution (already implemented):**
```python
# In app.py, verify CORS is configured:
from flask_cors import CORS
CORS(app, support_credentials=True)

# Restart server
python app.py
```

### Credentials not sent with request

**Problem:** Cookie/session not being sent to backend

**Solution (in JavaScript):**
```javascript
fetch('/auth/status', {
  method: 'GET',
  credentials: 'include',  // Required!
  headers: {
    'Content-Type': 'application/json'
  }
})
```

---

## Frontend Integration Issues

### AuthClient methods undefined

**Error:** `Uncaught ReferenceError: AuthClient is not defined`

**Cause:** Script not loaded or loaded in wrong order

**Solution:**
```html
<!-- Correct order:
  1. Load Google SDK
  2. Load auth-client.js
  3. Use AuthClient in your code
-->

<script src="https://accounts.google.com/gsi/client" async defer></script>
<script src="js/auth-client.js" data-client-id="999940301372-lsv85hnhe6ucju10uhhg2u36k1j8is9f.apps.googleusercontent.com"></script>

<script>
  // Wait for auth-client.js to load
  window.addEventListener('load', () => {
    AuthClient.onLogin((user) => {
      console.log('User logged in:', user);
    });
  });
</script>
```

### localStorage.getItem('user') returns null

**Problem:** User data not persisting in browser

**Cause:** Auth response not properly saving to localStorage

**Debug:**
```javascript
// In browser console:
localStorage.setItem('user', JSON.stringify({name: 'Test', email: 'test@test.com'}));
localStorage.getItem('user');
// Should return the JSON string

// If still null, check auth-client.js has:
localStorage.setItem('user', JSON.stringify(data.user));
```

---

## Server & Backend Issues

### /auth/status returns 500 error

**Error:** `Internal Server Error on /auth/status`

**Debug:**
```bash
# Check Flask logs for error details
python app.py 2>&1 | grep -i error

# Common causes and fixes:
# 1. Session not initialized:
#    Solution: Ensure Flask-Session configured in auth.py
#
# 2. Missing user in session:
#    Solution: Sign in through Google first
#
# 3. Missing environment variables:
#    Solution: Verify .env has SESSION_SECRET set
```

### /auth/google/callback returns error

**Error:** Redirect from Google shows error page

**Cause:** State token mismatch or callback not properly handling OAuth response

**Debug:**
```python
# Add logging in auth.py callback:
@app.route('/auth/google/callback')
def google_callback():
    print(f"Received state: {request.args.get('state')}")
    print(f"Expected state: {session.get('oauth_state')}")
    # ... rest of code
```

**Solution:**
```bash
# Clear cookies and try again
# Browser DevTools → Application → Cookies → Delete all for localhost:8800
# Refresh page and try OAuth flow again
```

### Logout not working

**Problem:** Click logout but user still logged in

**Solution:**
```python
# Verify logout endpoint clears session:
@app.route('/auth/logout', methods=['POST', 'GET'])
def logout():
    session.clear()
    return redirect('/login.html')

# Then restart server and test:
curl -X POST http://localhost:8800/auth/logout
```

---

## Environment & Configuration

### Missing environment variables

**Error:** Weird behavior suggesting missing config

**Fix:**
```bash
# Create .env file with all required variables
cat > .env << 'EOF'
GOOGLE_CLIENT_SECRETS=/home/crimson/Desktop/Laptop/client_secret_999940301372-lsv85hnhe6ucju10uhhg2u36k1j8is9f.apps.googleusercontent.com.json
GOOGLE_REDIRECT_URI=http://localhost:8800/auth/google/callback
SESSION_SECRET=your-secret-key-change-in-production
PORT=8800
FLASK_ENV=development
FLASK_DEBUG=1
EOF

# Verify auth.py loads variables:
source venv/bin/activate
python -c "from auth import *; import os; print('GOOGLE_CLIENT_SECRETS:', os.getenv('GOOGLE_CLIENT_SECRETS'))"
```

### Python dependencies outdated

**Problem:** Unexpected import errors or version conflicts

**Solution:**
```bash
# Reinstall all dependencies
source venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt --force-reinstall

# Or create fresh environment:
deactivate
rm -rf venv
python3.15 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## Testing & Verification

### Complete end-to-end test

```bash
#!/bin/bash

echo "1. Checking dependencies..."
source venv/bin/activate
python -c "import flask, google.auth; print('✓ Dependencies OK')"

echo "2. Starting server..."
python app.py &
SERVER_PID=$!
sleep 2

echo "3. Testing health endpoint..."
curl -s http://localhost:8800/health | grep -q "ok" && echo "✓ Health OK"

echo "4. Testing auth status (should be unauthenticated)..."
curl -s http://localhost:8800/auth/status | grep -q "authenticated" && echo "✓ Status OK"

echo "5. Stopping server..."
kill $SERVER_PID

echo "✓ All tests passed!"
```

### Manual browser testing

1. **Start server:**
   ```bash
   source venv/bin/activate
   python app.py
   ```

2. **Open browser:**
   ```
   http://localhost:8800
   ```

3. **Test OAuth flow:**
   - Click "Sign In"
   - Verify Google consent screen appears
   - Grant permissions
   - Verify redirects back to home page
   - Check user name/email displayed

4. **Test logout:**
   - Click "Logout"
   - Verify session cleared
   - Verify page shows "Sign In" button again

---

## Getting Help

### Check logs
```bash
# View full server output
python app.py 2>&1 | tee log.txt

# Watch logs in real-time
tail -f log.txt
```

### Enable debug mode
```bash
# Edit .env:
FLASK_DEBUG=1
FLASK_ENV=development

# Then restart server
python app.py
```

### Test with curl
```bash
# Test each endpoint
curl -v http://localhost:8800/health
curl -v http://localhost:8800/auth/status
curl -v -X POST http://localhost:8800/auth/logout

# Include cookies
curl -v -b cookies.txt http://localhost:8800/auth/status
```

### Check browser console
```javascript
// F12 → Console tab
// Paste to debug:
fetch('/auth/status')
  .then(r => r.json())
  .then(d => console.log(d))
  .catch(e => console.error(e));
```

---

## Common Error Messages Reference

| Error | Cause | Fix |
|-------|-------|-----|
| `ModuleNotFoundError: flask` | Not in venv | `source venv/bin/activate` |
| `Port already in use` | Port 8800 taken | `PORT=9000 python app.py` |
| `redirect_uri_mismatch` | URL doesn't match Google | Update Google Console settings |
| `invalid_client` | Wrong Client ID | Check credentials file Client ID |
| `invalid_token` | Token expired/invalid | Clear cookies and re-authenticate |
| `CORS policy blocked` | Origin mismatch | CORS already configured, check browser URL |
| `Session expired` | Timed out | Sign in again |
| `AuthClient undefined` | Script not loaded | Check script tag order |
| `localStorage.getItem(null)` | Not authenticated | Sign in first |

---

## Files to Check

When debugging, systematically check these files:

1. **`.env`** - Environment variables
   ```bash
   cat .env
   ```

2. **`auth.py`** - Backend logic
   ```bash
   python -m py_compile auth.py  # syntax check
   grep -n "def " auth.py  # show all functions
   ```

3. **`app.py`** - Flask app initialization
   ```bash
   grep init_auth app.py  # verify auth integration
   ```

4. **`js/auth-client.js`** - Frontend logic
   ```bash
   grep -c "class AuthClient" js/auth-client.js  # should = 1
   ```

5. **Credentials file** - Google OAuth credentials
   ```bash
   file client_secret_*.json
   python -c "import json; json.load(open('client_secret_*.json'))"
   ```

6. **HTML files** - Check script tags
   ```bash
   grep "<script src" login.html signin.html
   ```

---

## Advanced: Add Detailed Logging

Add this to `auth.py` for detailed debugging:

```python
import logging

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add to functions:
logger.debug(f"Verifying token: {token[:20]}...")
logger.info(f"User authenticated: {user_info.get('email')}")
logger.error(f"Auth failed: {str(e)}")
```

Then run server and check console output for detailed logs.

---

## Need More Help?

Check these resources:
- Flask docs: https://flask.palletsprojects.com/
- Google Auth docs: https://developers.google.com/identity/protocols/oauth2
- JS Client docs: Check `GOOGLE_AUTH_SETUP.md` examples
- Local logs: `tail -f log.txt` while server running
