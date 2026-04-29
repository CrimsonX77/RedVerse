# RedVerse Google Auth Integration Guide

## Overview
This guide explains how to wire Google OAuth2 authentication through the RedVerse codebase.

## Architecture

```
Frontend (HTML/JS)
    ↓
    └→ js/auth-client.js (AuthClient)
         ↓
         └→ Google Sign-In SDK
              ↓
              └→ /auth/google/verify (Backend)
                   ↓
                   └→ auth.py (Authentication Module)
                       ↓
                       └→ Session Management + User Data
```

## Setup Steps

### 1. Environment Variables

Export the required environment variables:

```bash
# Google OAuth Client Secrets (path to JSON file)
export GOOGLE_CLIENT_SECRETS='/home/crimson/Desktop/Laptop/client_secret_999940301372-lsv85hnhe6ucju10uhhg2u36k1j8is9f.apps.googleusercontent.com.json'

# Google OAuth Redirect URI (must match Google Cloud Console)
export GOOGLE_REDIRECT_URI='http://localhost:8800/auth/google/callback'

# Session secret (for production, use a strong random string)
export SESSION_SECRET='your-secure-session-secret-here'

# Stripe API Key (optional, for checkout)
export STRIPE_SECRET_KEY='sk_test_YOUR_KEY'
```

Or create a `.env` file:

```bash
cd /home/crimson/Desktop/Laptop
cat > .env << 'EOF'
GOOGLE_CLIENT_SECRETS=/home/crimson/Desktop/Laptop/client_secret_999940301372-lsv85hnhe6ucju10uhhg2u36k1j8is9f.apps.googleusercontent.com.json
GOOGLE_REDIRECT_URI=http://localhost:8800/auth/google/callback
SESSION_SECRET=dev-session-secret-change-in-production
STRIPE_SECRET_KEY=sk_test_REPLACE_WITH_YOUR_KEY
PORT=8800
EOF
```

Load from `.env`:

```bash
set -a && source .env && set +a
```

### 2. Install Dependencies

```bash
cd /home/crimson/Desktop/Laptop
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Start the Server

```bash
python app.py
```

Or with a specific port:

```bash
python app.py 8800
```

The server will start on `http://127.0.0.1:8800`

## Frontend Integration

### Basic Setup in HTML

Add Google Sign-In SDK and auth-client.js:

```html
<head>
  <!-- Google Sign-In SDK -->
  <script src="https://accounts.google.com/gsi/client" async defer></script>
  
  <!-- RedVerse Auth Client -->
  <script src="js/auth-client.js" data-client-id="999940301372-lsv85hnhe6ucju10uhhg2u36k1j8is9f.apps.googleusercontent.com"></script>
</head>

<body>
  <!-- Google Sign-In Button -->
  <div id="g_id_onload"
       data-client_id="999940301372-lsv85hnhe6ucju10uhhg2u36k1j8is9f.apps.googleusercontent.com"
       data-callback="handleCredentialResponse">
  </div>
  <div class="g_id_signin" data-type="standard"></div>
  
  <script>
    // Handle login
    AuthClient.onLogin((user) => {
      console.log('Logged in:', user);
      window.location.href = '/redverse-shop.html';
    });
    
    // Handle errors
    AuthClient.onError((err) => {
      console.error('Auth error:', err.message);
      // Show error message to user
    });
    
    // Handle logout
    AuthClient.onLogout(() => {
      console.log('Logged out');
      window.location.href = '/login.html';
    });
  </script>
</body>
```

### Advanced: Manual Login/Logout

```html
<button onclick="AuthClient.logout()">Logout</button>

<script>
  // Navigate after login
  AuthClient.onLogin((user) => {
    console.log('User:', user.email);
    // Update UI, fetch user data, etc.
  });
  
  // Check if already logged in
  if (AuthClient.isAuthenticated()) {
    const user = AuthClient.getCurrentUser();
    console.log('Already logged in as:', user.email);
  }
</script>
```

## Backend API Endpoints

### `GET /auth/status`
Check current authentication status.

**Response:**
```json
{
  "authenticated": true,
  "user": {
    "id": "1234567890",
    "email": "user@example.com",
    "name": "User Name",
    "picture": "https://..."
  }
}
```

### `POST /auth/google/verify`
Verify a Google ID token (called by frontend).

**Request:**
```json
{
  "token": "eyJhbGciOiJSUzI1NiIs..."
}
```

**Response:**
```json
{
  "ok": true,
  "user": {
    "id": "1234567890",
    "email": "user@example.com",
    "name": "User Name",
    "picture": "https://..."
  }
}
```

### `GET /auth/google/login`
Initiate OAuth2 server-side flow (if using server-side login).

**Redirects to:** Google's OAuth consent screen

### `GET /auth/logout`
Clear session and logout user.

**Redirects to:** `/login.html`

## Protecting Routes

Use the `@require_auth` decorator to protect API endpoints:

```python
from auth import require_auth

@app.route('/api/user/profile', methods=['GET'])
@require_auth
def get_user_profile():
    from auth import get_current_user
    user = get_current_user()
    return jsonify({'user': user})
```

## File Structure

```
/home/crimson/Desktop/Laptop/
├── app.py                    # Main Flask app
├── auth.py                   # Authentication module
├── requirements.txt          # Dependencies
├── login.html               # Login page
├── signin.html              # Sign-in page
├── redverse-shop.html       # Shop (requires auth)
├── js/
│   └── auth-client.js       # Frontend auth client
└── client_secret_*.json     # Google OAuth credentials
```

## Common Issues

### 1. "Redirect URI mismatch"
Check that `GOOGLE_REDIRECT_URI` matches your registered URI in Google Cloud Console.

### 2. "Invalid token issuer"
Ensure your Google Client ID is correct in the HTML and environment.

### 3. Session not persisting across requests
Ensure `SESSION_SECRET` is set and persistent sessions are enabled.

### 4. CORS errors
The backend should automatically enable CORS. If issues persist, check `app.py`.

## Testing

### Test Authentication Flow

```bash
# Start the server
python app.py

# In another terminal, test the health endpoint
curl http://127.0.0.1:8800/health

# Check auth status (should be unauthenticated)
curl http://127.0.0.1:8800/auth/status

# Visit in browser
open http://127.0.0.1:8800/login.html
```

### Test Protected Route

```python
# In a Python script
import requests

session = requests.Session()

# Simulate authenticated request
# (Requires valid session cookie from browser login)
response = session.get('http://127.0.0.1:8800/auth/status')
print(response.json())
```

## Next Steps

1. **User Database:** Create a database schema to store user data from Google OAuth.
2. **User Profile:** Extend `auth.py` to fetch/store user profile info.
3. **Email Verification:** Add email verification flow if needed.
4. **Permission Levels:** Implement role-based access control (admin, user, etc.).
5. **API Rate Limiting:** Add rate limiting to auth endpoints.

## References

- [Google OAuth 2.0 Documentation](https://developers.google.com/identity/protocols/oauth2)
- [Flask-Session Documentation](https://flask-session.readthedocs.io/)
- [Google Sign-In for Web](https://developers.google.com/identity/gsi/web)
