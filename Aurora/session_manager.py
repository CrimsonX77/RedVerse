"""
Session Manager - JWT Token Management for RedVerse Authentication
Handles creation, validation, and expiry of secure JWT tokens for auth flow
"""

import os
import jwt
import json
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

# Configuration - should come from .env in production
JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'redverse-dev-secret-key-change-in-production')
JWT_ALGORITHM = 'HS256'
JWT_EXPIRY_HOURS = int(os.getenv('JWT_EXPIRY_HOURS', 24))


class SessionManager:
    """Manages JWT session tokens for user authentication"""

    @staticmethod
    def create_session_token(
        member_id: str,
        thread_id: str,
        email: str,
        display_name: str,
        access_tier: int,
        tier_name: str,
        google_sub: str,
        is_admin: bool = False
    ) -> str:
        """
        Create a JWT session token for authenticated user

        Args:
            member_id: Unique member database ID
            thread_id: User's memory thread UUID
            email: Google email address
            display_name: User's display name
            access_tier: Tier level 1-7
            tier_name: Human-readable tier name
            google_sub: Google subject identifier
            is_admin: Whether user is admin

        Returns:
            Encoded JWT token string
        """
        now = datetime.utcnow()
        exp = now + timedelta(hours=JWT_EXPIRY_HOURS)

        payload = {
            'member_id': member_id,
            'thread_id': thread_id,
            'email': email,
            'display_name': display_name,
            'access_tier': access_tier,
            'tier_name': tier_name,
            'google_sub': google_sub,
            'is_admin': is_admin,
            'iat': int(now.timestamp()),
            'exp': int(exp.timestamp())
        }

        token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
        return token

    @staticmethod
    def validate_session_token(token: str) -> Tuple[bool, Optional[Dict]]:
        """
        Validate and decode a JWT session token

        Args:
            token: JWT token string (with or without 'Bearer ' prefix)

        Returns:
            Tuple of (is_valid: bool, payload: dict or None)
        """
        try:
            # Remove 'Bearer ' prefix if present
            if token.startswith('Bearer '):
                token = token[7:]

            payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
            return True, payload

        except jwt.InvalidTokenError:
            return False, None
        except Exception as e:
            print(f"[SessionManager] Token validation error: {e}")
            return False, None

    @staticmethod
    def refresh_session_token(token: str, db_member: Optional[Dict] = None) -> Tuple[bool, Optional[str]]:
        """
        Refresh an expiring JWT token with updated data from DB

        Args:
            token: Current JWT token
            db_member: Optional updated member data from database

        Returns:
            Tuple of (success: bool, new_token: str or None)
        """
        is_valid, payload = SessionManager.validate_session_token(token)

        if not is_valid:
            return False, None

        # If DB member provided, use updated data; otherwise use existing payload
        if db_member:
            new_token = SessionManager.create_session_token(
                member_id=db_member.get('id', payload['member_id']),
                thread_id=db_member.get('thread_id', payload['thread_id']),
                email=db_member.get('email', payload['email']),
                display_name=db_member.get('display_name', payload['display_name']),
                access_tier=db_member.get('access_tier', payload['access_tier']),
                tier_name=db_member.get('tier_name', payload['tier_name']),
                google_sub=db_member.get('google_sub', payload['google_sub']),
                is_admin=db_member.get('is_admin', payload.get('is_admin', False))
            )
        else:
            new_token = SessionManager.create_session_token(
                member_id=payload['member_id'],
                thread_id=payload['thread_id'],
                email=payload['email'],
                display_name=payload['display_name'],
                access_tier=payload['access_tier'],
                tier_name=payload['tier_name'],
                google_sub=payload['google_sub'],
                is_admin=payload.get('is_admin', False)
            )

        return True, new_token

    @staticmethod
    def get_token_payload(token: str) -> Optional[Dict]:
        """Get decoded payload without validation - use only for display purposes"""
        is_valid, payload = SessionManager.validate_session_token(token)
        return payload if is_valid else None

    @staticmethod
    def extract_bearer_token(auth_header: str) -> Optional[str]:
        """
        Extract token from Authorization header

        Args:
            auth_header: Value of Authorization header

        Returns:
            Token string or None if invalid format
        """
        if not auth_header:
            return None

        parts = auth_header.split()
        if len(parts) == 2 and parts[0].lower() == 'bearer':
            return parts[1]

        return None


# Example usage / testing
if __name__ == '__main__':
    # Create test token
    test_token = SessionManager.create_session_token(
        member_id='test-123',
        thread_id='uuid-456',
        email='user@example.com',
        display_name='Test User',
        access_tier=3,
        tier_name='Acolyte',
        google_sub='google-sub-123',
        is_admin=False
    )

    print("✅ Test token created:")
    print(test_token[:50] + "...")

    # Validate token
    is_valid, payload = SessionManager.validate_session_token(test_token)
    print(f"\n✅ Token validation: {is_valid}")
    if payload:
        print(f"   Member: {payload['display_name']} ({payload['email']})")
        print(f"   Tier: {payload['access_tier']} - {payload['tier_name']}")
        print(f"   Thread: {payload['thread_id']}")

    # Test Bearer header extraction
    bearer_header = f"Bearer {test_token}"
    extracted = SessionManager.extract_bearer_token(bearer_header)
    print(f"\n✅ Bearer extraction: {extracted == test_token}")
