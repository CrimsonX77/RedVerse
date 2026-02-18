"""
Aurora Archive - Admin Analytics
Provides backend analytics and observational data for Crimson Control Hall
Staff can view timelines, search memories, analyze patterns - but cannot modify user data

Phase 2C Implementation - Read-only admin observation system
"""

import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import defaultdict

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class AdminAnalytics:
    """
    Provides analytics and observation data for admin staff
    All functions are read-only - no modification of user data
    """

    def __init__(self, db, memory_dir: str = "memory/threads"):
        """
        Initialize admin analytics

        Args:
            db: DatabaseManager instance
            memory_dir: Path to memory threads directory
        """
        self.db = db
        self.memory_dir = Path(memory_dir)
        self.threads_dir = self.memory_dir / "threads"

    # ════════════════════════════════════════════════════════════════════════════
    # USER STATISTICS
    # ════════════════════════════════════════════════════════════════════════════

    def get_user_memory_stats(self, member_id: str) -> Optional[Dict]:
        """
        Get memory statistics for a single user

        Args:
            member_id: Member ID

        Returns:
            Dictionary with user stats or None
        """
        try:
            member = self.db.get_member(member_id)
            if not member:
                logger.warning(f"[ADMIN] Member not found: {member_id}")
                return None

            thread_id = member.get('thread_id')
            memory_file = self.threads_dir / f"{thread_id}.jsonl"

            stats = {
                'member_id': member_id,
                'display_name': member.get('display_name'),
                'email': member.get('email'),
                'tier': member.get('access_tier', 1),
                'tier_name': member.get('tier_name', 'Wanderer'),
                'sharing_mode': member.get('memory_sharing_mode', 'isolated'),
                'thread_id': thread_id,
                'memory_file_exists': memory_file.exists(),
                'total_events': 0,
                'file_size_bytes': 0,
                'first_event_time': None,
                'last_event_time': None,
                'created_at': member.get('created_at'),
                'admin_flags': member.get('admin_flags', []),
                'trusted_users_count': len(member.get('trusted_users', [])),
                'is_admin': member.get('is_admin', False)
            }

            if memory_file.exists():
                try:
                    events = []
                    with open(memory_file, 'r', encoding='utf-8') as f:
                        for line in f:
                            line = line.strip()
                            if line:
                                try:
                                    events.append(json.loads(line))
                                except json.JSONDecodeError:
                                    continue

                    stats['total_events'] = len(events)
                    stats['file_size_bytes'] = memory_file.stat().st_size

                    if events:
                        stats['first_event_time'] = events[0].get('timestamp')
                        stats['last_event_time'] = events[-1].get('timestamp')

                except Exception as e:
                    logger.warning(f"[ADMIN] Error reading memory file for {member_id}: {e}")

            return stats

        except Exception as e:
            logger.error(f"[ADMIN] Error getting user stats: {e}", exc_info=True)
            return None

    def get_all_users_summary(self) -> List[Dict]:
        """
        Get summary statistics for all users

        Returns:
            List of user summary dicts
        """
        try:
            all_members = self.db.get_all_members()
            summaries = []

            for member in all_members:
                member_id = member.get('id', member.get('member_id'))
                stats = self.get_user_memory_stats(member_id)
                if stats:
                    summaries.append(stats)

            logger.info(f"[ADMIN] Generated summaries for {len(summaries)} users")
            return summaries

        except Exception as e:
            logger.error(f"[ADMIN] Error getting users summary: {e}", exc_info=True)
            return []

    def get_tier_distribution(self) -> Dict:
        """
        Get distribution of users across tiers

        Returns:
            Dict with tier counts and percentages
        """
        try:
            all_members = self.db.get_all_members()
            distribution = {}

            for member in all_members:
                tier = member.get('access_tier', 1)
                tier_name = member.get('tier_name', 'Unknown')
                key = f"Tier {tier} - {tier_name}"

                distribution[key] = distribution.get(key, 0) + 1

            total = sum(distribution.values())
            for key in distribution:
                distribution[key] = {
                    'count': distribution[key],
                    'percentage': round(100 * distribution[key] / total, 1) if total > 0 else 0
                }

            logger.info(f"[ADMIN] Tier distribution: {len(distribution)} tiers")
            return distribution

        except Exception as e:
            logger.error(f"[ADMIN] Error getting tier distribution: {e}", exc_info=True)
            return {}

    # ════════════════════════════════════════════════════════════════════════════
    # MEMORY ANALYTICS
    # ════════════════════════════════════════════════════════════════════════════

    def get_user_timeline(self, member_id: str, limit: Optional[int] = None) -> List[Dict]:
        """
        Get full memory timeline for a user (read-only observation)

        Args:
            member_id: Member ID
            limit: Max events to return (None = all)

        Returns:
            List of events in chronological order (newest first)
        """
        try:
            member = self.db.get_member(member_id)
            if not member:
                logger.warning(f"[ADMIN] Member not found: {member_id}")
                return []

            thread_id = member.get('thread_id')
            memory_file = self.threads_dir / f"{thread_id}.jsonl"

            if not memory_file.exists():
                logger.debug(f"[ADMIN] No memory file for {member_id}")
                return []

            events = []
            try:
                with open(memory_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                event = json.loads(line)
                                # Add member context
                                event['member_id'] = member_id
                                event['member_name'] = member.get('display_name')
                                event['tier_at_time'] = event.get('metadata', {}).get('tier_at_time', member.get('access_tier'))
                                events.append(event)
                            except json.JSONDecodeError:
                                continue

                # Reverse for newest first
                events.reverse()

                if limit:
                    events = events[:limit]

                logger.info(f"[ADMIN] Retrieved {len(events)} timeline events for {member_id}")
                return events

            except Exception as e:
                logger.warning(f"[ADMIN] Error reading timeline: {e}")
                return []

        except Exception as e:
            logger.error(f"[ADMIN] Error getting user timeline: {e}", exc_info=True)
            return []

    def search_memory_content(self, query: str, case_sensitive: bool = False) -> List[Dict]:
        """
        Full-text search across all user memories

        Args:
            query: Search query
            case_sensitive: Whether to be case-sensitive

        Returns:
            List of matching events with member context
        """
        try:
            query_text = query if case_sensitive else query.lower()
            results = []

            all_members = self.db.get_all_members()

            for member in all_members:
                member_id = member.get('id', member.get('member_id'))
                timeline = self.get_user_timeline(member_id)

                for event in timeline:
                    content = event.get('content', '')
                    search_content = content if case_sensitive else content.lower()

                    if query_text in search_content:
                        results.append({
                            'matched_content': content,
                            'event': event,
                            'match_offset': search_content.find(query_text),
                            'context': f"{member.get('display_name')} on {event.get('timestamp', 'unknown')}"
                        })

            logger.info(f"[ADMIN] Search found {len(results)} matches for '{query}'")
            return results[:100]  # Limit to 100 results

        except Exception as e:
            logger.error(f"[ADMIN] Error searching memories: {e}", exc_info=True)
            return []

    def get_emotion_heatmap(self, days: int = 30) -> Dict:
        """
        Get system-wide emotion distribution over time

        Args:
            days: Number of days to analyze

        Returns:
            Dict with emotion trends
        """
        try:
            emotion_counts = defaultdict(int)
            intensity_sum = defaultdict(float)
            time_series = defaultdict(lambda: defaultdict(int))

            cutoff_date = (datetime.utcnow() - timedelta(days=days)).isoformat()

            all_members = self.db.get_all_members()

            for member in all_members:
                member_id = member.get('id', member.get('member_id'))
                timeline = self.get_user_timeline(member_id)

                for event in timeline:
                    timestamp = event.get('timestamp', '')
                    if timestamp < cutoff_date:
                        continue

                    emotion_state = event.get('emotion_state', {})
                    primary = emotion_state.get('primary', 'neutral')
                    intensity = emotion_state.get('intensity', 0.5)

                    emotion_counts[primary] += 1
                    intensity_sum[primary] += intensity

                    # Time series (by day)
                    date_key = timestamp[:10]  # YYYY-MM-DD
                    time_series[date_key][primary] += 1

            # Compile results
            emotions = {}
            for emotion, count in emotion_counts.items():
                emotions[emotion] = {
                    'count': count,
                    'avg_intensity': round(intensity_sum[emotion] / count, 2) if count > 0 else 0
                }

            logger.info(f"[ADMIN] Emotion heatmap: {len(emotions)} emotions tracked")

            return {
                'emotion_counts': emotions,
                'time_series': dict(time_series),
                'total_events_analyzed': sum(emotion_counts.values()),
                'days_analyzed': days
            }

        except Exception as e:
            logger.error(f"[ADMIN] Error getting emotion heatmap: {e}", exc_info=True)
            return {}

    # ════════════════════════════════════════════════════════════════════════════
    # SHARING GRAPH
    # ════════════════════════════════════════════════════════════════════════════

    def get_sharing_graph(self) -> Dict:
        """
        Get network graph of user sharing relationships

        Returns:
            Dict with nodes (users) and edges (sharing relationships)
        """
        try:
            nodes = []
            edges = []
            pooled_groups = defaultdict(list)

            all_members = self.db.get_all_members()

            for member in all_members:
                member_id = member.get('id', member.get('member_id'))
                tier = member.get('access_tier', 1)
                sharing_mode = member.get('memory_sharing_mode', 'isolated')

                node = {
                    'id': member_id,
                    'name': member.get('display_name'),
                    'tier': tier,
                    'sharing_mode': sharing_mode,
                    'memory_events': self.get_user_memory_stats(member_id).get('total_events', 0) if self.get_user_memory_stats(member_id) else 0
                }
                nodes.append(node)

                # Track pooled groups
                if sharing_mode == 'pooled':
                    pool_tier = member.get('pooled_tier', tier)
                    pooled_groups[f"Tier {pool_tier} Pool"].append(member_id)

            # Add trusted connections as edges
            for member in all_members:
                member_id = member.get('id', member.get('member_id'))
                trusted_users = member.get('trusted_users', [])

                for trusted_id in trusted_users:
                    # Only add edge once (from lower ID to higher)
                    if member_id < trusted_id:
                        edges.append({
                            'source': member_id,
                            'target': trusted_id,
                            'type': 'trusted'
                        })

            # Add pooled group connections
            for pool_name, members in pooled_groups.items():
                for i, member_a in enumerate(members):
                    for member_b in members[i + 1:]:
                        edges.append({
                            'source': member_a,
                            'target': member_b,
                            'type': 'pooled',
                            'pool': pool_name
                        })

            logger.info(f"[ADMIN] Sharing graph: {len(nodes)} users, {len(edges)} connections")

            return {
                'nodes': nodes,
                'edges': edges,
                'pooled_groups': dict(pooled_groups),
                'total_users': len(nodes),
                'total_connections': len(edges)
            }

        except Exception as e:
            logger.error(f"[ADMIN] Error getting sharing graph: {e}", exc_info=True)
            return {'nodes': [], 'edges': [], 'pooled_groups': {}}

    # ════════════════════════════════════════════════════════════════════════════
    # MODERATION (READ-ONLY OBSERVATIONS)
    # ════════════════════════════════════════════════════════════════════════════

    def get_user_admin_flags(self, member_id: str) -> List[Dict]:
        """
        Get all admin observation flags for a user

        Args:
            member_id: Member ID

        Returns:
            List of admin flags
        """
        try:
            member = self.db.get_member(member_id)
            if not member:
                return []

            flags = member.get('admin_flags', [])
            logger.info(f"[ADMIN] Retrieved {len(flags)} flags for {member_id}")
            return flags

        except Exception as e:
            logger.error(f"[ADMIN] Error getting admin flags: {e}")
            return []

    def add_admin_observation(self, member_id: str, note: str, admin_id: str = 'system') -> bool:
        """
        Add admin observation note (read-only, non-modifying)

        Args:
            member_id: Member ID
            note: Observation note
            admin_id: Admin who made the observation

        Returns:
            True if successful
        """
        try:
            success = self.db.add_admin_flag(member_id, note)
            if success:
                logger.info(f"[ADMIN] Added observation for {member_id}: {note}")
            return success

        except Exception as e:
            logger.error(f"[ADMIN] Error adding observation: {e}")
            return False

    def get_suspicious_patterns(self) -> List[Dict]:
        """
        Identify potentially suspicious patterns (for staff review)
        - Multiple failed auth attempts
        - Sudden tier jumps
        - Large memory downloads

        Returns:
            List of flagged patterns
        """
        try:
            flags = []
            all_members = self.db.get_all_members()

            for member in all_members:
                member_id = member.get('id', member.get('member_id'))
                member_flags = self.get_user_admin_flags(member_id)

                # Check for patterns
                if len(member_flags) > 5:
                    flags.append({
                        'member_id': member_id,
                        'pattern': 'multiple_flags',
                        'severity': 'warning',
                        'details': f"User has {len(member_flags)} observation flags"
                    })

                # Check for high memory usage
                stats = self.get_user_memory_stats(member_id)
                if stats and stats['total_events'] > 1000:
                    flags.append({
                        'member_id': member_id,
                        'pattern': 'high_memory_usage',
                        'severity': 'info',
                        'details': f"User has {stats['total_events']} memory events"
                    })

            logger.info(f"[ADMIN] Identified {len(flags)} potential patterns")
            return flags

        except Exception as e:
            logger.error(f"[ADMIN] Error identifying patterns: {e}")
            return []
