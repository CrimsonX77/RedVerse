"""
Aurora Archive - User Memory Bridge
Per-user JSONL memory system for cross-site AI continuity

Phase 2 Implementation:
- Each user gets their own conversation memory file (threads/{thread_id}.jsonl)
- Memory persists across sessions and pages (E-Drive, Oracle, RedVerse)
- Tier-based memory depth limits
- Cross-site context awareness for seamless AI continuity

Python 3.10+ | Part of the Crimson Gate Protocol
"""

import json
import os
import uuid
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import logging

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class UserMemoryBridge:
    """
    Per-user memory that persists across sessions and pages.
    Links to user via thread_id, supports tiered access control.
    """

    # Tier configuration (from member_manager.py)
    TIER_CONFIG = {
        1: {"name": "Wanderer",      "memory_depth": 0,   "cross_site": False, "custom_soul": False},
        2: {"name": "Initiate",      "memory_depth": 10,  "cross_site": False, "custom_soul": False},
        3: {"name": "Acolyte",       "memory_depth": 25,  "cross_site": False, "custom_soul": False},
        4: {"name": "Keeper",        "memory_depth": 50,  "cross_site": True,  "custom_soul": False},
        5: {"name": "Sentinel",      "memory_depth": 100, "cross_site": True,  "custom_soul": True},
        6: {"name": "Archon",        "memory_depth": 500, "cross_site": True,  "custom_soul": True},
        7: {"name": "Inner Sanctum", "memory_depth": -1,  "cross_site": True,  "custom_soul": True},
    }

    def __init__(self, thread_id: str, access_tier: int = 1, module_name: str = "EDrive"):
        """
        Initialize user memory bridge

        Args:
            thread_id: UUID linking to user's memory file
            access_tier: User's access tier (1-7)
            module_name: Source module (EDrive, Oracle, RedVerse)
        """
        self.thread_id = thread_id
        self.access_tier = access_tier
        self.module_name = module_name

        # Get tier configuration
        self.tier_config = self.TIER_CONFIG.get(access_tier, self.TIER_CONFIG[1])
        self.tier_name = self.tier_config["name"]
        self.memory_depth = self.tier_config["memory_depth"]
        self.cross_site_enabled = self.tier_config["cross_site"]

        # Setup paths
        self.memory_dir = Path("memory")
        self.threads_dir = self.memory_dir / "threads"
        self.user_memory_file = self.threads_dir / f"{thread_id}.jsonl"

        # Ensure directories exist
        self.threads_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"UserMemoryBridge initialized for thread_id={thread_id}, tier={access_tier} ({self.tier_name})")

    def load_user_context(self, last_n: Optional[int] = None) -> List[Dict]:
        """
        Load last N events for this user across all pages.

        Args:
            last_n: Number of events to load (None uses tier default)

        Returns:
            List of event dictionaries, newest first
        """
        # Determine how many events to load based on tier
        if last_n is None:
            last_n = self.memory_depth

        # Tier 1 (Wanderer) gets no memory
        if last_n == 0:
            logger.debug(f"Tier {self.access_tier} ({self.tier_name}): No memory access")
            return []

        # Tier 7 (Inner Sanctum) gets unlimited memory (-1)
        if last_n == -1:
            last_n = None  # Load all

        # Check if memory file exists
        if not self.user_memory_file.exists():
            logger.debug(f"No memory file found for thread_id={self.thread_id}")
            return []

        # Load events from JSONL
        events = []
        try:
            with open(self.user_memory_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        events.append(json.loads(line))

            # Return last N events (newest first)
            if last_n is not None:
                events = events[-last_n:]

            events.reverse()  # Newest first
            logger.info(f"Loaded {len(events)} events for thread_id={self.thread_id}")
            return events

        except Exception as e:
            logger.error(f"Error loading user context: {e}", exc_info=True)
            return []

    def store_user_event(
        self,
        role: str,
        content: str,
        source: Optional[str] = None,
        emotion_state: Optional[Dict] = None,
        metadata: Optional[Dict] = None
    ):
        """
        Append event to user's JSONL file.

        Args:
            role: Message role (user, assistant, system)
            content: Message content
            source: Source module (defaults to self.module_name)
            emotion_state: Emotional state dict (optional)
            metadata: Additional metadata (optional)
        """
        event = {
            "event_id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "source": source or self.module_name.lower(),
            "role": role,
            "content": content,
            "emotion_state": emotion_state or {},
            "metadata": metadata or {}
        }

        # Ensure metadata includes tier info
        event["metadata"]["tier_at_time"] = self.access_tier
        event["metadata"]["tier_name"] = self.tier_name

        try:
            # Append to JSONL file
            with open(self.user_memory_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(event, ensure_ascii=False) + '\n')

            logger.debug(f"Stored {role} event for thread_id={self.thread_id} from {event['source']}")

        except Exception as e:
            logger.error(f"Error storing user event: {e}", exc_info=True)

    def get_cross_site_summary(self, limit: int = 10) -> str:
        """
        Generate a summary of user's activity across E-Drive and Oracle.
        Used for the AI's "awareness" of the user between pages.

        Args:
            limit: Number of recent events to summarize

        Returns:
            Formatted summary string for prompt injection
        """
        # Only available for Tier 4+ (cross-site enabled)
        if not self.cross_site_enabled:
            return ""

        # Load recent events
        events = self.load_user_context(last_n=limit)

        if not events:
            return "No previous interactions recorded."

        # Build summary
        summary_lines = []
        source_counts = {}

        for event in events:
            source = event.get("source", "unknown")
            source_counts[source] = source_counts.get(source, 0) + 1

        # Format summary
        summary_lines.append(f"Recent activity ({len(events)} events):")
        for source, count in source_counts.items():
            summary_lines.append(f"  - {source.upper()}: {count} interactions")

        # Add last interaction details
        if events:
            last_event = events[0]  # Newest first
            last_source = last_event.get("source", "unknown")
            last_timestamp = last_event.get("timestamp", "")
            last_content_preview = last_event.get("content", "")[:100]

            summary_lines.append(f"\nLast interaction: {last_source.upper()} at {last_timestamp}")
            summary_lines.append(f"Preview: {last_content_preview}...")

        return "\n".join(summary_lines)

    def get_conversation_history_for_prompt(self, limit: Optional[int] = None) -> List[Dict]:
        """
        Get conversation history formatted for AI prompt injection.

        Args:
            limit: Number of messages to include (None uses tier default)

        Returns:
            List of {"role": str, "content": str} dicts for prompt
        """
        events = self.load_user_context(last_n=limit)

        # Format for prompt (only user and assistant messages)
        history = []
        for event in reversed(events):  # Chronological order
            if event.get("role") in ["user", "assistant"]:
                history.append({
                    "role": event["role"],
                    "content": event["content"]
                })

        return history

    def get_emotion_trajectory(self, limit: int = 20) -> Dict:
        """
        Analyze emotional trajectory from recent events.

        Args:
            limit: Number of recent events to analyze

        Returns:
            Dict with emotion statistics
        """
        events = self.load_user_context(last_n=limit)

        if not events:
            return {"primary_emotion": None, "intensity_avg": 0, "trend": "neutral"}

        # Collect emotions
        emotions = []
        for event in events:
            emotion_state = event.get("emotion_state", {})
            if emotion_state:
                emotions.append(emotion_state)

        if not emotions:
            return {"primary_emotion": None, "intensity_avg": 0, "trend": "neutral"}

        # Calculate statistics
        primary_emotions = [e.get("primary") for e in emotions if e.get("primary")]
        intensities = [e.get("intensity", 0) for e in emotions if "intensity" in e]

        most_common_emotion = max(set(primary_emotions), key=primary_emotions.count) if primary_emotions else None
        avg_intensity = sum(intensities) / len(intensities) if intensities else 0

        return {
            "primary_emotion": most_common_emotion,
            "intensity_avg": round(avg_intensity, 2),
            "trend": "positive" if avg_intensity > 0.5 else "neutral" if avg_intensity > 0.3 else "negative",
            "event_count": len(emotions)
        }

    def clear_user_memory(self):
        """
        Clear all memory for this user (admin function).
        WARNING: This is destructive and cannot be undone.
        """
        if self.user_memory_file.exists():
            self.user_memory_file.unlink()
            logger.warning(f"Cleared all memory for thread_id={self.thread_id}")

    def get_memory_stats(self) -> Dict:
        """
        Get statistics about this user's memory.

        Returns:
            Dict with event count, file size, date range
        """
        if not self.user_memory_file.exists():
            return {
                "exists": False,
                "event_count": 0,
                "file_size_bytes": 0
            }

        # Count lines
        event_count = 0
        first_timestamp = None
        last_timestamp = None

        try:
            with open(self.user_memory_file, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f):
                    if line.strip():
                        event_count += 1
                        event = json.loads(line)
                        timestamp = event.get("timestamp")

                        if line_num == 0:
                            first_timestamp = timestamp
                        last_timestamp = timestamp

        except Exception as e:
            logger.error(f"Error getting memory stats: {e}")

        file_size = self.user_memory_file.stat().st_size

        return {
            "exists": True,
            "event_count": event_count,
            "file_size_bytes": file_size,
            "first_event": first_timestamp,
            "last_event": last_timestamp,
            "tier": self.access_tier,
            "tier_name": self.tier_name,
            "memory_depth_limit": self.memory_depth
        }


# Example usage and testing
if __name__ == '__main__':
    print("=" * 70)
    print("User Memory Bridge - Phase 2 Test")
    print("=" * 70)

    # Create a test user memory bridge (Tier 3 - Acolyte)
    test_thread_id = str(uuid.uuid4())
    print(f"\n1. Creating UserMemoryBridge for thread_id: {test_thread_id}")
    print(f"   Tier: 3 (Acolyte)")

    bridge = UserMemoryBridge(thread_id=test_thread_id, access_tier=3, module_name="EDrive")

    # Store some test events
    print("\n2. Storing test events...")
    bridge.store_user_event(
        role="user",
        content="Hello, I'm looking for some fantasy books.",
        emotion_state={"primary": "curiosity", "intensity": 0.7}
    )

    bridge.store_user_event(
        role="assistant",
        content="Welcome! I'd be happy to help you find some fantasy books. What type of fantasy are you interested in?",
        emotion_state={"primary": "joy", "intensity": 0.8}
    )

    bridge.store_user_event(
        role="user",
        content="I love epic fantasy with dragons!",
        emotion_state={"primary": "excitement", "intensity": 0.9}
    )

    print("   ✓ Stored 3 events")

    # Load context
    print("\n3. Loading user context...")
    context = bridge.load_user_context(last_n=10)
    print(f"   ✓ Loaded {len(context)} events")

    for i, event in enumerate(context):
        print(f"   [{i+1}] {event['role']}: {event['content'][:50]}...")

    # Get cross-site summary
    print("\n4. Generating cross-site summary...")
    summary = bridge.get_cross_site_summary()
    print(summary)

    # Get emotion trajectory
    print("\n5. Analyzing emotion trajectory...")
    emotions = bridge.get_emotion_trajectory()
    print(f"   Primary emotion: {emotions['primary_emotion']}")
    print(f"   Average intensity: {emotions['intensity_avg']}")
    print(f"   Trend: {emotions['trend']}")

    # Get memory stats
    print("\n6. Memory statistics...")
    stats = bridge.get_memory_stats()
    print(f"   Event count: {stats['event_count']}")
    print(f"   File size: {stats['file_size_bytes']} bytes")
    print(f"   Tier: {stats['tier']} ({stats['tier_name']})")
    print(f"   Memory depth limit: {stats['memory_depth_limit']}")

    print("\n✓ User Memory Bridge test complete!")
    print(f"✓ Memory file: {bridge.user_memory_file}")
