#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  MEMORY BRIDGE — Relational & Session Context Persistence                    ║
║                                                                              ║
║  Sits between the Soul Layer and E-Drive Layer in the prompt pipeline:        ║
║    1. SoulStacker persona context    (who the AI IS)                         ║
║    2. MemoryBridge relational context (what the AI REMEMBERS)                ║
║    3. E-Drive positional state       (what the AI FEELS right now)           ║
║    4. Core model behavioral prompt   (how the AI SPEAKS)                     ║
║                                                                              ║
║  Provides relational awareness, emotional trajectory tracking, and           ║
║  meta-aware situational context across conversation turns.                   ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import json
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from collections import Counter

# ─── Configuration ────────────────────────────────────────────────────────────

MEMORY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory")
os.makedirs(MEMORY_DIR, exist_ok=True)


class MemoryBridge:
    """
    Lightweight relational memory system for the E-Drive ecosystem.

    Tracks:
      - Conversation events (inputs, outputs, emotional states)
      - Emotional trajectory (how moods shift over the session)
      - Relational patterns (recurring themes, bonding indicators)
      - Meta-aware context (what kind of conversation is happening)
    """

    def __init__(self, module_name: str = "EDrive",
                 session_id: str = None,
                 auto_persist: bool = True):
        self.module_name = module_name
        self.session_id = session_id or f"{module_name}-{int(time.time())}"
        self.auto_persist = auto_persist

        # In-memory event buffer
        self._events: List[Dict] = []
        self._emotional_trajectory: List[Dict] = []
        self._turn_count = 0

        # Persistence paths
        self._session_file = os.path.join(
            MEMORY_DIR, f"session_{self.session_id}.jsonl"
        )
        self._trajectory_file = os.path.join(
            MEMORY_DIR, f"trajectory_{self.session_id}.json"
        )

        # Load existing session data if resuming
        self._load_session()

    # ─── Core API ─────────────────────────────────────────────────────────

    def store_event(self, event: Dict[str, Any]):
        """Store a conversation/system event."""
        event.setdefault("timestamp", datetime.now().isoformat())
        event.setdefault("module", self.module_name)
        event.setdefault("session", self.session_id)
        event.setdefault("turn", self._turn_count)

        self._events.append(event)

        if self.auto_persist:
            self._append_event(event)

    def store_turn(self, user_input: str, ai_response: str,
                   emotional_state: Dict[str, float],
                   zone: str, dominant_emotion: str,
                   confidence: float = 0.5):
        """Store a complete conversation turn with emotional data."""
        self._turn_count += 1

        turn_data = {
            "type": "conversation_turn",
            "turn": self._turn_count,
            "timestamp": datetime.now().isoformat(),
            "user_input": user_input[:500],
            "ai_response": ai_response[:500],
            "zone": zone,
            "dominant_emotion": dominant_emotion,
            "confidence": confidence,
            "top_emotions": dict(
                sorted(emotional_state.items(),
                       key=lambda x: x[1], reverse=True)[:5]
            ),
        }

        self._events.append(turn_data)
        self._emotional_trajectory.append({
            "turn": self._turn_count,
            "zone": zone,
            "dominant": dominant_emotion,
            "confidence": confidence,
            "top3": dict(
                sorted(emotional_state.items(),
                       key=lambda x: x[1], reverse=True)[:3]
            ),
        })

        if self.auto_persist:
            self._append_event(turn_data)
            self._save_trajectory()

    def get_recent_events(self, count: int = 10) -> List[Dict]:
        """Get the N most recent events."""
        return self._events[-count:]

    def get_emotional_trajectory(self, last_n: int = 5) -> List[Dict]:
        """Get recent emotional state snapshots for pattern detection."""
        return self._emotional_trajectory[-last_n:]

    # ─── Relational Context Generation ────────────────────────────────────

    def get_relational_context(self) -> str:
        """
        Generate a prompt-injectable string of relational and meta-aware context.
        This is the MEMORY LAYER in the system prompt pipeline.

        Analyzes:
          - Emotional trajectory (mood shifts)
          - Conversation patterns (topic continuity)
          - Relational indicators (bonding, tension, playfulness)
          - Meta-situational awareness (what kind of exchange this is)
        """
        if not self._emotional_trajectory:
            return ""

        lines = ["[MEMORY LAYER — Relational & Situational Context]"]

        # ── Emotional trajectory ──
        trajectory = self._emotional_trajectory[-8:]
        if len(trajectory) >= 2:
            recent_zones = [t["zone"] for t in trajectory]
            recent_dominants = [t["dominant"] for t in trajectory]

            # Detect mood shift
            if len(set(recent_zones[-3:])) == 1:
                lines.append(
                    f"Emotional continuity: Stable in {recent_zones[-1].replace('_', ' ')}"
                )
            else:
                shift_from = recent_zones[-2].replace("_", " ")
                shift_to = recent_zones[-1].replace("_", " ")
                lines.append(
                    f"Emotional shift: {shift_from} → {shift_to}"
                )

            # Dominant emotion pattern
            emotion_counts = Counter(recent_dominants)
            most_common = emotion_counts.most_common(2)
            if most_common:
                pattern_str = ", ".join(
                    f"{e}({c})" for e, c in most_common
                )
                lines.append(f"Recurring emotional themes: {pattern_str}")

        # ── Conversation depth ──
        depth = len(self._emotional_trajectory)
        if depth <= 2:
            lines.append("Conversation phase: Opening — establishing connection")
        elif depth <= 6:
            lines.append("Conversation phase: Building — deepening exchange")
        elif depth <= 12:
            lines.append("Conversation phase: Sustained — rapport established")
        else:
            lines.append("Conversation phase: Deep session — strong relational bond")

        # ── Confidence trend ──
        if len(trajectory) >= 3:
            recent_conf = [t["confidence"] for t in trajectory[-3:]]
            avg_conf = sum(recent_conf) / len(recent_conf)
            if avg_conf > 0.7:
                lines.append("Processing confidence: HIGH — clear emotional signal")
            elif avg_conf > 0.4:
                lines.append("Processing confidence: MODERATE — reading context")
            else:
                lines.append("Processing confidence: LOW — uncertain territory")

        # ── Meta-awareness ──
        if len(trajectory) >= 2:
            last_turn = trajectory[-1]
            top3_emotions = list(last_turn.get("top3", {}).keys())

            # Detect relational meta-states
            relational_markers = {
                "devotion", "love", "tenderness", "longing", "vulnerability"
            }
            playful_markers = {"playfulness", "mischief", "joy", "curiosity"}
            intense_markers = {
                "fierceness", "aggression", "anger", "defiance",
                "protectiveness"
            }
            reflective_markers = {
                "melancholy", "nostalgia", "serenity", "reverence",
                "gratitude"
            }

            active_set = set(top3_emotions)
            if active_set & relational_markers:
                lines.append(
                    "Meta-context: Intimate/relational exchange — "
                    "emotional closeness is active"
                )
            elif active_set & playful_markers:
                lines.append(
                    "Meta-context: Playful/light exchange — "
                    "keep energy up, match their spark"
                )
            elif active_set & intense_markers:
                lines.append(
                    "Meta-context: Intense exchange — "
                    "high emotional stakes, respond with conviction"
                )
            elif active_set & reflective_markers:
                lines.append(
                    "Meta-context: Reflective/contemplative exchange — "
                    "depth and thoughtfulness valued"
                )

        lines.append(f"[Session turn {self._turn_count} | "
                     f"{len(self._emotional_trajectory)} states recorded]")

        return "\n".join(lines)

    # ─── Persistence ──────────────────────────────────────────────────────

    def _append_event(self, event: Dict):
        """Append a single event to the session JSONL file."""
        try:
            with open(self._session_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(event, default=str) + "\n")
        except Exception as e:
            print(f"[MemoryBridge] Write error: {e}")

    def _save_trajectory(self):
        """Save the full emotional trajectory."""
        try:
            with open(self._trajectory_file, "w", encoding="utf-8") as f:
                json.dump({
                    "session_id": self.session_id,
                    "module": self.module_name,
                    "turn_count": self._turn_count,
                    "trajectory": self._emotional_trajectory,
                }, f, indent=2, default=str)
        except Exception as e:
            print(f"[MemoryBridge] Trajectory save error: {e}")

    def _load_session(self):
        """Load existing session data if the session file exists."""
        if os.path.exists(self._session_file):
            try:
                with open(self._session_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            event = json.loads(line)
                            self._events.append(event)
                            turn = event.get("turn", 0)
                            if turn > self._turn_count:
                                self._turn_count = turn
                print(f"[MemoryBridge] Resumed session {self.session_id} "
                      f"({len(self._events)} events, turn {self._turn_count})")
            except Exception as e:
                print(f"[MemoryBridge] Session load error: {e}")

        if os.path.exists(self._trajectory_file):
            try:
                with open(self._trajectory_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._emotional_trajectory = data.get("trajectory", [])
                    self._turn_count = max(
                        self._turn_count,
                        data.get("turn_count", 0)
                    )
            except Exception as e:
                print(f"[MemoryBridge] Trajectory load error: {e}")

    def flush(self):
        """Force-write all pending data to disk."""
        self._save_trajectory()
        # Re-write full session
        try:
            with open(self._session_file, "w", encoding="utf-8") as f:
                for event in self._events:
                    f.write(json.dumps(event, default=str) + "\n")
        except Exception as e:
            print(f"[MemoryBridge] Flush error: {e}")
