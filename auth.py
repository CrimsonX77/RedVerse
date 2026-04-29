"""
Google OAuth2 Authentication Module for RedVerse

Setup:
  1. Install: pip install google-auth-oauthlib google-auth-httplib2 flask-session
  2. Export credentials: export GOOGLE_CLIENT_SECRETS='path/to/client_secret_*.json'
  3. Configure: Update GOOGLE_REDIRECT_URI and SESSION_SECRET below

Provides:
  - OAuth2 login endpoint (/auth/google/callback)
  - User session management
  - Token validation
"""

import json
import os
from functools import wraps
from pathlib import Path

from flask import Flask, request, jsonify, session, redirect, url_for
from flask_session import Session
from google.auth.transport.requests import Request
from google.oauth2.id_token import verify_oauth2_token
from google_auth_oauthlib.flow import Flow
import google.auth.exceptions

# ── Configuration ──────────────────────────────────────────────────

# Load Google OAuth credentials
GOOGLE_CLIENT_SECRETS = os.environ.get(
    'GOOGLE_CLIENT_SECRETS',
    '/home/crimson/Desktop/Laptop/client_secret_999940301372-lsv85hnhe6ucju10uhhg2u36k1j8is9f.apps.googleusercontent.com.json'
)

# Redirect URI for OAuth callback (must match Google Cloud Console config)
GOOGLE_REDIRECT_URI = os.environ.get(
    'GOOGLE_REDIRECT_URI',
    'http://localhost:8800/auth/google/callback'
)

# Session configuration
SESSION_SECRET = os.environ.get('SESSION_SECRET', 'dev-secret-key-change-in-production')

# ── Session Setup ──────────────────────────────────────────────────

def init_auth(app: Flask):
    """Initialize authentication for a Flask app."""
    app.config['SECRET_KEY'] = SESSION_SECRET
    app.config['SESSION_TYPE'] = 'filesystem'
    Session(app)
    
    # Register OAuth routes
    @app.route('/auth/google/login', methods=['GET'])
    def google_login():
        """Initiate Google OAuth2 login flow."""
        try:
            flow = Flow.from_client_secrets_file(
                GOOGLE_CLIENT_SECRETS,
                scopes=[
                    'openid',
                    'https://www.googleapis.com/auth/userinfo.email',
                    'https://www.googleapis.com/auth/userinfo.profile',
                ],
                redirect_uri=GOOGLE_REDIRECT_URI
            )
            authorization_url, state = flow.authorization_url(
                access_type='offline',
                include_granted_scopes='true'
            )
            session['oauth_state'] = state
            return redirect(authorization_url)
        except Exception as e:
            return jsonify({'error': f'Login initiation failed: {str(e)}'}), 500

    @app.route('/auth/google/callback', methods=['GET'])
    def google_callback():
        """Handle Google OAuth2 callback."""
        try:
            # Verify state token
            state = request.args.get('state')
            if not state or state != session.get('oauth_state'):
                return jsonify({'error': 'Invalid state parameter'}), 400
            
            # Exchange authorization code for tokens
            flow = Flow.from_client_secrets_file(
                GOOGLE_CLIENT_SECRETS,
                scopes=[
                    'openid',
                    'https://www.googleapis.com/auth/userinfo.email',
                    'https://www.googleapis.com/auth/userinfo.profile',
                ],
                redirect_uri=GOOGLE_REDIRECT_URI
            )
            
            flow.fetch_token(authorization_response=request.url)
            credentials = flow.credentials
            
            # Verify ID token and get user info
            id_token = credentials.id_token
            user_info = verify_oauth2_token(id_token, Request())
            
            # Store user session
            session['user'] = {
                'id': user_info.get('sub'),
                'email': user_info.get('email'),
                'name': user_info.get('name'),
                'picture': user_info.get('picture'),
                'token': credentials.token,
            }
            session['authenticated'] = True
            
            # Redirect to success page (or redirect_uri from query param)
            redirect_to = request.args.get('redirect_uri', '/redverse-shop.html')
            return redirect(redirect_to)
            
        except Exception as e:
            return jsonify({'error': f'OAuth callback failed: {str(e)}'}), 500

    @app.route('/auth/google/verify', methods=['POST'])
    def verify_google_token():
        """Verify a Google ID token (for frontend-initiated auth)."""
        try:
            data = request.get_json()
            token = data.get('token')
            
            if not token:
                return jsonify({'error': 'No token provided'}), 400
            
            # Verify token using Google's public key
            user_info = verify_oauth2_token(token, Request())
            
            # Check token issuer
            if user_info['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
                raise ValueError('Invalid token issuer')
            
            # Store user session
            session['user'] = {
                'id': user_info.get('sub'),
                'email': user_info.get('email'),
                'name': user_info.get('name'),
                'picture': user_info.get('picture'),
            }
            session['authenticated'] = True
            
            return jsonify({
                'ok': True,
                'user': session['user']
            })
            
        except google.auth.exceptions.GoogleAuthError as e:
            return jsonify({'error': f'Token verification failed: {str(e)}'}), 401
        except Exception as e:
            return jsonify({'error': f'Verification error: {str(e)}'}), 500

    @app.route('/auth/logout', methods=['POST', 'GET'])
    def logout():
        """Clear user session."""
        session.clear()
        return redirect('/login.html') if request.method == 'GET' else jsonify({'ok': True})

    @app.route('/auth/status', methods=['GET'])
    def auth_status():
        """Get current authentication status."""
        user = session.get('user')
        return jsonify({
            'authenticated': session.get('authenticated', False),
            'user': user
        })

    return app


# ── Decorators ─────────────────────────────────────────────────────

def require_auth(f):
    """Decorator to require authentication on a route."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('authenticated'):
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated_function


def get_current_user():
    """Get the currently authenticated user from the session."""
    return session.get('user') if session.get('authenticated') else None
