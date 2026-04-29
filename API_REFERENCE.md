# RedVerse Authentication API Reference

Complete API documentation for Google OAuth2 endpoints and usage patterns.

---

## Quick Reference

| Method | Endpoint | Auth Required | Purpose |
|--------|----------|----------------|---------|
| `POST` | `/auth/google/verify` | No | Verify Google ID token |
| `GET` | `/auth/status` | No | Check authentication status |
| `POST` | `/auth/logout` | No | Logout current user |
| `GET` | `/auth/google/login` | No | Initiate OAuth flow |
| `GET` | `/auth/google/callback` | No | OAuth callback handler |
| `GET` | `/health` | No | Health check |

---

## Endpoints

### POST /auth/google/verify

Verify Google ID token and establish session.

**Used by:** Frontend after Google Sign-In

**Request:**
```json
{
  "token": "eyJhbGciOiJSUzI1NiIsImtpZCI6IjE..."
}
```

**Response (Success - 200):**
```json
{
  "ok": true,
  "user": {
    "sub": "109123456789",
    "name": "John Doe",
    "email": "john@example.com",
    "email_verified": true,
    "picture": "https://lh3.googleusercontent.com/...",
    "locale": "en"
  }
}
```

**Response (Error - 401):**
```json
{
  "ok": false,
  "error": "Invalid token"
}
```

**Example cURL:**
```bash
curl -X POST http://localhost:8800/auth/google/verify \
  -H "Content-Type: application/json" \
  -d '{"token":"eyJhbGciOiJSUzI1NiIsImtpZCI6IjE..."}'
```

**Example JavaScript:**
```javascript
fetch('/auth/google/verify', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ token: response.credential })
})
.then(res => res.json())
.then(data => {
  if (data.ok) {
    console.log('Authenticated as:', data.user.email);
  }
});
```

---

### GET /auth/status

Check current authentication status and retrieve user info.

**Used by:** Frontend on page load to verify session

**Request:**
```bash
GET /auth/status
```

**Response (Authenticated - 200):**
```json
{
  "authenticated": true,
  "user": {
    "sub": "109123456789",
    "name": "John Doe",
    "email": "john@example.com",
    "picture": "https://lh3.googleusercontent.com/..."
  }
}
```

**Response (Not Authenticated - 200):**
```json
{
  "authenticated": false,
  "user": null
}
```

**Example cURL:**
```bash
curl http://localhost:8800/auth/status
```

**Example JavaScript:**
```javascript
fetch('/auth/status')
  .then(res => res.json())
  .then(data => {
    if (data.authenticated) {
      console.log('User:', data.user.name);
      // Show protected content
    } else {
      console.log('Not authenticated');
      // Redirect to login
    }
  });
```

---

### POST /auth/logout

Clear session and logout user.

**Used by:** Frontend logout button

**Request:**
```bash
POST /auth/logout
```

**Response (200):**
```json
{
  "message": "Logged out successfully"
}
```

**Redirects to:** `/login.html`

**Example cURL:**
```bash
curl -X POST http://localhost:8800/auth/logout
```

**Example JavaScript:**
```javascript
document.getElementById('logoutBtn').onclick = () => {
  fetch('/auth/logout', { method: 'POST' })
    .then(() => {
      localStorage.removeItem('user');
      window.location.href = '/login.html';
    });
};
```

---

### GET /auth/google/login

Initiate OAuth2 flow (server-side redirect flow).

**Used by:** Traditional server-rendered apps or fallback

**Request:**
```bash
GET /auth/google/login
```

**Response:**
- Redirects to Google consent screen

**Example:**
```html
<a href="/auth/google/login">Sign in with Google</a>
```

---

### GET /auth/google/callback

OAuth2 callback handler (called by Google after user consent).

**Used by:** Google OAuth2 flow automatically

**Query Parameters:**
- `code` - Authorization code from Google
- `state` - CSRF protection token

**Response:**
- Redirects to `/` on success
- Redirects to `/login.html` on failure

**Note:** Handles automatically, no manual calls needed

---

### GET /health

Health check endpoint.

**Used by:** Monitoring, load balancers

**Request:**
```bash
GET /health
```

**Response (200):**
```json
{
  "status": "ok",
  "service": "RedVerse Auth",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

**Example cURL:**
```bash
curl http://localhost:8800/health
```

---

## Protected Endpoints Pattern

Use the `@require_auth` decorator to protect routes:

```python
from flask import jsonify, request
from auth import require_auth, get_current_user

@app.route('/api/user-profile')
@require_auth
def get_profile():
    """Get authenticated user's profile"""
    user = get_current_user()
    return jsonify({
        'id': user['sub'],
        'name': user['name'],
        'email': user['email']
    })

@app.route('/api/checkout', methods=['POST'])
@require_auth
def checkout():
    """Protected checkout endpoint"""
    user = get_current_user()
    data = request.get_json()
    
    # Your checkout logic here
    
    return jsonify({
        'order_id': 'ORD-123',
        'user_email': user['email'],
        'total': data['total']
    })
```

---

## Frontend Implementation Patterns

### Pattern 1: Basic Sign-In

```html
<div id="g_id_onload"
     data-client_id="999940301372-lsv85hnhe6ucju10uhhg2u36k1j8is9f.apps.googleusercontent.com"
     data-callback="handleCredentialResponse">
</div>
<div class="g_id_signin" data-type="standard"></div>

<script src="https://accounts.google.com/gsi/client" async defer></script>

<script>
function handleCredentialResponse(response) {
  fetch('/auth/google/verify', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token: response.credential })
  })
  .then(res => res.json())
  .then(data => {
    if (data.ok) {
      window.location.href = '/';
    }
  });
}
</script>
```

### Pattern 2: Check Auth on Page Load

```javascript
window.addEventListener('load', () => {
  fetch('/auth/status')
    .then(res => res.json())
    .then(data => {
      if (!data.authenticated) {
        window.location.href = '/login.html';
      } else {
        initializeApp(data.user);
      }
    });
});
```

### Pattern 3: API Call with Auth

```javascript
async function fetchUserData() {
  const response = await fetch('/api/user-profile');
  
  if (response.status === 401) {
    // Not authenticated
    window.location.href = '/login.html';
    return;
  }
  
  const data = await response.json();
  console.log('User data:', data);
}
```

### Pattern 4: Logout

```javascript
document.getElementById('logoutBtn').onclick = async () => {
  await fetch('/auth/logout', { method: 'POST' });
  localStorage.clear();
  window.location.href = '/login.html';
};
```

---

## Error Handling

### Common Error Responses

**401 Unauthorized:**
```json
{
  "error": "Unauthorized",
  "message": "Authentication required"
}
```

**403 Forbidden:**
```json
{
  "error": "Forbidden",
  "message": "You don't have permission to access this resource"
}
```

**400 Bad Request:**
```json
{
  "error": "Bad Request",
  "message": "Invalid token format"
}
```

**500 Internal Server Error:**
```json
{
  "error": "Server Error",
  "message": "An error occurred during authentication"
}
```

### Error Handling in Frontend

```javascript
async function safeApiCall(url) {
  try {
    const res = await fetch(url);
    
    if (res.status === 401) {
      console.log('Session expired');
      window.location.href = '/login.html';
      return null;
    }
    
    if (!res.ok) {
      const error = await res.json();
      console.error('API Error:', error.message);
      return null;
    }
    
    return await res.json();
  } catch (err) {
    console.error('Network error:', err);
    return null;
  }
}
```

---

## Request/Response Examples

### Complete OAuth Flow Example

**1. Frontend initiates Google Sign-In:**
```javascript
// User clicks Google Sign-In button
// Google SDK calls handleCredentialResponse() with JWT
```

**2. Frontend verifies with backend:**
```bash
POST /auth/google/verify
Content-Type: application/json

{
  "token": "eyJhbGciOiJSUzI1NiIsImtpZCI6IjE..."
}
```

**3. Backend verifies and responds:**
```bash
HTTP/1.1 200 OK
Content-Type: application/json
Set-Cookie: session=abc123...; Path=/; HttpOnly

{
  "ok": true,
  "user": {
    "sub": "109123456789",
    "name": "John Doe",
    "email": "john@example.com",
    "picture": "https://lh3.googleusercontent.com/...",
    "email_verified": true
  }
}
```

**4. Frontend can now make authenticated requests:**
```bash
GET /api/user-profile

HTTP/1.1 200 OK
Content-Type: application/json

{
  "id": "109123456789",
  "name": "John Doe",
  "email": "john@example.com"
}
```

---

## Testing Endpoints

### Quick Test Script

```bash
#!/bin/bash

BASE_URL="http://localhost:8800"

echo "1. Health check"
curl -s $BASE_URL/health | jq '.'

echo -e "\n2. Check auth status (should be unauthenticated)"
curl -s $BASE_URL/auth/status | jq '.'

echo -e "\n3. Test logout"
curl -s -X POST $BASE_URL/auth/logout | jq '.'

echo -e "\n✓ All endpoints accessible"
```

### Using Postman

1. Create collection: "RedVerse Auth"
2. Add requests:
   - GET `/auth/status`
   - POST `/auth/logout`
   - GET `/health`
3. Set base URL: `{{base_url}}`
4. Create environment with: `base_url = http://localhost:8800`
5. Run collection

---

## API Response Format

All responses follow this format:

```json
{
  "ok": true|false,
  "data": {},
  "error": null|"error message",
  "timestamp": "ISO-8601 timestamp"
}
```

---

## Rate Limiting

Currently no rate limiting implemented. In production, add:

```python
from flask_limiter import Limiter

limiter = Limiter(
    app,
    key_func=lambda: get_current_user()['sub'] if get_current_user() else request.remote_addr,
    default_limits=["200 per day", "50 per hour"]
)

@app.route('/auth/google/verify', methods=['POST'])
@limiter.limit("5 per minute")
def verify_google_token():
    # Rate limited to 5 requests per minute per user
    ...
```

---

## Session Management

### Session Configuration

```python
# In auth.py
app.config['SESSION_TIMEOUT'] = 24 * 60 * 60  # 24 hours
app.config['SESSION_REFRESH_EACH_REQUEST'] = False
app.config['SESSION_COOKIE_SECURE'] = False  # True in production
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
```

### Session Duration

- **Current:** 24 hours or browser close
- **Customize by:** Editing `SESSION_TIMEOUT` config
- **Check status:** Call `/auth/status` endpoint

---

## Production Considerations

### Before Deploying to Production

1. **Security:**
   - Set `SESSION_COOKIE_SECURE = True` (HTTPS only)
   - Change `SESSION_SECRET` to random value
   - Enable CSRF protection
   - Add rate limiting

2. **Performance:**
   - Enable caching headers
   - Use Redis for session storage (instead of server memory)
   - Add CDN for static files

3. **Monitoring:**
   - Log all auth attempts
   - Monitor failed authentications
   - Set up alerts

4. **Example Production Config:**
   ```python
   app.config['SESSION_COOKIE_SECURE'] = True
   app.config['SESSION_COOKIE_SAMESITE'] = 'Strict'
   app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
   app.config['SESSION_REFRESH_EACH_REQUEST'] = True
   ```

---

## Debugging

### Enable Detailed Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Then check console output
```

### Test Individual Endpoints

```bash
# Test without authentication
curl -v http://localhost:8800/auth/status

# Test with cookies (after login)
curl -v -b cookies.txt http://localhost:8800/auth/status

# Capture cookies
curl -c cookies.txt http://localhost:8800/auth/status
```

### Check Headers

```bash
curl -i http://localhost:8800/auth/status
# Look for Set-Cookie header with session
```

---

## Glossary

- **OAuth2** - Authorization protocol (not authentication)
- **OIDC** - OpenID Connect (OpenID on top of OAuth2)
- **ID Token** - JWT containing user identity info from Google
- **Session** - Server-side user state stored after login
- **CSRF** - Cross-Site Request Forgery (prevented with state token)
- **JWT** - JSON Web Token (Google's ID token format)
- **JWKS** - JSON Web Key Set (Google's public keys for verification)
