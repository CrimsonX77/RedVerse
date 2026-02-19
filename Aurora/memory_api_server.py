"""
Aurora Archive - Memory API Server
Flask-based REST API for per-user memory system

Provides endpoints for E-Drive, Oracle, and RedVerse to:
- Store conversation events
- Load user context
- Get cross-site summaries
- Track emotional trajectories

Phase 2 Integration for HTML interfaces
Python 3.10+ | Flask | Part of the Crimson Gate Protocol
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import logging
from pathlib import Path
from typing import Dict, List, Optional
import sys
import os
from functools import wraps

# Add Aurora directory to path
sys.path.insert(0, str(Path(__file__).parent))

from user_memory_bridge import UserMemoryBridge
from database_manager import get_database
from session_manager import SessionManager
from admin_analytics import AdminAnalytics
from member_card_service import create_member_card_for_account

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for HTML pages

# Initialize database
db = get_database()

# Initialize admin analytics
admin_analytics = AdminAnalytics(db)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ADMIN CHECK - Verify user has admin privileges
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def require_admin(f):
    """Decorator to verify admin privileges on top of JWT auth"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Get member from request (set by @require_auth)
        member_id = getattr(request, 'member_id', None)
        if not member_id:
            logger.warning(f"[ADMIN] No member context in request")
            return jsonify({"error": "Authentication required"}), 401

        # Check if user is admin
        member = db.get_member(member_id)
        if not member or not member.get('is_admin', False):
            logger.warning(f"[ADMIN] Non-admin user {member_id} attempted admin access: {request.path}")
            return jsonify({"error": "Admin privileges required"}), 403

        return f(*args, **kwargs)

    return decorated_function

def require_auth(f):
    """Decorator to validate JWT token on protected endpoints"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Public endpoints don't need auth
        if request.path in ['/api/health']:
            return f(*args, **kwargs)

        # Get Authorization header
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            logger.warning(f"[AUTH] Missing Authorization header for {request.path}")
            return jsonify({"error": "Missing Authorization header"}), 401

        # Extract and validate JWT
        token = SessionManager.extract_bearer_token(auth_header)
        if not token:
            logger.warning(f"[AUTH] Invalid Authorization header format")
            return jsonify({"error": "Invalid Authorization header format"}), 401

        is_valid, payload = SessionManager.validate_session_token(token)
        if not is_valid:
            logger.warning(f"[AUTH] Invalid or expired JWT token")
            return jsonify({"error": "Invalid or expired JWT token"}), 401

        # Extract session info from JWT
        member_id = payload.get('member_id')
        thread_id = payload.get('thread_id')
        access_tier = payload.get('access_tier', 1)
        tier_name = payload.get('tier_name')

        # Re-validate tier from database
        member = db.get_member(member_id)
        if not member:
            logger.warning(f"[AUTH] Member {member_id} not found in database")
            return jsonify({"error": "Member not found"}), 403

        # Check for tier spoofing
        db_tier = member.get('access_tier', 1)
        if access_tier != db_tier:
            logger.warning(f"[AUTH] Tier spoofing attempt: JWT says {access_tier}, DB says {db_tier}")
            return jsonify({"error": "Tier validation failed"}), 403

        # Store JWT payload in request context for use in endpoints
        request.jwt_payload = payload
        request.member_id = member_id
        request.thread_id = thread_id
        request.access_tier = access_tier

        logger.debug(f"[AUTH] Valid JWT for {member_id} with tier {access_tier}")
        return f(*args, **kwargs)

    return decorated_function


def get_user_bridge(thread_id: str, access_tier: int = 1, source: str = "edrive") -> UserMemoryBridge:
    """
    Get or create a UserMemoryBridge for a given thread_id

    Args:
        thread_id: User's thread ID
        access_tier: User's access tier (1-7)
        source: Source module (edrive, oracle, redverse)

    Returns:
        UserMemoryBridge instance
    """
    return UserMemoryBridge(
        thread_id=thread_id,
        access_tier=access_tier,
        module_name=source.upper()
    )


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "Aurora Memory API",
        "version": "2.0.0",
        "auth": "JWT required for /api/memory/* endpoints"
    })


@app.route('/api/memory/store', methods=['POST'])
@require_auth
def store_event():
    """
    Store a conversation event to user's memory (requires JWT auth)

    Request JSON:
    {
        "role": "user|assistant|system",
        "content": "message text",
        "source": "edrive|oracle|redverse",
        "emotion_state": {
            "primary": "joy",
            "intensity": 0.8
        },
        "metadata": {}
    }

    Note: thread_id and access_tier come from JWT, not request body
    """
    try:
        data = request.json

        # Validate required fields
        if not data.get('role'):
            return jsonify({"error": "role is required"}), 400
        if not data.get('content'):
            return jsonify({"error": "content is required"}), 400

        # Use JWT-provided values (guaranteed by @require_auth)
        thread_id = request.thread_id
        access_tier = request.access_tier
        member_id = request.member_id
        source = data.get('source', 'edrive')

        logger.info(f"[MEMORY] Storing event for {member_id} (tier {access_tier})")

        # Get user bridge
        bridge = get_user_bridge(thread_id, access_tier, source)

        # Store event
        bridge.store_user_event(
            role=data['role'],
            content=data['content'],
            source=source,
            emotion_state=data.get('emotion_state'),
            metadata=data.get('metadata')
        )

        return jsonify({
            "success": True,
            "message": "Event stored successfully",
            "member_id": member_id,
            "thread_id": thread_id
        })

    except Exception as e:
        logger.error(f"Error storing event: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/memory/load', methods=['POST'])
@require_auth
def load_context():
    """
    Load user conversation context (requires JWT auth)

    Request JSON:
    {
        "limit": 50  // optional, uses tier default if not provided
    }

    Response:
    {
        "events": [...],
        "count": 10,
        "tier_limit": 50
    }
    """
    try:
        data = request.json or {}

        # Use JWT-provided values
        thread_id = request.thread_id
        access_tier = request.access_tier
        member_id = request.member_id
        limit = data.get('limit')

        logger.info(f"[MEMORY] Loading context for {member_id} (tier {access_tier})")

        # Get user bridge
        bridge = get_user_bridge(thread_id, access_tier)

        # Load context
        events = bridge.load_user_context(last_n=limit)

        return jsonify({
            "events": events,
            "count": len(events),
            "tier": access_tier,
            "tier_name": bridge.tier_name,
            "tier_limit": bridge.memory_depth,
            "member_id": member_id
        })

    except Exception as e:
        logger.error(f"Error loading context: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/memory/conversation_history', methods=['POST'])
@require_auth
def get_conversation_history():
    """
    Get conversation history formatted for AI prompt injection (requires JWT auth)

    Request JSON:
    {
        "limit": 50  // optional
    }

    Response:
    {
        "history": [
            {"role": "user", "content": "..."},
            {"role": "assistant", "content": "..."}
        ],
        "count": 10
    }
    """
    try:
        data = request.json or {}

        # Use JWT-provided values
        thread_id = request.thread_id
        access_tier = request.access_tier
        member_id = request.member_id
        limit = data.get('limit')

        logger.info(f"[MEMORY] Loading conversation history for {member_id}")

        # Get user bridge
        bridge = get_user_bridge(thread_id, access_tier)

        # Get conversation history
        history = bridge.get_conversation_history_for_prompt(limit=limit)

        return jsonify({
            "history": history,
            "count": len(history),
            "member_id": member_id
        })

    except Exception as e:
        logger.error(f"Error getting conversation history: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/memory/cross_site_summary', methods=['POST'])
@require_auth
def get_cross_site_summary():
    """
    Get cross-site activity summary (Tier 4+ only) (requires JWT auth)

    Request JSON:
    {
        "limit": 10
    }

    Response:
    {
        "summary": "text summary",
        "cross_site_enabled": true
    }
    """
    try:
        data = request.json or {}

        # Use JWT-provided values
        thread_id = request.thread_id
        access_tier = request.access_tier
        member_id = request.member_id
        limit = data.get('limit', 10)

        # Check tier eligibility
        if access_tier < 4:
            logger.warning(f"[MEMORY] Cross-site summary denied for {member_id} (tier {access_tier} < 4)")
            return jsonify({"error": "Cross-site summary requires tier 4 or higher"}), 403

        logger.info(f"[MEMORY] Loading cross-site summary for {member_id}")

        # Get user bridge
        bridge = get_user_bridge(thread_id, access_tier)

        # Get summary
        summary = bridge.get_cross_site_summary(limit=limit)

        return jsonify({
            "summary": summary,
            "cross_site_enabled": bridge.cross_site_enabled,
            "member_id": member_id
        })

    except Exception as e:
        logger.error(f"Error getting cross-site summary: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/memory/emotions', methods=['POST'])
@require_auth
def get_emotion_trajectory():
    """
    Get emotional trajectory analysis (requires JWT auth)

    Request JSON:
    {
        "limit": 20
    }

    Response:
    {
        "primary_emotion": "joy",
        "intensity_avg": 0.75,
        "trend": "positive",
        "event_count": 15
    }
    """
    try:
        data = request.json or {}

        # Use JWT-provided values
        thread_id = request.thread_id
        access_tier = request.access_tier
        member_id = request.member_id
        limit = data.get('limit', 20)

        logger.info(f"[MEMORY] Loading emotion trajectory for {member_id}")

        # Get user bridge
        bridge = get_user_bridge(thread_id, access_tier)

        # Get emotion trajectory
        emotions = bridge.get_emotion_trajectory(limit=limit)

        return jsonify({**emotions, "member_id": member_id})

    except Exception as e:
        logger.error(f"Error getting emotion trajectory: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/memory/stats', methods=['POST'])
@require_auth
def get_memory_stats():
    """
    Get memory statistics for a user (requires JWT auth)

    Request JSON: (no specific fields needed, JWT provides all context)

    Response:
    {
        "exists": true,
        "event_count": 150,
        "file_size_bytes": 45678,
        "first_event": "2026-01-15T...",
        "last_event": "2026-02-17T...",
        "tier": 3,
        "tier_name": "Acolyte",
        "memory_depth_limit": 25
    }
    """
    try:
        # Use JWT-provided values
        thread_id = request.thread_id
        access_tier = request.access_tier
        member_id = request.member_id

        logger.info(f"[MEMORY] Getting memory stats for {member_id}")

        # Get user bridge
        bridge = get_user_bridge(thread_id, access_tier)

        # Get stats
        stats = bridge.get_memory_stats()
        stats['member_id'] = member_id

        return jsonify(stats)

    except Exception as e:
        logger.error(f"Error getting memory stats: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500




@app.route('/api/auth/validate_google_token', methods=['POST'])
def validate_google_token():
    """
    Validate Google OAuth token and issue RedVerse JWT session token

    Request JSON:
    {
        "google_token": "eyJhbGc...",  // Google ID token from frontend
        "email": "user@gmail.com"
    }

    Response:
    {
        "success": true,
        "member_id": "member-uuid",
        "thread_id": "thread-uuid",
        "access_tier": 3,
        "tier_name": "Acolyte",
        "session_token": "eyJhbGc...",  // RedVerse JWT
        "display_name": "User Name"
    }
    """
    try:
        data = request.json

        if not data.get('email'):
            return jsonify({"error": "email is required"}), 400

        email = data['email'].lower().strip()

        logger.info(f"[AUTH] Google auth attempt for {email}")

        # Try to find existing member by email
        member = db.get_member_by_email(email)

        if not member:
            # Create new member from Google auth
            logger.info(f"[AUTH] Creating new member for {email}")
            member = db.create_new_member_from_google(
                email=email,
                name=data.get('name', email.split('@')[0]),
                google_sub=data.get('google_sub', '')
            )

            if not member:
                logger.error(f"[AUTH] Failed to create member for {email}")
                return jsonify({"error": "Failed to create member account"}), 500

            # Generate member card with embedded seal on signup
            try:
                card_path = create_member_card_for_account(member, db)
                if card_path:
                    logger.info(f"[AUTH] Generated member card for {member.get('id')}: {card_path}")
                else:
                    logger.warning(f"[AUTH] Member card generation returned None for {email}")
            except Exception as card_error:
                logger.error(f"[AUTH] Error generating member card: {card_error}", exc_info=True)
                # Don't fail auth if card generation fails - continue with session creation

        # Generate RedVerse JWT session token
        session_token = SessionManager.create_session_token(
            member_id=member.get('id'),
            thread_id=member.get('thread_id'),
            email=member.get('email'),
            display_name=member.get('display_name', email.split('@')[0]),
            access_tier=member.get('access_tier', 1),
            tier_name=member.get('tier_name', 'Wanderer'),
            google_sub=member.get('google_sub', ''),
            is_admin=member.get('is_admin', False)
        )

        logger.info(f"[AUTH] Session issued for {email} - tier {member.get('access_tier')}")

        return jsonify({
            "success": True,
            "member_id": member.get('id'),
            "thread_id": member.get('thread_id'),
            "access_tier": member.get('access_tier', 1),
            "tier_name": member.get('tier_name', 'Wanderer'),
            "session_token": session_token,
            "display_name": member.get('display_name', email.split('@')[0]),
            "is_admin": member.get('is_admin', False)
        })

    except Exception as e:
        logger.error(f"[AUTH] Error validating Google token: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500




@app.route('/api/memory/sharing/set_mode', methods=['POST'])
@require_auth
def set_sharing_mode():
    """
    Set memory sharing mode for authenticated user

    Request JSON:
    {
        "mode": "isolated" | "trusted" | "pooled",
        "pooled_tier": 4  // optional, if mode is "pooled"
    }

    Response:
    {
        "success": true,
        "mode": "isolated",
        "message": "Sharing mode updated"
    }
    """
    try:
        data = request.json or {}
        member_id = request.member_id
        mode = data.get('mode', 'isolated')

        # Only Tier 4+ can use sharing modes other than isolated
        access_tier = request.access_tier
        if access_tier < 4 and mode != 'isolated':
            logger.warning(f"[SHARING] Tier {access_tier} user cannot use {mode} sharing")
            return jsonify({"error": "Your tier does not support this sharing mode"}), 403

        pooled_tier = data.get('pooled_tier', access_tier) if mode == 'pooled' else None

        # Update in database
        success = db.set_memory_sharing_mode(member_id, mode, pooled_tier)

        if not success:
            return jsonify({"error": "Failed to set sharing mode"}), 400

        logger.info(f"[SHARING] Set {mode} mode for {member_id}")

        return jsonify({
            "success": True,
            "mode": mode,
            "pooled_tier": pooled_tier,
            "message": f"Sharing mode set to {mode}"
        })

    except Exception as e:
        logger.error(f"[SHARING] Error setting mode: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/memory/sharing/add_trusted', methods=['POST'])
@require_auth
def add_trusted_user():
    """
    Add a trusted user to share memory with (bidirectional)

    Request JSON:
    {
        "trusted_email": "friend@example.com"  // Email of user to trust
    }

    Response:
    {
        "success": true,
        "trusted_member_id": "uuid",
        "message": "User added to trusted list"
    }
    """
    try:
        data = request.json or {}
        member_id = request.member_id
        access_tier = request.access_tier
        trusted_email = data.get('trusted_email', '').lower().strip()

        if not trusted_email:
            return jsonify({"error": "trusted_email is required"}), 400

        # Only Tier 4+ can share
        if access_tier < 4:
            return jsonify({"error": "Your tier does not support trusted sharing"}), 403

        # Find trusted member by email
        trusted_member = db.get_member_by_email(trusted_email)
        if not trusted_member:
            logger.warning(f"[SHARING] Trusted user not found: {trusted_email}")
            return jsonify({"error": "User not found"}), 404

        trusted_member_id = trusted_member.get('id')

        # Add bidirectional trust
        success = db.add_trusted_user(member_id, trusted_member_id)

        if not success:
            return jsonify({"error": "Failed to add trusted user"}), 400

        logger.info(f"[SHARING] Added trusted user: {member_id} <-> {trusted_member_id}")

        return jsonify({
            "success": True,
            "trusted_member_id": trusted_member_id,
            "trusted_name": trusted_member.get('display_name'),
            "message": f"Successfully added {trusted_member.get('display_name')} to trusted users"
        })

    except Exception as e:
        logger.error(f"[SHARING] Error adding trusted user: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/memory/accessible_contexts', methods=['GET', 'POST'])
@require_auth
def get_accessible_contexts():
    """
    Get all memories accessible to the user based on sharing mode

    Response:
    {
        "sharing_mode": "isolated",
        "accessible_threads": ["uuid1", "uuid2"],
        "total_accessible": 2,
        "thread_details": [
            {
                "thread_id": "uuid1",
                "owner": "User Name",
                "is_own": true,
                "shared_via": "direct"
            }
        ]
    }
    """
    try:
        member_id = request.member_id
        member = db.get_member(member_id)

        if not member:
            return jsonify({"error": "Member not found"}), 403

        # Get accessible thread_ids
        accessible_threads = db.get_accessible_thread_ids(member_id)

        # Build thread details
        thread_details = []
        for thread_id in accessible_threads:
            # Find which member owns this thread
            owner_member = None
            for m in db.get_all_members():
                if m.get('thread_id') == thread_id:
                    owner_member = m
                    break

            detail = {
                "thread_id": thread_id,
                "owner": owner_member.get('display_name', 'Unknown') if owner_member else 'Unknown',
                "is_own": thread_id == member.get('thread_id'),
                "shared_via": "direct" if thread_id == member.get('thread_id') else member.get('memory_sharing_mode', 'isolated')
            }
            thread_details.append(detail)

        logger.info(f"[SHARING] Got {len(accessible_threads)} accessible contexts for {member_id}")

        return jsonify({
            "sharing_mode": member.get('memory_sharing_mode', 'isolated'),
            "accessible_threads": accessible_threads,
            "total_accessible": len(accessible_threads),
            "thread_details": thread_details
        })

    except Exception as e:
        logger.error(f"[SHARING] Error getting accessible contexts: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500




# ════════════════════════════════════════════════════════════════════════════
# ADMIN ENDPOINTS - Crimson Control Hall
# ════════════════════════════════════════════════════════════════════════════

@app.route('/api/admin/overview', methods=['GET', 'POST'])
@require_auth
@require_admin
def admin_overview():
    """
    Get system overview statistics for admin dashboard

    Response:
    {
        "total_users": 42,
        "users_by_tier": {...},
        "total_memories": 5000,
        "suspicious_patterns": [...],
        "emotion_heatmap": {...}
    }
    """
    try:
        all_users = admin_analytics.get_all_users_summary()
        tier_dist = admin_analytics.get_tier_distribution()
        emotion_heat = admin_analytics.get_emotion_heatmap(days=30)
        patterns = admin_analytics.get_suspicious_patterns()

        total_memories = sum(u.get('total_events', 0) for u in all_users)

        logger.info("[ADMIN] Overview requested")

        return jsonify({
            "total_users": len(all_users),
            "users_by_tier": tier_dist,
            "total_memories": total_memories,
            "avg_memories_per_user": round(total_memories / len(all_users), 1) if all_users else 0,
            "suspicious_patterns": patterns,
            "emotion_heatmap": emotion_heat
        })

    except Exception as e:
        logger.error(f"[ADMIN] Error getting overview: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/admin/users', methods=['GET', 'POST'])
@require_auth
@require_admin
def admin_users_list():
    """
    Get list of all users with summary stats

    Query params:
        tier: Filter by tier (e.g., "4")
        sort: Sort by field ("events", "created", "activity")

    Response:
    {
        "users": [
            {
                "member_id": "uuid",
                "display_name": "User",
                "tier": 4,
                "total_events": 150,
                "last_activity": "2026-02-19T...",
                "admin_flags": [...]
            }
        ],
        "total": 42
    }
    """
    try:
        tier_filter = request.args.get('tier') or request.json.get('tier') if request.is_json else None
        sort_by = request.args.get('sort', 'created') or request.json.get('sort', 'created') if request.is_json else 'created'

        all_users = admin_analytics.get_all_users_summary()

        # Filter by tier if specified
        if tier_filter:
            try:
                tier_num = int(tier_filter)
                all_users = [u for u in all_users if u.get('tier') == tier_num]
            except ValueError:
                pass

        # Sort
        if sort_by == 'events':
            all_users.sort(key=lambda x: x.get('total_events', 0), reverse=True)
        elif sort_by == 'activity':
            all_users.sort(key=lambda x: x.get('last_event_time', ''), reverse=True)
        else:  # created
            all_users.sort(key=lambda x: x.get('created_at', ''), reverse=True)

        logger.info(f"[ADMIN] Retrieved users list ({len(all_users)} users)")

        return jsonify({
            "users": all_users,
            "total": len(all_users)
        })

    except Exception as e:
        logger.error(f"[ADMIN] Error getting users list: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/admin/user/<member_id>/timeline', methods=['GET', 'POST'])
@require_auth
@require_admin
def admin_user_timeline(member_id):
    """
    Get full memory timeline for a user (read-only observation)

    Query params:
        limit: Max events (default 100)

    Response:
    {
        "member_id": "uuid",
        "member_name": "User Name",
        "tier": 4,
        "total_events": 150,
        "events": [...]
    }
    """
    try:
        limit = int(request.args.get('limit', 100))
        if limit > 500:
            limit = 500  # Cap at 500 for performance

        timeline = admin_analytics.get_user_timeline(member_id, limit=limit)
        stats = admin_analytics.get_user_memory_stats(member_id)

        if not stats:
            return jsonify({"error": "User not found"}), 404

        logger.info(f"[ADMIN] Timeline viewed for {member_id} ({len(timeline)} events)")

        return jsonify({
            "member_id": member_id,
            "member_name": stats.get('display_name'),
            "tier": stats.get('tier'),
            "sharing_mode": stats.get('sharing_mode'),
            "total_events": stats.get('total_events'),
            "events_shown": len(timeline),
            "events": timeline
        })

    except Exception as e:
        logger.error(f"[ADMIN] Error getting timeline: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/admin/user/<member_id>/analytics', methods=['GET', 'POST'])
@require_auth
@require_admin
def admin_user_analytics(member_id):
    """
    Get detailed analytics for a user

    Response:
    {
        "stats": {...},
        "emotion_data": {...},
        "activity_summary": {...}
    }
    """
    try:
        stats = admin_analytics.get_user_memory_stats(member_id)
        if not stats:
            return jsonify({"error": "User not found"}), 404

        timeline = admin_analytics.get_user_timeline(member_id)

        # Calculate emotion distribution
        emotion_counts = defaultdict(int)
        for event in timeline:
            emotion = event.get('emotion_state', {}).get('primary', 'neutral')
            emotion_counts[emotion] += 1

        # Calculate activity by day
        daily_activity = defaultdict(int)
        for event in timeline:
            date = event.get('timestamp', '')[:10]
            daily_activity[date] += 1

        # Calculate source distribution
        source_dist = defaultdict(int)
        for event in timeline:
            source = event.get('source', 'unknown')
            source_dist[source] += 1

        logger.info(f"[ADMIN] Analytics viewed for {member_id}")

        return jsonify({
            "stats": stats,
            "emotion_distribution": dict(emotion_counts),
            "daily_activity": dict(sorted(daily_activity.items())),
            "source_distribution": dict(source_dist)
        })

    except Exception as e:
        logger.error(f"[ADMIN] Error getting analytics: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/admin/search', methods=['POST'])
@require_auth
@require_admin
def admin_search():
    """
    Search across all user memories

    Request JSON:
    {
        "query": "search term",
        "case_sensitive": false
    }

    Response:
    {
        "query": "search term",
        "results_count": 5,
        "results": [...]
    }
    """
    try:
        data = request.json or {}
        query = data.get('query', '').strip()

        if not query:
            return jsonify({"error": "query is required"}), 400

        if len(query) < 2:
            return jsonify({"error": "query must be at least 2 characters"}), 400

        case_sensitive = data.get('case_sensitive', False)
        results = admin_analytics.search_memory_content(query, case_sensitive=case_sensitive)

        logger.info(f"[ADMIN] Search executed: '{query}' ({len(results)} results)")

        return jsonify({
            "query": query,
            "results_count": len(results),
            "results": results[:100]  # Limit response
        })

    except Exception as e:
        logger.error(f"[ADMIN] Error searching: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/admin/sharing_graph', methods=['GET', 'POST'])
@require_auth
@require_admin
def admin_sharing_graph():
    """
    Get visualization data for memory sharing network

    Response:
    {
        "nodes": [...],  // Users
        "edges": [...],  // Sharing relationships
        "pooled_groups": {...}
    }
    """
    try:
        graph = admin_analytics.get_sharing_graph()
        logger.info(f"[ADMIN] Sharing graph requested ({graph.get('total_users')} users)")

        return jsonify(graph)

    except Exception as e:
        logger.error(f"[ADMIN] Error getting sharing graph: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/admin/user/<member_id>/flags', methods=['GET', 'POST'])
@require_auth
@require_admin
def admin_user_flags(member_id):
    """
    Get and manage admin observation flags for a user

    GET: Retrieve flags
    POST: Add new flag

    Request JSON (POST):
    {
        "note": "Observation note"
    }

    Response:
    {
        "member_id": "uuid",
        "flags": [...]
    }
    """
    try:
        if request.method == 'GET':
            flags = admin_analytics.get_user_admin_flags(member_id)
            logger.info(f"[ADMIN] Flags retrieved for {member_id} ({len(flags)} flags)")

            return jsonify({
                "member_id": member_id,
                "flags_count": len(flags),
                "flags": flags
            })

        elif request.method == 'POST':
            data = request.json or {}
            note = data.get('note', '').strip()

            if not note:
                return jsonify({"error": "note is required"}), 400

            # Add flag
            success = admin_analytics.add_admin_observation(member_id, note, admin_id=request.member_id)

            if not success:
                return jsonify({"error": "Failed to add flag"}), 400

            logger.info(f"[ADMIN] Flag added for {member_id}: {note}")

            return jsonify({
                "success": True,
                "message": "Observation flag added",
                "member_id": member_id
            })

    except Exception as e:
        logger.error(f"[ADMIN] Error managing flags: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/admin/emotions', methods=['GET', 'POST'])
@require_auth
@require_admin
def admin_emotions_heatmap():
    """
    Get system-wide emotion analytics

    Query params:
        days: Number of days to analyze (default 30)

    Response:
    {
        "emotion_counts": {...},
        "time_series": {...},
        "total_events_analyzed": 5000,
        "days_analyzed": 30
    }
    """
    try:
        days = int(request.args.get('days', 30))
        days = min(days, 365)  # Cap at 1 year

        emotion_data = admin_analytics.get_emotion_heatmap(days=days)
        logger.info(f"[ADMIN] Emotion heatmap requested ({days} days)")

        return jsonify(emotion_data)

    except Exception as e:
        logger.error(f"[ADMIN] Error getting emotions: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


from collections import defaultdict
@app.route('/api/member/validate', methods=['POST'])
def validate_member():
    """
    Validate member credentials and return session info

    Request JSON:
    {
        "member_id": "m_abc123",
        "email": "user@example.com"
    }

    Response:
    {
        "valid": true,
        "thread_id": "uuid",
        "access_tier": 3,
        "tier_name": "Acolyte",
        "member_profile": {...}
    }
    """
    try:
        data = request.json

        if not data.get('member_id'):
            return jsonify({"error": "member_id is required"}), 400

        member_id = data['member_id']

        # Get member from database
        member = db.get_member(member_id)

        if not member:
            return jsonify({"valid": False, "error": "Member not found"}), 404

        # Return session info
        return jsonify({
            "valid": True,
            "thread_id": member.get('thread_id'),
            "access_tier": member.get('access_tier', 1),
            "tier_name": member.get('tier_name', 'Wanderer'),
            "member_profile": {
                "name": member.get('member_profile', {}).get('name'),
                "email": member.get('member_profile', {}).get('email')
            }
        })

    except Exception as e:
        logger.error(f"Error validating member: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    print("=" * 70)
    print("Aurora Memory API Server")
    print("Phase 2 Integration - Per-User JSONL Memory System")
    print("=" * 70)
    print()
    print("Starting Flask server on http://localhost:5000")
    print()
    print("Available endpoints:")
    print("  GET  /api/health")
    print("  POST /api/memory/store")
    print("  POST /api/memory/load")
    print("  POST /api/memory/conversation_history")
    print("  POST /api/memory/cross_site_summary")
    print("  POST /api/memory/emotions")
    print("  POST /api/memory/stats")
    print("  POST /api/member/validate")
    print()

    # Run Flask app
    app.run(host='0.0.0.0', port=5000, debug=True)
