# Google Auth Integration Examples

This document provides step-by-step examples for integrating Google OAuth2 authentication into your HTML pages.

## Quick Start Pattern

Every page that needs authentication should follow this pattern:

```html
<!DOCTYPE html>
<html>
<head>
  <title>Your Page</title>
</head>
<body>
  <!-- Your page content here -->
  
  <!-- Google Sign-In SDK (required) -->
  <script src="https://accounts.google.com/gsi/client" async defer></script>

  <!-- Auth Client (required) -->
  <script src="js/auth-client.js" data-client-id="999940301372-lsv85hnhe6ucju10uhhg2u36k1j8is9f.apps.googleusercontent.com"></script>

  <!-- Your authentication logic -->
  <script>
    // Listen for login events
    AuthClient.onLogin((user) => {
      console.log("User logged in:", user);
      // Redirect or update UI here
    });

    // Check if already logged in
    fetch('/auth/status')
      .then(r => r.json())
      .then(data => {
        if (!data.authenticated) {
          // Redirect to login
          window.location.href = '/login.html';
        }
      });
  </script>
</body>
</html>
```

---

## Pattern 1: Login/Sign-In Page

Use this pattern for your sign-in page (e.g., `signin.html` or `login.html`):

```html
<!DOCTYPE html>
<html>
<head>
  <title>Sign In to RedVerse</title>
  <style>
    .login-container {
      max-width: 400px;
      margin: 100px auto;
      text-align: center;
    }
    .google-signin-button {
      padding: 12px 24px;
      background: white;
      border: 1px solid #ddd;
      border-radius: 4px;
      cursor: pointer;
      font-size: 16px;
    }
  </style>
</head>
<body>
  <div class="login-container">
    <h1>Sign In to RedVerse</h1>
    
    <!-- Google Sign-In Button -->
    <div id="g_id_onload"
         data-client_id="999940301372-lsv85hnhe6ucju10uhhg2u36k1j8is9f.apps.googleusercontent.com"
         data-callback="handleCredentialResponse">
    </div>
    <div class="g_id_signin" data-type="standard"></div>

    <div id="authMessage"></div>
  </div>

  <script src="https://accounts.google.com/gsi/client" async defer></script>
  <script src="js/auth-client.js" data-client-id="999940301372-lsv85hnhe6ucju10uhhg2u36k1j8is9f.apps.googleusercontent.com"></script>

  <script>
    // Handle Google OAuth response
    function handleCredentialResponse(response) {
      console.log("Google response:", response);
      
      // Send to backend for verification
      fetch('/auth/google/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: response.credential })
      })
      .then(res => res.json())
      .then(data => {
        if (data.ok) {
          console.log("✓ Authenticated as:", data.user.email);
          // Redirect to home or dashboard
          window.location.href = '/';
        } else {
          document.getElementById('authMessage').textContent = 'Authentication failed';
        }
      })
      .catch(err => {
        console.error('✗ Auth error:', err);
        document.getElementById('authMessage').textContent = 'Error: ' + err.message;
      });
    }

    // If already logged in, redirect to home
    fetch('/auth/status')
      .then(r => r.json())
      .then(data => {
        if (data.authenticated) {
          window.location.href = '/';
        }
      });
  </script>
</body>
</html>
```

---

## Pattern 2: Protected Shop/Checkout Page

Use this pattern for pages requiring authentication (e.g., `redverse-shop.html`):

```html
<!DOCTYPE html>
<html>
<head>
  <title>RedVerse Shop</title>
</head>
<body>
  <header>
    <h1>RedVerse Shop</h1>
    <button id="logoutBtn" onclick="logout()">Logout</button>
    <span id="userDisplay"></span>
  </header>

  <main id="shopContent" style="display: none;">
    <!-- Your shop products here -->
  </main>

  <div id="authCheck" style="text-align: center; padding: 60px 20px;">
    <p>Verifying authentication...</p>
  </div>

  <script src="https://accounts.google.com/gsi/client" async defer></script>
  <script src="js/auth-client.js" data-client-id="999940301372-lsv85hnhe6ucju10uhhg2u36k1j8is9f.apps.googleusercontent.com"></script>

  <script>
    // Require authentication
    fetch('/auth/status')
      .then(res => res.json())
      .then(data => {
        if (data.authenticated && data.user) {
          // Show shop content
          document.getElementById('authCheck').style.display = 'none';
          document.getElementById('shopContent').style.display = 'block';
          document.getElementById('userDisplay').textContent = 'Welcome, ' + data.user.name;
          
          // Initialize shop functionality
          initializeShop();
        } else {
          // Redirect to login
          document.getElementById('authCheck').innerHTML = 
            '<p>Please <a href="/login.html">sign in</a> to view the shop.</p>';
        }
      })
      .catch(err => {
        document.getElementById('authCheck').innerHTML = 
          '<p>Error checking authentication. Please <a href="/login.html">try again</a>.</p>';
      });

    function logout() {
      fetch('/auth/logout', { method: 'GET' })
        .then(() => {
          window.location.href = '/login.html';
        });
    }

    function initializeShop() {
      console.log("Shop initialized");
      // Add your shop logic here
    }
  </script>
</body>
</html>
```

---

## Pattern 3: API with Route Protection (Backend)

Protect your Flask routes using the `@require_auth` decorator:

```python
from flask import jsonify
from auth import require_auth

# Protect a route - requires authentication
@app.route('/api/user-profile')
@require_auth
def get_user_profile():
    current_user = get_current_user()
    return jsonify({
        'id': current_user.get('sub'),
        'name': current_user.get('name'),
        'email': current_user.get('email'),
        'profile_picture': current_user.get('picture')
    })

# Protect POST endpoint - creates protected resource
@app.route('/api/cart', methods=['POST'])
@require_auth
def create_cart():
    current_user = get_current_user()
    cart_data = request.get_json()
    
    # Your logic here
    return jsonify({
        'cart_id': 'cart_123',
        'user_id': current_user['sub'],
        'items': cart_data.get('items', [])
    })

# Optional: Combine with custom logic
@app.route('/api/checkout')
@require_auth
def checkout():
    user = get_current_user()
    
    # Verify user has permission
    if not user.get('email'):
        return jsonify({'error': 'Invalid user'}), 401
    
    # Your checkout logic
    return jsonify({'success': True})
```

---

## Pattern 4: User Feedback & Error Handling

Add user feedback for auth state changes:

```html
<script src="https://accounts.google.com/gsi/client" async defer></script>
<script src="js/auth-client.js" data-client-id="999940301372-lsv85hnhe6ucju10uhhg2u36k1j8is9f.apps.googleusercontent.com"></script>

<div id="notification" style="display: none; padding: 12px; margin: 12px 0; border-radius: 4px;"></div>

<script>
  function showNotification(message, type = 'info') {
    const notif = document.getElementById('notification');
    notif.textContent = message;
    notif.style.display = 'block';
    
    if (type === 'success') {
      notif.style.background = '#4caf50';
      notif.style.color = 'white';
    } else if (type === 'error') {
      notif.style.background = '#f44336';
      notif.style.color = 'white';
    } else {
      notif.style.background = '#2196f3';
      notif.style.color = 'white';
    }
    
    setTimeout(() => {
      notif.style.display = 'none';
    }, 3000);
  }

  AuthClient.onLogin((user) => {
    showNotification(`Welcome back, ${user.name}!`, 'success');
  });

  AuthClient.onLogout(() => {
    showNotification('You have been logged out', 'info');
  });

  AuthClient.onError((error) => {
    showNotification(`Auth error: ${error.message}`, 'error');
  });
</script>
```

---

## Pattern 5: Programmatic Login/Logout

Trigger login/logout from JavaScript:

```javascript
// Logout programmatically
document.getElementById('logoutButton').addEventListener('click', () => {
  fetch('/auth/logout', { method: 'POST' })
    .then(() => {
      AuthClient.emit('logout');
      window.location.href = '/login.html';
    });
});

// Check auth status periodically
setInterval(() => {
  fetch('/auth/status')
    .then(r => r.json())
    .then(data => {
      if (!data.authenticated) {
        // Session expired, redirect to login
        window.location.href = '/login.html';
      }
    });
}, 5 * 60 * 1000); // Every 5 minutes
```

---

## Backend Setup Checklist

- [ ] Created `auth.py` in project root
- [ ] Created `js/auth-client.js` in project root
- [ ] Created `.env` file with:
  - `GOOGLE_CLIENT_SECRETS=/path/to/client_secret_*.json`
  - `GOOGLE_REDIRECT_URI=http://localhost:8800/auth/google/callback`
  - `SESSION_SECRET=your-secret-key`
- [ ] Downloaded Google credentials JSON
- [ ] Run `pip install -r requirements.txt`
- [ ] Updated `app.py` with `init_auth(app)` call
- [ ] Test endpoints:
  - GET `/auth/status` - Check auth status
  - POST `/auth/logout` - Logout user
  - POST `/auth/google/verify` - Verify token (frontend calls)

---

## Common Issues & Solutions

### Issue: "Cannot verify token"
**Solution:** Ensure `GOOGLE_CLIENT_SECRETS` env var points to downloaded credentials file

### Issue: "Redirect URI mismatch"
**Solution:** Update `GOOGLE_REDIRECT_URI` in `.env` to match Google Console settings

### Issue: localStorage not persisting
**Solution:** Check browser privacy settings; use session cookies instead (already done in auth.py)

### Issue: "CORS error from /auth/google/verify"
**Solution:** Ensure `flask-cors` is installed and `CORS(app)` called in app.py

### Issue: User logged out after page refresh
**Solution:** Backend session still valid; call `fetch('/auth/status')` to verify

---

## Testing the Integration

```bash
# 1. Start the server
python app.py

# 2. Open browser to http://localhost:8800

# 3. Test login via Google Sign-In button

# 4. Verify authentication status
curl http://localhost:8800/auth/status

# 5. Test logout
curl -X POST http://localhost:8800/auth/logout

# 6. Verify logout
curl http://localhost:8800/auth/status
```

---

## Environment Variable Reference

| Variable | Example | Purpose |
|----------|---------|---------|
| `GOOGLE_CLIENT_SECRETS` | `/path/to/client_secret_*.json` | Path to downloaded Google credentials |
| `GOOGLE_REDIRECT_URI` | `http://localhost:8800/auth/google/callback` | OAuth redirect endpoint |
| `SESSION_SECRET` | `random-secret-key` | Session encryption key |
| `PORT` | `8800` | Port to run Flask server |

---

## Next Steps After Integration

1. **Create User Database** - Persist authenticated users in database
2. **Add User Profiles** - Store additional user data (preferences, settings)
3. **Implement Email Verification** - Verify user email before full access
4. **Add Role-Based Access Control** - Different permission levels for different users
5. **Set Up Monitoring** - Track auth success/failure rates

See `GOOGLE_AUTH_SETUP.md` for detailed next steps.
