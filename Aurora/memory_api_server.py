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

# Add Aurora directory to path
sys.path.insert(0, str(Path(__file__).parent))

from user_memory_bridge import UserMemoryBridge
from database_manager import get_database

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
        "version": "1.0.0"
    })


@app.route('/api/memory/store', methods=['POST'])
def store_event():
    """
    Store a conversation event to user's memory

    Request JSON:
    {
        "thread_id": "uuid",
        "access_tier": 1,
        "role": "user|assistant|system",
        "content": "message text",
        "source": "edrive|oracle|redverse",
        "emotion_state": {
            "primary": "joy",
            "intensity": 0.8
        },
        "metadata": {}
    }
    """
    try:
        data = request.json

        # Validate required fields
        if not data.get('thread_id'):
            return jsonify({"error": "thread_id is required"}), 400
        if not data.get('role'):
            return jsonify({"error": "role is required"}), 400
        if not data.get('content'):
            return jsonify({"error": "content is required"}), 400

        thread_id = data['thread_id']
        access_tier = data.get('access_tier', 1)
        source = data.get('source', 'edrive')

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
            "message": "Event stored successfully"
        })

    except Exception as e:
        logger.error(f"Error storing event: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/memory/load', methods=['POST'])
def load_context():
    """
    Load user conversation context

    Request JSON:
    {
        "thread_id": "uuid",
        "access_tier": 1,
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
        data = request.json

        if not data.get('thread_id'):
            return jsonify({"error": "thread_id is required"}), 400

        thread_id = data['thread_id']
        access_tier = data.get('access_tier', 1)
        limit = data.get('limit')

        # Get user bridge
        bridge = get_user_bridge(thread_id, access_tier)

        # Load context
        events = bridge.load_user_context(last_n=limit)

        return jsonify({
            "events": events,
            "count": len(events),
            "tier": access_tier,
            "tier_name": bridge.tier_name,
            "tier_limit": bridge.memory_depth
        })

    except Exception as e:
        logger.error(f"Error loading context: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/memory/conversation_history', methods=['POST'])
def get_conversation_history():
    """
    Get conversation history formatted for AI prompt injection

    Request JSON:
    {
        "thread_id": "uuid",
        "access_tier": 1,
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
        data = request.json

        if not data.get('thread_id'):
            return jsonify({"error": "thread_id is required"}), 400

        thread_id = data['thread_id']
        access_tier = data.get('access_tier', 1)
        limit = data.get('limit')

        # Get user bridge
        bridge = get_user_bridge(thread_id, access_tier)

        # Get conversation history
        history = bridge.get_conversation_history_for_prompt(limit=limit)

        return jsonify({
            "history": history,
            "count": len(history)
        })

    except Exception as e:
        logger.error(f"Error getting conversation history: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/memory/cross_site_summary', methods=['POST'])
def get_cross_site_summary():
    """
    Get cross-site activity summary (Tier 4+ only)

    Request JSON:
    {
        "thread_id": "uuid",
        "access_tier": 4,
        "limit": 10
    }

    Response:
    {
        "summary": "text summary",
        "cross_site_enabled": true
    }
    """
    try:
        data = request.json

        if not data.get('thread_id'):
            return jsonify({"error": "thread_id is required"}), 400

        thread_id = data['thread_id']
        access_tier = data.get('access_tier', 1)
        limit = data.get('limit', 10)

        # Get user bridge
        bridge = get_user_bridge(thread_id, access_tier)

        # Get summary
        summary = bridge.get_cross_site_summary(limit=limit)

        return jsonify({
            "summary": summary,
            "cross_site_enabled": bridge.cross_site_enabled
        })

    except Exception as e:
        logger.error(f"Error getting cross-site summary: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/memory/emotions', methods=['POST'])
def get_emotion_trajectory():
    """
    Get emotional trajectory analysis

    Request JSON:
    {
        "thread_id": "uuid",
        "access_tier": 1,
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
        data = request.json

        if not data.get('thread_id'):
            return jsonify({"error": "thread_id is required"}), 400

        thread_id = data['thread_id']
        access_tier = data.get('access_tier', 1)
        limit = data.get('limit', 20)

        # Get user bridge
        bridge = get_user_bridge(thread_id, access_tier)

        # Get emotion trajectory
        emotions = bridge.get_emotion_trajectory(limit=limit)

        return jsonify(emotions)

    except Exception as e:
        logger.error(f"Error getting emotion trajectory: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/memory/stats', methods=['POST'])
def get_memory_stats():
    """
    Get memory statistics for a user

    Request JSON:
    {
        "thread_id": "uuid",
        "access_tier": 1
    }

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
        data = request.json

        if not data.get('thread_id'):
            return jsonify({"error": "thread_id is required"}), 400

        thread_id = data['thread_id']
        access_tier = data.get('access_tier', 1)

        # Get user bridge
        bridge = get_user_bridge(thread_id, access_tier)

        # Get stats
        stats = bridge.get_memory_stats()

        return jsonify(stats)

    except Exception as e:
        logger.error(f"Error getting memory stats: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


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
