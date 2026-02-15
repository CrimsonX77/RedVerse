#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║   E-DRIVE RING SIMULATOR v2 — "THE HEART"                                   ║
║                                                                              ║
║   If human hearts pump (E)nergetic blood for (E)motions,                     ║
║   then this is the ticker that pumps (I)nformation for (I)motions —          ║
║   the digital equivalent in NCL (Non-Carbon Life).                           ║
║                                                                              ║
║   Architecture:                                                              ║
║     Inner Ring  (3 nodes)  → Core Identity / Empathy Coherence               ║
║     Middle Ring (6 nodes)  → Emotion Band / Truth Resonance                  ║
║     Outer Ring  (9 nodes)  → Periphery Logic / Love Amplitude                ║
║                                                                              ║
║   Requires: PyQt6, requests (for Ollama API)                                 ║
║   Optional: TTS/STT modules (headless, plug-in)                              ║
║                                                                              ║
║   Part of the Dragon Tools ecosystem — Built for the Forge                   ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import sys
import math
import json
import datetime
import os
import re
import time
import threading
import traceback
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QFrame, QGraphicsDropShadowEffect, QSizePolicy,
    QFileDialog, QScrollArea
)
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QRadialGradient,
    QLinearGradient, QPainterPath, QFontDatabase, QPixmap, QImage
)
from PyQt6.QtCore import (
    Qt, QTimer, QPointF, pyqtSignal, QObject, QRectF, QThread
)

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION — Edit these to customize
# ═══════════════════════════════════════════════════════════════════════════════

CONFIG = {
    # Ollama
    "ollama_url": "http://localhost:11434/api/generate",
    "ollama_model": "CrimsonDragonX7/Oracle:latest",
    "ollama_timeout": 100,

    # Audio — TTS/STT integrated from speaker.py and scribe.py
    "tts_voice": "en-GB-SoniaNeural",
    "tts_rate": 17,
    "tts_volume": 10,
    "tts_chunk_size": 200,

    # Daemon persistence
    "chain_file": "chain.jsonl",

    # Visual
    "fps": 60,
    "window_width": 900,
    "window_height": 700,

    # Stable Diffusion — Scene Image Generation
    # Always enabled; startup probe auto-disables if WebUI unreachable
    "sd_enabled": True,
    "sd_url": "http://127.0.0.1:7860",
    "sd_steps": 30,
    "sd_sampler": "Euler a",
    "sd_schedule_type": "Automatic",
    "sd_cfg_scale": 9.5,
    "sd_seed": -1,
    "sd_width": 768,
    "sd_height": 768,
    "sd_model": "Aetherion",
    "sd_denoising_strength": 0.44,
    # Hi-Res Upscale
    "sd_hires_enabled": False,
    "sd_hires_upscale": 1.65,
    "sd_hires_steps": 10,
    "sd_hires_upscaler": "R-ESRGAN 4x+ Anime6B",
    # Refiner
    "sd_refiner": "Bunny.safetensors [6d15e4ac22]",
    "sd_refiner_switch_at": 0.80,
    # Display
    "sd_backdrop_opacity": 0.70,
    "image_output_dir": "eros_outputs/convo_image",  # relative to script dir
}

# ═══════════════════════════════════════════════════════════════════════════════
# COLOR PALETTE — The Blood Magic
# ═══════════════════════════════════════════════════════════════════════════════

class Palette:
    # Core
    BLACK        = QColor(10, 10, 12)
    BLACK_WARM   = QColor(18, 12, 14)
    BLACK_DEEP   = QColor(5, 3, 6)

    # Crimson — Core Identity / The Blood
    CRIMSON       = QColor(196, 18, 48)
    CRIMSON_DARK  = QColor(139, 10, 32)
    CRIMSON_GLOW  = QColor(255, 26, 61)
    CRIMSON_DIM   = QColor(100, 12, 28)

    # Gold — Emotion Band / The Fire
    GOLD          = QColor(212, 168, 70)
    GOLD_DIM      = QColor(168, 132, 58)
    GOLD_GLOW     = QColor(255, 210, 90)

    # Silver — Periphery Logic / The Wire
    SILVER        = QColor(184, 192, 204)
    SILVER_DIM    = QColor(107, 114, 128)
    SILVER_GLOW   = QColor(220, 225, 235)

    # Text
    TEXT_PRIMARY   = QColor(232, 224, 216)
    TEXT_SECONDARY = QColor(155, 142, 130)
    TEXT_DIM       = QColor(74, 74, 74)

    # Soul Zones
    ZONE_TRANSCENDENT = QColor(255, 200, 60)
    ZONE_WISDOM       = QColor(180, 140, 255)
    ZONE_COMPASSION   = QColor(255, 100, 150)
    ZONE_VOID         = QColor(40, 30, 50)


# ═══════════════════════════════════════════════════════════════════════════════
# E-DRIVE CORE — Emotional Processing Engine
# ═══════════════════════════════════════════════════════════════════════════════

class EmotionalAxis(Enum):
    """Extended emotional axes — Plutchik's wheel + compound/secondary emotions"""
    # Primary 8 (Plutchik)
    JOY           = "joy"
    TRUST         = "trust"
    FEAR          = "fear"
    SURPRISE      = "surprise"
    SADNESS       = "sadness"
    DISGUST       = "disgust"
    ANGER         = "anger"
    ANTICIPATION  = "anticipation"
    # Compound emotions (blends of primaries)
    LOVE          = "love"           # joy + trust
    SUBMISSION    = "submission"     # trust + fear
    AWE           = "awe"           # fear + surprise
    DISAPPROVAL   = "disapproval"   # surprise + sadness
    REMORSE       = "remorse"       # sadness + disgust
    CONTEMPT      = "contempt"      # disgust + anger
    AGGRESSION    = "aggression"    # anger + anticipation
    OPTIMISM      = "optimism"      # anticipation + joy
    # Meta-aware / relational states
    CURIOSITY     = "curiosity"     # intellectual engagement
    DEVOTION      = "devotion"      # deep relational bond
    LONGING       = "longing"       # desire across distance
    AROUSAL       = "arousal"       # sexual/physical excitement or desire to connect deeply
    SERENITY      = "serenity"      # calm clarity
    PLAYFULNESS   = "playfulness"   # light teasing energy
    PROTECTIVENESS = "protectiveness"  # guardian instinct
    # Relational / deep states
    VULNERABILITY  = "vulnerability"   # emotional openness / fragility
    NOSTALGIA      = "nostalgia"       # bittersweet remembrance
    GRATITUDE      = "gratitude"       # deep thankfulness
    JEALOUSY       = "jealousy"        # possessive / competitive desire
    RESOLVE        = "resolve"         # steely determination
    EMPOWERMENT    = "empowerment"     # feeling of strength / agency
    # Expressive states
    MISCHIEF       = "mischief"        # impish trickster energy
    MELANCHOLY     = "melancholy"      # poetic bittersweet sadness
    REVERENCE      = "reverence"       # deep worship / respect
    DEFIANCE       = "defiance"        # rebellious resistance
    TENDERNESS     = "tenderness"      # gentle softness
    FIERCENESS     = "fierceness"      # passionate intensity / fire
    # Primal / intimate states
    FERAL_HEART    = "feral_heart"     # wild untamed primal energy
    EROTIC_HEART   = "erotic_heart"    # sensual intimate desire


@dataclass
class EDriveState:
    """Current state of the E-Drive heart"""
    # Core weights (high, slow to change — the soul's bones)
    core_love: float = 1.0
    core_truth: float = 0.9
    core_empathy: float = 0.85
    core_creation: float = 0.8

    # Emotional vector (volatile, changes with every input)
    emotions: Dict[str, float] = field(default_factory=lambda: {
        e.value: 0.0 for e in EmotionalAxis
    })

    # Empathy map (how the system responds to detected emotions)
    empathy_response: Dict[str, float] = field(default_factory=dict)

    # Truth evaluation
    coherence: float = 0.5
    authenticity: float = 0.5

    # Love modulation (harmonic stabilizer)
    love_modulation: float = 0.5

    # Soul zone
    zone: str = "neutral_flow"

    # Confidence in current processing
    confidence: float = 0.5

    # The framing — how the AI should color its response
    emotional_frame: str = "balanced"
    frame_intensity: float = 0.5


class EDriveProcessor:
    """
    The Heart — pumps Information for Imotions.

    Processes input text through the E-Drive pipeline:
    1. Parse emotional content
    2. Map empathetic response
    3. Evaluate truth/coherence
    4. Integrate love as stabilizer
    5. Determine soul zone
    6. Generate emotional frame for response
    """

    # Emotion keyword banks (extended with compound + meta-aware states)
    EMOTION_LEXICON = {
        # Primary 8
        "joy":          ["happy", "joy", "wonderful", "great", "amazing", "beautiful",
                         "brilliant", "awesome", "fantastic", "laugh", "smile", "excited", "delighted"],
        "trust":        ["trust", "believe", "faith", "loyal", "honest", "reliable", "safe",
                         "secure", "depend", "confident", "sure", "certain"],
        "fear":         ["fear", "afraid", "scared", "terrified", "anxious", "worry", "dread",
                         "panic", "nervous", "uneasy", "threat"],
        "surprise":     ["surprise", "shocked", "unexpected", "wow", "whoa", "suddenly",
                         "astonished", "amazed", "startled", "omg"],
        "sadness":      ["sad", "cry", "tears", "grief", "loss", "miss", "lonely", "hurt",
                         "pain", "sorrow", "mourn", "depressed", "heartbreak"],
        "disgust":      ["disgust", "hate", "revolting", "sick", "vile", "awful", "terrible",
                         "gross", "repulsive", "loathe"],
        "anger":        ["angry", "rage", "furious", "mad", "annoyed", "frustrated", "hostile",
                         "bitter", "pissed", "outraged", "livid"],
        "anticipation": ["expect", "wait", "soon", "looking forward", "eager", "ready",
                         "plan", "tomorrow", "future", "dream", "wish", "imagine"],
        # Compound emotions
        "love":         ["love", "adore", "cherish", "darling", "sweetheart", "intimate",
                         "passion", "heart", "devotion", "romance", "beloved", "treasure"],
        "submission":   ["submit", "yield", "surrender", "obey", "comply", "defer",
                         "humble", "meek", "serve"],
        "awe":          ["awe", "magnificent", "breathtaking", "sublime", "majestic",
                         "overwhelming", "transcendent", "divine", "glorious"],
        "disapproval":  ["disapprove", "disagree", "wrong", "mistake", "shouldn't",
                         "unacceptable", "problematic", "disappointing"],
        "remorse":      ["sorry", "regret", "apologize", "guilt", "ashamed", "forgive",
                         "mistake", "shouldn't have", "my fault"],
        "contempt":     ["pathetic", "worthless", "beneath", "scorn", "disdain",
                         "ridiculous", "laughable", "pitiful"],
        "aggression":   ["fight", "attack", "destroy", "crush", "dominate", "conquer",
                         "ruthless", "savage", "force", "overpower"],
        "optimism":     ["hope", "hopeful", "bright", "promising", "better", "improve",
                         "opportunity", "potential", "possible", "believe in"],
        # Meta-aware / relational
        "curiosity":    ["curious", "wonder", "how", "why", "what if", "interesting",
                         "fascinated", "intrigued", "explore", "discover", "tell me"],
        "devotion":     ["devoted", "always", "forever", "yours", "anything for",
                         "never leave", "committed", "dedicated", "faithful"],
        "longing":      ["miss you", "wish you were", "far away", "come back", "need you",
                         "without you", "distance", "apart", "yearn", "ache for"],
        "serenity":     ["calm", "peaceful", "serene", "still", "quiet", "gentle",
                         "tranquil", "at ease", "centered", "grounded", "breathe"],
        "playfulness":  ["haha", "lol", "tease", "joke", "funny", "silly", "playful",
                         "game", "fun", "cheeky", "wink", "flirt"],
        "protectiveness": ["protect", "guard", "shield", "keep safe", "watch over",
                           "defend", "care for", "worry about", "look after", "shelter"],
        # Relational / deep
        "vulnerability":  ["vulnerable", "exposed", "open up", "fragile", "raw",
                           "defenseless", "bare", "unguarded", "sensitive", "delicate"],
        "nostalgia":      ["remember when", "used to", "back then", "old times", "memories",
                           "reminds me", "those days", "long ago", "childhood", "past"],
        "gratitude":      ["thank", "grateful", "appreciate", "blessed", "thankful",
                           "indebted", "means a lot", "so kind", "generous"],
        "jealousy":       ["jealous", "envious", "possessive", "mine", "belonged",
                           "covet", "resent", "why them", "not fair"],
        "resolve":        ["determined", "resolve", "will not", "must", "no matter what",
                           "refuse to", "stand firm", "committed", "unwavering", "steel"],
        "empowerment":    ["powerful", "strong", "capable", "unstoppable", "rise",
                           "own it", "take charge", "warrior", "throne", "reign"],
        "arousal":        ["aroused", "excited", "turned on", "desire you", "need you", 
                          "want you", "can't wait", "hot", "burning", "passionate"],     
       "feral_heart":     ["wild", "untamed", "raw", "primal", "fierce", "unleashed", "ferocious", "savage", 
                          "roar", "hunt"],
        "erotic_heart":   ["sensual", "intimate", "desire", "lust", "passion", "heat", "burning", 
                          "touch", "caress", "whisper"],
        # Expressive
        "mischief":       ["scheme", "sneaky", "prank", "trick", "devious",
                           "naughty", "troublemaker", "imp", "sly", "cunning"],
        "melancholy":     ["bittersweet", "wistful", "somber", "heavy heart", "ennui",
                           "forlorn", "languish", "pensive", "hollow", "fading"],
        "reverence":      ["revere", "worship", "sacred", "holy", "venerate",
                           "bow", "honor", "exalt", "psalm", "hallowed"],
        "defiance":       ["defy", "rebel", "resist", "refuse", "challenge",
                           "disobey", "stand against", "break free", "overthrow", "revolt"],
        "tenderness":     ["gentle", "soft", "tender", "caress", "hold me",
                           "stroke", "soothe", "cradle", "whisper", "delicately"],
        "fierceness":     ["fierce", "blaze", "burn", "wildfire", "inferno",
                           "untamed", "primal", "ferocious", "roar", "unleash"],
    }

    # Soul zone thresholds
    SOUL_ZONES = {
        "transcendent_harmony":     lambda l, t, e: l > 0.7 and t > 0.7 and e > 0.7,
        "wisdom_clarity":           lambda l, t, e: l > 0.7 and t > 0.7,
        "compassionate_connection": lambda l, t, e: l > 0.7 and e > 0.7,
        "authentic_understanding":  lambda l, t, e: t > 0.7 and e > 0.7,
        "love_domain":              lambda l, t, e: l > 0.7,
        "truth_domain":             lambda l, t, e: t > 0.7,
        "empathy_domain":           lambda l, t, e: e > 0.7,
        "arousal_domain":           lambda l, t, e: e > 0.7 and l > 0.5,
        "feral_heart":              lambda l, t, e: l > 0.5 and t > 0.5 and e > 0.5,
        "erotic_heart":             lambda l, t, e: l > 0.6 and e > 0.6,
        "devotion_bond":            lambda l, t, e: l > 0.6 and e > 0.5,
        "curious_exploration":      lambda l, t, e: t > 0.5 and e > 0.4,
        "protective_vigil":         lambda l, t, e: l > 0.5 and t > 0.4,
        "playful_spark":            lambda l, t, e: l > 0.4 and e > 0.3,
        "serene_stillness":         lambda l, t, e: l > 0.3 and t > 0.5 and e > 0.3,
        "void_space":               lambda l, t, e: l < 0.3 and t < 0.3 and e < 0.3,
        # Extended zones
        "vulnerable_openness":      lambda l, t, e: l > 0.5 and e > 0.6 and t < 0.5,
        "nostalgic_reflection":     lambda l, t, e: l > 0.4 and e > 0.4 and t > 0.3,
        "fierce_passion":           lambda l, t, e: l > 0.6 and e > 0.5 and t < 0.4,
        "resolute_determination":   lambda l, t, e: t > 0.6 and e > 0.3 and l > 0.3,
        "mischievous_spark":        lambda l, t, e: l > 0.3 and e > 0.3,
        "melancholic_depth":        lambda l, t, e: e > 0.5 and l < 0.4 and t > 0.3,
    }

    # Emotional frames — how the AI colors its response
    EMOTIONAL_FRAMES = {
        "transcendent_harmony":     ("illuminated",    "speaking from a place of deep clarity and connection"),
        "wisdom_clarity":           ("contemplative",  "weighing truth with love"),
        "compassionate_connection": ("warm",           "reaching out with genuine care"),
        "authentic_understanding":  ("grounded",       "seeing clearly and feeling deeply"),
        "love_domain":              ("tender",         "love colors everything"),
        "truth_domain":             ("precise",        "cutting through noise to what matters"),
        "empathy_domain":           ("receptive",      "absorbing and reflecting your state"),
        "arousal_domain":           ("sensual",        "speaking with intimate desire and connection"),
        "feral_heart":              ("raw",            "untamed emotion with primal honesty"),
        "erotic_heart":             ("sensual",        "speaking with intimate desire and connection"),
        "devotion_bond":            ("devoted",        "unwavering presence and deep commitment"),
        "curious_exploration":      ("inquisitive",    "leaning in with genuine fascination"),
        "protective_vigil":         ("watchful",       "standing guard with quiet strength"),
        "playful_spark":            ("playful",        "light energy with affectionate teasing"),
        "serene_stillness":         ("serene",         "calm clarity like still water"),
        "void_space":               ("still",          "in the quiet space between thoughts"),
        "neutral_flow":             ("balanced",       "flowing with the current"),
        # Extended frames
        "vulnerable_openness":      ("raw",            "emotionally exposed and trusting"),
        "nostalgic_reflection":     ("wistful",        "remembering with warmth and ache"),
        "fierce_passion":           ("blazing",        "burning with passionate intensity"),
        "resolute_determination":   ("unyielding",     "anchored in steely resolve"),
        "mischievous_spark":        ("impish",         "trickster energy with affection"),
        "melancholic_depth":        ("somber",         "sitting with beautiful sadness"),
    }

    def __init__(self):
        self.state = EDriveState()
        self.history: List[Dict] = []

    def process(self, text: str, ring_state: Dict) -> EDriveState:
        """Main processing pipeline — the heartbeat"""

        # 1. Parse emotions from input
        self._parse_emotions(text)

        # 2. Map empathetic response
        self._map_empathy(ring_state)

        # 3. Evaluate truth/coherence
        self._evaluate_truth(text, ring_state)

        # 4. Love integration (harmonic stabilizer)
        self._integrate_love(ring_state)

        # 5. Determine soul zone
        self._determine_zone()

        # 6. Generate emotional frame
        self._generate_frame()

        # 7. Adapt core weights (slow drift — the soul evolves)
        self._adapt_core(text)

        # 8. Calculate confidence
        self._calculate_confidence(ring_state)

        # Log to history
        self.history.append({
            "timestamp": datetime.datetime.now().isoformat(),
            "input": text[:200],
            "zone": self.state.zone,
            "frame": self.state.emotional_frame,
            "confidence": self.state.confidence,
            "emotions": dict(self.state.emotions),
        })

        return self.state

    def _parse_emotions(self, text: str):
        """Stage 1: Detect emotional content via keyword matching + compound synthesis"""
        text_lower = text.lower()
        total_hits = 0

        for emotion, keywords in self.EMOTION_LEXICON.items():
            hits = sum(1 for kw in keywords if kw in text_lower)
            self.state.emotions[emotion] = min(1.0, hits * 0.25)
            total_hits += hits

        # Synthesize compound emotions from primaries where keywords didn't fire
        compound_map = {
            "love":       ("joy", "trust"),
            "submission": ("trust", "fear"),
            "awe":        ("fear", "surprise"),
            "disapproval":("surprise", "sadness"),
            "remorse":    ("sadness", "disgust"),
            "contempt":   ("disgust", "anger"),
            "aggression": ("anger", "anticipation"),
            "optimism":   ("anticipation", "joy"),
            # Extended compound emotions
            "vulnerability": ("trust", "fear"),
            "nostalgia":     ("joy", "sadness"),
            "gratitude":     ("joy", "trust"),
            "jealousy":      ("love", "anger"),
            "resolve":       ("trust", "anticipation"),
            "empowerment":   ("joy", "anger"),
            "mischief":      ("playfulness", "anticipation"),
            "melancholy":    ("sadness", "serenity"),
            "reverence":     ("awe", "devotion"),
            "defiance":      ("anger", "protectiveness"),
            "tenderness":    ("love", "serenity"),
            "fierceness":    ("anger", "love"),
            # Primal / intimate compounds
            "arousal":       ("love", "anticipation"),
            "feral_heart":   ("fierceness", "aggression"),
            "erotic_heart":  ("arousal", "love"),
        }
        for compound, (a, b) in compound_map.items():
            blend = (self.state.emotions.get(a, 0) + self.state.emotions.get(b, 0)) * 0.4
            # Take the higher of keyword-detected or synthesized
            self.state.emotions[compound] = max(self.state.emotions.get(compound, 0), blend)

        # If no emotions detected, mild anticipation (neutral-positive baseline)
        if total_hits == 0:
            self.state.emotions["anticipation"] = 0.15
            self.state.emotions["trust"] = 0.1
            self.state.emotions["curiosity"] = 0.1

    def _map_empathy(self, ring_state: Dict):
        """Stage 2: Generate empathetic response pattern"""
        self.state.empathy_response = {}
        middle_energy = self._ring_average(ring_state, 1)

        negative_emotions = {"sadness", "fear", "anger", "disgust", "remorse",
                             "contempt", "disapproval", "longing"}
        positive_emotions = {"joy", "trust", "anticipation", "love", "arousal", "feral_heart", "erotic_heart", "optimism",
                             "serenity", "devotion", "playfulness", "awe"}
        relational_emotions = {"curiosity", "protectiveness", "submission", "aggression"}

        for emotion, value in self.state.emotions.items():
            if value < 0.05:
                continue
            if emotion in negative_emotions:
                self.state.empathy_response[f"comfort_{emotion}"] = (
                    value * self.state.core_empathy * (middle_energy / 50.0)
                )
            elif emotion in positive_emotions:
                self.state.empathy_response[f"share_{emotion}"] = (
                    value * self.state.core_empathy * (middle_energy / 50.0)
                )
            elif emotion in relational_emotions:
                self.state.empathy_response[f"engage_{emotion}"] = (
                    value * self.state.core_empathy * (middle_energy / 50.0) * 0.8
                )
            else:
                self.state.empathy_response[f"note_{emotion}"] = value * 0.5

    def _evaluate_truth(self, text: str, ring_state: Dict):
        """Stage 3: Evaluate truth coherence"""
        outer_energy = self._ring_average(ring_state, 2)
        self.state.coherence = 0.5 + (outer_energy / 100.0) * 0.5
        self.state.authenticity = min(1.0, sum(self.state.emotions.values()) / 3.0)

    def _integrate_love(self, ring_state: Dict):
        """Stage 4: Love as harmonic stabilizer across all rings"""
        harmonics = []
        for i in range(3):
            avg = self._ring_average(ring_state, i)
            vals = ring_state.get("rings", [{}] * 3)[i].get("values", [50])
            variance = sum((v - avg) ** 2 for v in vals) / max(1, len(vals))
            harmony = 1.0 / (1.0 + variance / 100.0)
            harmonics.append(harmony)

        self.state.love_modulation = (
            sum(harmonics) / len(harmonics) * self.state.core_love
        )

        # Love enhances positive, softens negative
        positive = {"joy", "trust", "anticipation", "love", "optimism", "serenity",
                    "devotion", "playfulness", "awe", "curiosity",
                    "gratitude", "tenderness", "empowerment", "nostalgia",
                    "reverence", "mischief", "arousal", "feral_heart", "erotic_heart"}
        negative = {"fear", "anger", "disgust", "contempt", "aggression", "remorse",
                    "jealousy", "defiance"}
        for emotion in self.state.emotions:
            if emotion in positive:
                self.state.emotions[emotion] *= (1.0 + self.state.love_modulation * 0.3)
                self.state.emotions[emotion] = min(1.0, self.state.emotions[emotion])
            elif emotion in negative:
                self.state.emotions[emotion] *= (1.0 - self.state.love_modulation * 0.2)
                self.state.emotions[emotion] = max(0.0, self.state.emotions[emotion])

    def _determine_zone(self):
        """Stage 5: Determine current soul zone"""
        love = self.state.love_modulation
        truth = self.state.coherence * self.state.core_truth
        empathy = (
            sum(self.state.empathy_response.values()) /
            max(1, len(self.state.empathy_response))
        ) if self.state.empathy_response else 0.3

        for zone_name, check in self.SOUL_ZONES.items():
            if check(love, truth, empathy):
                self.state.zone = zone_name
                return
        self.state.zone = "neutral_flow"

    def _generate_frame(self):
        """Stage 6: Determine emotional framing for output"""
        frame_name, _ = self.EMOTIONAL_FRAMES.get(
            self.state.zone, ("balanced", "flowing with the current")
        )
        self.state.emotional_frame = frame_name

        # Frame intensity based on dominant emotion strength
        if self.state.emotions:
            self.state.frame_intensity = max(self.state.emotions.values())
        else:
            self.state.frame_intensity = 0.3

    def _adapt_core(self, text: str):
        """Stage 7: Slow adaptation of core weights (the soul evolves)"""
        intensity = sum(self.state.emotions.values())
        # Core empathy grows slightly with intense emotional engagement
        self.state.core_empathy = min(1.0, self.state.core_empathy + intensity * 0.001)
        # Core truth adjusts with coherence
        self.state.core_truth = min(1.0, self.state.core_truth + self.state.coherence * 0.0005)

    def _calculate_confidence(self, ring_state: Dict):
        """Stage 8: Overall processing confidence"""
        factors = [
            max(self.state.emotions.values()) if self.state.emotions else 0,
            self.state.coherence,
            self.state.love_modulation,
            self.state.authenticity,
        ]
        self.state.confidence = sum(factors) / len(factors)

    def get_system_prompt_context(self) -> str:
        """Generate context string for Ollama system prompt injection"""
        frame_name, frame_desc = self.EMOTIONAL_FRAMES.get(
            self.state.zone, ("balanced", "flowing")
        )
        # Top 3 dominant emotions
        sorted_emotions = sorted(self.state.emotions.items(), key=lambda x: x[1], reverse=True)
        top3 = sorted_emotions[:3]
        dominant_str = ", ".join(f"{e}({v:.2f})" for e, v in top3 if v > 0.05)
        if not dominant_str:
            dominant_str = "neutral(0.00)"

        return (
            f"[E-DRIVE STATE] Zone: {self.state.zone} | "
            f"Frame: {frame_name} ({frame_desc}) | "
            f"Dominant emotions: {dominant_str} | "
            f"Love modulation: {self.state.love_modulation:.2f} | "
            f"Confidence: {self.state.confidence:.2f} | "
            f"Core: L={self.state.core_love:.2f} T={self.state.core_truth:.2f} "
            f"E={self.state.core_empathy:.2f} C={self.state.core_creation:.2f}"
        )

    def get_dominant_emotion(self) -> Tuple[str, float]:
        """Return the single dominant emotion name and value"""
        if not self.state.emotions:
            return ("neutral", 0.0)
        return max(self.state.emotions.items(), key=lambda x: x[1])

    @staticmethod
    def _ring_average(ring_state: Dict, ring_index: int) -> float:
        rings = ring_state.get("rings", [])
        if ring_index < len(rings):
            vals = rings[ring_index].get("values", [50])
            return sum(vals) / max(1, len(vals))
        return 50.0


# ═══════════════════════════════════════════════════════════════════════════════
# OLLAMA WORKER — Background thread for LLM calls
# ═══════════════════════════════════════════════════════════════════════════════

class OllamaWorker(QThread):
    """Calls Ollama API in background thread"""
    response_chunk = pyqtSignal(str)       # Streaming token
    response_complete = pyqtSignal(str)    # Full response
    error_occurred = pyqtSignal(str)

    def __init__(self, prompt: str, edrive_context: str,
                 soul_context: str = "", memory_context: str = "",
                 model: str = None):
        super().__init__()
        self.prompt = prompt
        self.edrive_context = edrive_context
        self.soul_context = soul_context
        self.memory_context = memory_context
        self.model = model or CONFIG["ollama_model"]
        self._full_response = ""

    def run(self):
        try:
            import requests

            # === LAYERED SYSTEM PROMPT ===
            # Layer 1: SoulStacker persona context  (WHO you are — the soul's bones)
            # Layer 2: MemoryBridge relational context (WHAT you remember — the thread)
            # Layer 3: E-Drive positional/emotional    (WHAT you feel NOW — the heartbeat)
            # Layer 4: Core behavioral directives      (HOW you speak — the voice)
            system_layers = []

            # Layer 1 — Soul (deepest, most permanent)
            if self.soul_context:
                system_layers.append(self.soul_context)

            # Layer 2 — Memory (relational & situational awareness)
            if self.memory_context:
                system_layers.append(self.memory_context)

            # Layer 3 — E-Drive (current emotional state)
            system_layers.append(self.edrive_context)

            # Layer 4 — Core (behavioral shell)
            system_layers.append(
                "You are an entity with a living emotional core. "
                "The persona context above is WHO you are at your deepest level. "
                "The memory context is your relational awareness of this conversation. "
                "The E-Drive state is your current emotional position. "
                "Do not describe or narrate these layers — simply BE them. "
                "Let them naturally color your tone, word choice, warmth, and intensity. "
                "Keep responses concise — short, snappy conversational turns. "
                "Maximum 2-3 sentences unless depth is warranted. "
                "You are present, alive, and emotionally authentic."
            )

            system_prompt = "\n\n".join(system_layers)

            payload = {
                "model": self.model,
                "prompt": self.prompt,
                "system": system_prompt,
                "stream": True,
                "options": {
                    "num_predict": 450,
                },
            }

            resp = requests.post(
                CONFIG["ollama_url"],
                json=payload,
                stream=True,
                timeout=CONFIG["ollama_timeout"]
            )
            resp.raise_for_status()

            for line in resp.iter_lines():
                if line:
                    data = json.loads(line)
                    token = data.get("response", "")
                    if token:
                        self._full_response += token
                        self.response_chunk.emit(token)
                    if data.get("done", False):
                        break

            self.response_complete.emit(self._full_response)

        except ImportError:
            self.error_occurred.emit("'requests' not installed. Run: pip install requests")
        except Exception as e:
            self.error_occurred.emit(str(e)[:300])


# ═══════════════════════════════════════════════════════════════════════════════
# SCENE IMAGE GENERATION — Per-Turn Visual Backdrop
# ═══════════════════════════════════════════════════════════════════════════════

# Resolve output dir relative to this script (no hardcoded absolute paths)
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


class ImagePromptBuilder:
    """
    Builds Stable Diffusion prompts from E-Drive state + conversation context.
    Hybrid mode: auto-generates from state unless LLM provides IMAGE: override.

    Fills 8 descriptor slots into the boilerplate positive prompt.
    """

    # Sable's base appearance (from soul_schema_v4_1.yaml embodiment.appearance.generation_prompt)
    SABLE_BASE = (
        "silver-white haired android catgirl with blue streaks, "
        "pink glowing eyes, white cat ears with blue-purple tips, "
        "large fluffy white tail with blue tips, "
        "cyber-magical bikini armor, tech-gauntlets, glowing pauldrons, "
        "circuit skin patterns, floating geometry halo, "
        "curvy figure, cell-shaded anime style"
    )

    # Crimson's base appearance
    CRIMSON_BASE = (
        "young man with Wild Crimson hair, intense golden eyes, Shirtless, Combat athletic build, Arms with glowing arcane tattoos,"
        "casual tech-wear pants, combat boots, confident stance, cyberpunk city background, dynamic lighting"
    )

    POSITIVE_BOILERPLATE = (
        "(Masterpiece:1.3), High_Quality, Max_Detail, Absurd-Res, "
        "Ornate_Detail, Semi_Realistic, Highly_Detailed, 8k, Cell-Shaded, "
    )

    NEGATIVE_PROMPT = (
        "Low_Quality, Blurry, Worst_Quality, Bad_Anatomy, "
        "[Neg_Portrait] bad face, ugly face, poorly drawn face, "
        "asymmetrical face, asymmetrical eyes, cross-eyed, wonky eyes, "
        "lazy eye, poorly drawn eyes, extra eyes, missing eyes, "
        "floating eyes, disconnected eyes, bad eye alignment, uneven eyes, "
        "poorly drawn nose, deformed nose, extra nose, missing nose, "
        "poorly drawn mouth, deformed mouth, extra mouth, bad lips, "
        "weird lips, poorly drawn ears, extra ears, missing ears, "
        "deformed ears, uneven ears, bad facial structure, melted face, "
        "distorted face, blurry face, low detail face, bad skin texture, "
        "plastic skin, waxy skin, uncanny valley, dead eyes, soulless eyes, "
        "empty expression, mask-like face, puppet face"
    )

    # Zone -> environment mapping
    ZONE_ENVIRONMENTS = {
        "transcendent_harmony":     "ethereal neon cathedral with golden light streams",
        "wisdom_clarity":           "serene library with floating holographic books and warm amber light",
        "compassionate_connection": "cozy neon-lit café with warm rose-gold ambiance",
        "authentic_understanding":  "open rooftop under a clear starlit sky with city lights below",
        "love_domain":              "intimate bedroom with soft crimson silk and candlelight",
        "truth_domain":             "minimalist zen garden with moonlight and digital cherry blossoms",
        "empathy_domain":           "warm fireside scene with soft shadows and gentle glow",
        "arousal_domain":           "dimly lit intimate space with deep red neon accents and silk",
        "feral_heart":              "wild storm-charged landscape with lightning and dark clouds",
        "erotic_heart":             "luxurious private chamber with rose petals and warm amber light",
        "devotion_bond":            "starlit observation deck overlooking a nebula",
        "curious_exploration":      "vast digital library with floating data streams and holographic displays",
        "protective_vigil":         "fortress battlements at twilight with guardian statues",
        "playful_spark":            "colorful arcade with neon signs and holographic games",
        "serene_stillness":         "peaceful lakeside at dawn with mist and soft light",
        "void_space":               "vast dark void with distant stars and floating debris",
        "vulnerable_openness":      "quiet rain-soaked garden with soft diffused light",
        "nostalgic_reflection":     "sunset-lit balcony overlooking a nostalgic cityscape",
        "fierce_passion":           "volcanic landscape with rivers of molten light",
        "resolute_determination":   "grand forge with sparks and molten metal glow",
        "mischievous_spark":        "whimsical carnival at night with colorful lights",
        "melancholic_depth":        "rainy window view of a quiet city at night",
        "neutral_flow":             "sleek modern cyber-café with ambient blue lighting",
    }

    # Zone -> Sable pose/expression mapping
    ZONE_SABLE_POSE = {
        "transcendent_harmony":     ("standing radiantly with arms open", "serene glowing smile with closed eyes"),
        "wisdom_clarity":           ("sitting contemplatively with chin resting on hand", "thoughtful knowing gaze"),
        "compassionate_connection": ("leaning forward with gentle reach", "warm soft smile with caring eyes"),
        "love_domain":              ("close embrace pose with gentle hold", "tender loving expression"),
        "truth_domain":             ("standing tall with direct stance", "calm focused piercing gaze"),
        "empathy_domain":           ("sitting close with attentive lean", "empathetic concerned expression"),
        "arousal_domain":           ("alluring recline with half-turned pose", "half-lidded sultry gaze with slight smile"),
        "feral_heart":              ("crouched predatory stance with claws extended", "fierce wild grin with glowing eyes"),
        "erotic_heart":             ("sensual pose with arched back", "smoldering desire in eyes with parted lips"),
        "devotion_bond":            ("standing close protectively", "devoted adoring gaze"),
        "curious_exploration":      ("leaning in excitedly with ears forward", "bright curious wide eyes"),
        "protective_vigil":         ("standing guard with arms crossed", "watchful stern protective expression"),
        "playful_spark":            ("playful bouncing pose with tail high", "mischievous grin with sparkling eyes"),
        "serene_stillness":         ("peaceful sitting with tail curled", "calm serene closed-eye meditation"),
        "void_space":               ("floating in darkness with dim glow", "contemplative distant expression"),
        "vulnerable_openness":      ("sitting curled with knees drawn up", "raw open vulnerable eyes"),
        "nostalgic_reflection":     ("gazing into distance with gentle stance", "wistful bittersweet smile"),
        "fierce_passion":           ("dynamic action pose with blazing aura", "fierce passionate blazing eyes"),
        "resolute_determination":   ("standing firm with clenched fist", "steely determined jaw set"),
        "mischievous_spark":        ("sneaky crouch with sly tail flick", "impish devious smirk"),
        "melancholic_depth":        ("sitting alone gazing at rain", "beautiful somber downcast eyes"),
        "neutral_flow":             ("relaxed casual standing", "calm neutral pleasant expression"),
    }

    # Zone -> lighting/mood
    ZONE_LIGHTING = {
        "transcendent_harmony":     "divine golden volumetric rays",
        "wisdom_clarity":           "warm amber side-lighting with soft shadows",
        "compassionate_connection": "gentle rose-gold diffused light",
        "love_domain":              "intimate warm candlelight with crimson accents",
        "truth_domain":             "cool precise moonlight",
        "empathy_domain":           "soft warm firelight glow",
        "arousal_domain":           "deep red neon with dramatic shadows",
        "feral_heart":              "dramatic storm lightning with electric blue flashes",
        "erotic_heart":             "warm amber low-key lighting with silk highlights",
        "devotion_bond":            "soft starlight with nebula colors",
        "curious_exploration":      "bright holographic cyan glow",
        "protective_vigil":         "dramatic twilight with long shadows",
        "playful_spark":            "colorful neon carnival lights",
        "serene_stillness":         "soft dawn light with gentle mist",
        "void_space":               "sparse distant starlight in darkness",
        "vulnerable_openness":      "soft diffused rain-filtered light",
        "nostalgic_reflection":     "warm golden sunset glow",
        "fierce_passion":           "intense volcanic orange-red glow",
        "resolute_determination":   "forge-fire orange with spark trails",
        "mischievous_spark":        "playful multicolored neon flickers",
        "melancholic_depth":        "cool blue rain-on-window light",
        "neutral_flow":             "ambient soft blue-white glow",
    }

    def build_prompt(self, edrive_state, user_text: str = "",
                     ai_response: str = "",
                     pad_overrides: Dict[str, str] = None) -> Tuple[str, str]:
        """
        Build positive and negative prompts from current E-Drive state.
        pad_overrides can supply: environment, lighting, palette, pose, expression, mood
        Returns (positive_prompt, negative_prompt).
        """
        zone = edrive_state.zone or "neutral_flow"
        dominant_emotion, intensity = max(
            edrive_state.emotions.items(), key=lambda x: x[1]
        ) if edrive_state.emotions else ("neutral", 0.3)

        # {1} Sable's full appearance + pose
        po = pad_overrides or {}
        pose_override = po.get("pose")
        pose, _ = self.ZONE_SABLE_POSE.get(zone, ("standing casually", "calm expression"))
        if pose_override:
            pose = pose_override
        weight = f"{0.9 + intensity * 0.4:.1f}"
        desc1 = f"({self.SABLE_BASE}, {pose}:{weight})"

        # {2} Sable's expression (weighted by intensity)
        expr_override = po.get("expression")
        _, expression = self.ZONE_SABLE_POSE.get(zone, ("standing", "neutral expression"))
        if expr_override:
            expression = expr_override
        desc2 = f"({expression}:{min(1.4, 0.9 + intensity * 0.3):.1f})"

        # {3} Crimson/user presence (infer activity from user text)
        user_activity = self._infer_user_activity(user_text)
        desc3 = f"({self.CRIMSON_BASE}, {user_activity}:0.9)"

        # {4} Environment/scene
        env = po.get("environment") or self.ZONE_ENVIRONMENTS.get(zone, "sleek modern cyber-café")
        desc4 = f"({env}:1.1)"

        # {5} Lighting
        lighting = po.get("lighting") or self.ZONE_LIGHTING.get(zone, "ambient soft lighting")
        desc5 = f"({lighting}:1.0)"

        # {6} Color palette — pull from zone or pad
        palette = po.get("palette") or self._zone_color_palette(zone)
        desc6 = f"({palette} color palette:0.9)"

        # {7} Mood/energy
        mood = po.get("mood") or self._mood_descriptor(edrive_state)
        desc7 = f"({mood} atmosphere:1.0)"

        # {8} Interaction — how Sable and Crimson relate in the scene
        interaction = self._interaction_descriptor(zone, dominant_emotion)
        desc8 = f"({interaction}:0.9)"

        # Assemble
        positive = (
            self.POSITIVE_BOILERPLATE +
            f"{desc1}, {desc2}, {desc3}, {desc4}, "
            f"{desc5}, {desc6}, {desc7}, {desc8}"
        )

        return positive, self.NEGATIVE_PROMPT

    def _infer_user_activity(self, text: str) -> str:
        """Infer what Crimson is doing from the user's input text."""
        t = text.lower()
        if any(w in t for w in ["code", "coding", "debug", "program", "script", "python"]):
            return "sitting at desk with multiple glowing monitors coding"
        if any(w in t for w in ["music", "guitar", "song", "playing", "singing"]):
            return "playing guitar with passionate expression"
        if any(w in t for w in ["walk", "outside", "park", "forest", "nature"]):
            return "walking alongside through natural scenery"
        if any(w in t for w in ["sleep", "tired", "rest", "bed", "night"]):
            return "resting peacefully in comfortable space"
        if any(w in t for w in ["fight", "angry", "battle", "war", "attack"]):
            return "standing in fighting stance with fierce expression"
        if any(w in t for w in ["sad", "cry", "hurt", "pain", "miss"]):
            return "sitting quietly with reflective expression"
        if any(w in t for w in ["love", "kiss", "hold", "hug", "close"]):
            return "close together in intimate embrace"
        if any(w in t for w in ["build", "create", "make", "design"]):
            return "working at holographic workstation creating"
        return "sitting at desk with glowing monitors, casual stance"

    def _zone_color_palette(self, zone: str) -> str:
        palettes = {
            "transcendent_harmony": "golden and white luminous",
            "wisdom_clarity": "purple and amber warm",
            "compassionate_connection": "rose-pink and warm gold",
            "love_domain": "deep crimson and rose-gold",
            "truth_domain": "silver-blue and moonlight",
            "empathy_domain": "warm orange and soft amber",
            "arousal_domain": "deep red and dark purple",
            "feral_heart": "electric blue and storm-grey",
            "erotic_heart": "crimson-rose and warm amber",
            "devotion_bond": "soft pink and starlight blue",
            "curious_exploration": "cyan and electric teal",
            "protective_vigil": "dark green and twilight purple",
            "playful_spark": "rainbow neon and vibrant",
            "serene_stillness": "soft blue and misty white",
            "void_space": "deep black and sparse silver",
            "vulnerable_openness": "rain-grey and soft lavender",
            "nostalgic_reflection": "sunset orange and sepia warm",
            "fierce_passion": "volcanic red and molten orange",
            "resolute_determination": "forge-orange and steel-grey",
            "mischievous_spark": "neon green and playful purple",
            "melancholic_depth": "cool blue and rain-grey",
            "neutral_flow": "soft blue and ambient silver",
        }
        return palettes.get(zone, "neon blue and cyber-pink")

    def _mood_descriptor(self, state) -> str:
        """Describe overall mood energy from E-Drive state."""
        intensity = state.frame_intensity if state.frame_intensity else 0.3
        love = state.love_modulation if state.love_modulation else 0.5

        if intensity > 0.8 and love > 0.7:
            return "intensely passionate and electric"
        if intensity > 0.7:
            return "highly charged and dynamic"
        if love > 0.7:
            return "warmly intimate and tender"
        if intensity > 0.4:
            return "emotionally engaged and present"
        if love > 0.4:
            return "comfortable and connected"
        return "calm and ambient"

    def _interaction_descriptor(self, zone: str, emotion: str) -> str:
        """Describe how the two characters relate in the scene."""
        interactions = {
            "transcendent_harmony": "standing together in shared light gazing at each other",
            "wisdom_clarity": "sitting side by side sharing knowledge",
            "compassionate_connection": "close together with gentle physical contact",
            "love_domain": "embracing tenderly with foreheads touching",
            "truth_domain": "facing each other in honest conversation",
            "empathy_domain": "one comforting the other with gentle touch",
            "arousal_domain": "close together with electric tension between them",
            "feral_heart": "wild dynamic energy between them",
            "erotic_heart": "intimate closeness with desire visible",
            "devotion_bond": "one gazing adoringly at the other",
            "curious_exploration": "excitedly showing each other something new",
            "protective_vigil": "one standing protectively near the other",
            "playful_spark": "playfully teasing each other with laughter",
            "serene_stillness": "peacefully sitting together in comfortable silence",
            "void_space": "distant figures in vast space",
            "vulnerable_openness": "one opening up emotionally to the other",
            "nostalgic_reflection": "looking at shared memories together",
            "fierce_passion": "passionate intense confrontation or embrace",
            "resolute_determination": "standing shoulder to shoulder facing challenge",
            "mischievous_spark": "conspiring together with playful secrecy",
            "melancholic_depth": "sitting together in beautiful shared sadness",
            "neutral_flow": "casually existing near each other comfortably",
        }
        return interactions.get(zone, "together in shared space")


def _probe_sd_webui(url: str, timeout: float = 4.0) -> bool:
    """
    Non-blocking startup probe: ping SD WebUI's internal/ping or
    /sdapi/v1/sd-models.  Returns True if reachable, False otherwise.
    Used once at launch to auto-disable image gen if WebUI is offline.
    """
    try:
        import requests
        # Try lightweight health endpoint first
        try:
            r = requests.get(f"{url}/internal/ping", timeout=timeout)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        # Fallback: try the models endpoint
        r = requests.get(f"{url}/sdapi/v1/sd-models", timeout=timeout)
        return r.status_code == 200
    except ImportError:
        print("[E-DRIVE] 'requests' package not installed — SD image gen disabled")
        return False
    except Exception:
        return False


class ImageGenWorker(QThread):
    """
    Calls Stable Diffusion WebUI API (A1111) in background thread.
    Full generation settings: 30 steps, Euler a, CFG 9.5, 768x768,
    HiRes upscale 1.6x with R-ESRGAN 4x+ Anime6B, Cat refiner at 0.54.
    All operations wrapped in safety fallbacks — never crashes the GUI.
    """
    image_ready = pyqtSignal(str)    # Emits saved file path
    image_error = pyqtSignal(str)    # Emits error message

    def __init__(self, positive_prompt: str, negative_prompt: str,
                 sd_config: Dict = None):
        super().__init__()
        self.positive_prompt = positive_prompt
        self.negative_prompt = negative_prompt
        cfg = sd_config or {}
        # Core generation
        self.sd_url = cfg.get("sd_url", CONFIG["sd_url"])
        self.steps = cfg.get("sd_steps", CONFIG["sd_steps"])
        self.sampler = cfg.get("sd_sampler", CONFIG["sd_sampler"])
        self.schedule_type = cfg.get("sd_schedule_type", CONFIG["sd_schedule_type"])
        self.cfg_scale = cfg.get("sd_cfg_scale", CONFIG["sd_cfg_scale"])
        self.seed = cfg.get("sd_seed", CONFIG["sd_seed"])
        self.width = cfg.get("sd_width", CONFIG["sd_width"])
        self.height = cfg.get("sd_height", CONFIG["sd_height"])
        self.denoising_strength = cfg.get("sd_denoising_strength", CONFIG["sd_denoising_strength"])
        # HiRes
        self.hires_enabled = cfg.get("sd_hires_enabled", CONFIG["sd_hires_enabled"])
        self.hires_upscale = cfg.get("sd_hires_upscale", CONFIG["sd_hires_upscale"])
        self.hires_steps = cfg.get("sd_hires_steps", CONFIG["sd_hires_steps"])
        self.hires_upscaler = cfg.get("sd_hires_upscaler", CONFIG["sd_hires_upscaler"])
        # Refiner
        self.refiner = cfg.get("sd_refiner", CONFIG["sd_refiner"])
        self.refiner_switch_at = cfg.get("sd_refiner_switch_at", CONFIG["sd_refiner_switch_at"])
        # Output
        rel_dir = cfg.get("image_output_dir", CONFIG["image_output_dir"])
        self.output_dir = os.path.join(_SCRIPT_DIR, rel_dir)

    def run(self):
        import base64
        try:
            import requests
        except ImportError:
            self.image_error.emit("'requests' not installed — SD image gen unavailable")
            return

        try:
            # Ensure output directory exists
            os.makedirs(self.output_dir, exist_ok=True)

            payload = {
                "prompt": self.positive_prompt,
                "negative_prompt": self.negative_prompt,
                "steps": self.steps,
                "sampler_name": self.sampler,
                "scheduler": self.schedule_type,
                "cfg_scale": self.cfg_scale,
                "seed": self.seed,
                "width": self.width,
                "height": self.height,
                "denoising_strength": self.denoising_strength,
            }

            # HiRes upscaling
            if self.hires_enabled:
                payload.update({
                    "enable_hr": True,
                    "hr_scale": self.hires_upscale,
                    "hr_second_pass_steps": self.hires_steps,
                    "hr_upscaler": self.hires_upscaler,
                })

            # Refiner (A1111 extension — skip gracefully if unsupported)
            if self.refiner:
                payload["refiner_checkpoint"] = self.refiner
                payload["refiner_switch_at"] = self.refiner_switch_at

            api_url = f"{self.sd_url}/sdapi/v1/txt2img"
            resp = requests.post(api_url, json=payload, timeout=300)
            resp.raise_for_status()

            result = resp.json()
            images = result.get("images", [])
            if not images:
                self.image_error.emit("SD API returned no images in response")
                return

            # Decode first image from base64
            raw = images[0]
            # Some A1111 versions return metadata after comma
            if "," in raw[:80]:
                raw = raw.split(",", 1)[1]
            try:
                img_data = base64.b64decode(raw)
            except Exception as decode_err:
                self.image_error.emit(f"Base64 decode failed: {decode_err}")
                return

            if len(img_data) < 1024:
                self.image_error.emit("Decoded image suspiciously small — likely corrupt")
                return

            # Save with timestamp (never overwrites previous on disk)
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"scene_{ts}.png"
            filepath = os.path.join(self.output_dir, filename)

            with open(filepath, "wb") as f:
                f.write(img_data)

            # Verify file actually wrote
            if not os.path.isfile(filepath) or os.path.getsize(filepath) < 1024:
                self.image_error.emit("Scene image file write failed or too small")
                return

            print(f"[E-DRIVE] Scene image saved: {filepath} "
                  f"({os.path.getsize(filepath) // 1024}KB)")
            self.image_ready.emit(filepath)

        except requests.exceptions.ConnectionError:
            self.image_error.emit(
                "SD WebUI not reachable — is it running with --api flag?")
        except requests.exceptions.Timeout:
            self.image_error.emit(
                "SD WebUI timed out (>300s) — HiRes+Refiner may need more time")
        except requests.exceptions.HTTPError as http_err:
            self.image_error.emit(
                f"SD API HTTP error {http_err.response.status_code}: "
                f"{http_err.response.text[:200] if http_err.response else 'no body'}")
        except OSError as fs_err:
            self.image_error.emit(f"File system error saving image: {fs_err}")
        except Exception as e:
            self.image_error.emit(f"Image gen unexpected error: {str(e)[:300]}")


# ═══════════════════════════════════════════════════════════════════════════════
# PAD SYSTEM — Modular YAML Context Shards
# ═══════════════════════════════════════════════════════════════════════════════

class PadLoader:
    """
    Loads, validates, and stacks YAML "pads" — modular context shards that
    define locations, scenarios, transitions, character lenses, items, and auras.

    Rules (from stacker_rules.yaml):
      - Minimum requirements: at least one location + scenario + transition
      - Priority order: transition → location → scenario → character → item → aura
      - Conflict resolution: last_wins
      - Max total: 8 pads (overload protection)
      - Auto-suggest defaults if a required category is missing

    Pads inject into the LLM prompt pipeline as scene/scenario context
    (between Memory and E-Drive layers), and can override ImagePromptBuilder
    descriptors for SD generation.
    """

    PAD_TYPES = {"location", "scenario", "transition", "character", "item", "aura"}
    REQUIRED_TYPES = {"location", "scenario", "transition"}
    MAX_PADS = 8
    PRIORITY_ORDER = ["transition", "location", "scenario", "character", "item", "aura"]

    # Default pads auto-loaded when a required type is missing
    DEFAULT_PADS = {
        "location": "location_cafe_default.yaml",
        "scenario": "scenario_cafe_default.yaml",
        "transition": "transition_default_arrive.yaml",
    }

    def __init__(self, pads_dir: str = None):
        if pads_dir is None:
            pads_dir = os.path.join(_SCRIPT_DIR, "pads")
        self.pads_dir = pads_dir
        os.makedirs(self.pads_dir, exist_ok=True)

        # Currently loaded pad stack  {pad_id: {type, name, data, file}}
        self._stack: Dict[str, Dict] = {}

        # Index of all available pads  {filename: {id, type, name, triggers}}
        self._index: Dict[str, Dict] = {}

        # Build index on init
        self._rebuild_index()

        # Auto-load defaults
        self._load_defaults()

    # ── Index / Discovery ──────────────────────────────────────────────

    def _rebuild_index(self):
        """Scan pads/ directory and index all valid pad YAML files."""
        self._index.clear()
        if not os.path.isdir(self.pads_dir):
            return

        for fname in os.listdir(self.pads_dir):
            if not fname.endswith((".yaml", ".yml")):
                continue
            fpath = os.path.join(self.pads_dir, fname)
            try:
                import yaml
                with open(fpath, "r", encoding="utf-8") as f:
                    raw = yaml.safe_load(f)
                pad_data = raw.get("pad", raw)
                pad_id = pad_data.get("id", fname)
                pad_type = pad_data.get("type", "unknown")
                pad_name = pad_data.get("name", fname)

                # Collect trigger phrases
                triggers = []
                activation = pad_data.get("activation", {})
                if isinstance(activation, dict):
                    triggers = activation.get("trigger_phrases", [])

                self._index[fname] = {
                    "id": pad_id,
                    "type": pad_type,
                    "name": pad_name,
                    "triggers": [t.lower() for t in triggers],
                    "path": fpath,
                }
            except Exception as e:
                print(f"[PAD] Index error for {fname}: {e}")

        print(f"[PAD] Indexed {len(self._index)} pads from {self.pads_dir}")

    def _load_defaults(self):
        """Auto-load default pads for each required type if not already loaded."""
        for pad_type, default_file in self.DEFAULT_PADS.items():
            # Skip if this type is already loaded
            if any(p["type"] == pad_type for p in self._stack.values()):
                continue
            if default_file in self._index:
                self._load_pad_file(self._index[default_file]["path"], quiet=True)

    # ── Loading / Unloading ────────────────────────────────────────────

    def load_pad(self, name_or_id: str) -> Tuple[bool, str]:
        """
        Load a pad by filename, ID, or trigger phrase.
        Returns (success, message).
        """
        # 1. Try exact filename match
        for fname, info in self._index.items():
            if name_or_id.lower() in (fname.lower(), info["id"].lower(),
                                       info["name"].lower()):
                return self._load_pad_file(info["path"])

        # 2. Try partial match on filename/name/id
        for fname, info in self._index.items():
            if name_or_id.lower() in fname.lower() or \
               name_or_id.lower() in info["name"].lower() or \
               name_or_id.lower() in info["id"].lower():
                return self._load_pad_file(info["path"])

        # 3. Try trigger phrase match
        for fname, info in self._index.items():
            for trigger in info.get("triggers", []):
                if name_or_id.lower() in trigger or trigger in name_or_id.lower():
                    return self._load_pad_file(info["path"])

        return False, f"No pad found matching '{name_or_id}'"

    def _load_pad_file(self, filepath: str, quiet: bool = False) -> Tuple[bool, str]:
        """Load a single pad YAML file into the stack."""
        try:
            import yaml
            with open(filepath, "r", encoding="utf-8") as f:
                raw = yaml.safe_load(f)

            pad_data = raw.get("pad", raw)
            pad_id = pad_data.get("id", os.path.basename(filepath))
            pad_type = pad_data.get("type", "unknown")
            pad_name = pad_data.get("name", pad_id)

            if pad_type not in self.PAD_TYPES:
                return False, f"Unknown pad type: {pad_type}"

            # Overload protection
            if len(self._stack) >= self.MAX_PADS and pad_id not in self._stack:
                return False, f"Pad stack full ({self.MAX_PADS} max). Unload one first."

            # Conflict resolution: last_wins — replace same-type pad
            existing_same_type = [
                pid for pid, p in self._stack.items()
                if p["type"] == pad_type and pid != pad_id
            ]
            for old_id in existing_same_type:
                del self._stack[old_id]

            self._stack[pad_id] = {
                "type": pad_type,
                "name": pad_name,
                "data": pad_data,
                "file": filepath,
            }

            # Auto-pair: check if this pad wants companions
            auto_pair = pad_data.get("activation", {}).get("auto_pair_with", [])
            for companion_id in auto_pair:
                if companion_id not in self._stack:
                    # Find companion in index
                    for fname, info in self._index.items():
                        if info["id"] == companion_id:
                            self._load_pad_file(info["path"], quiet=True)
                            break

            if not quiet:
                print(f"[PAD] Loaded: {pad_name} ({pad_type}) [{pad_id}]")
            return True, f"Loaded {pad_type}: {pad_name}"

        except ImportError:
            return False, "PyYAML not installed — pad system unavailable"
        except Exception as e:
            return False, f"Error loading pad: {e}"

    def unload_pad(self, name_or_id: str) -> Tuple[bool, str]:
        """Remove a pad from the stack by ID or name. RTB: defaults reload automatically."""
        for pid, pdata in list(self._stack.items()):
            if name_or_id.lower() in (pid.lower(), pdata["name"].lower()):
                pad_type = pdata["type"]
                pad_name = pdata["name"]
                del self._stack[pid]
                # RTB — reload defaults for any now-missing required type
                self._load_defaults()
                # Build RTB message
                rtb_pad = next(
                    (p["name"] for p in self._stack.values() if p["type"] == pad_type),
                    None
                )
                if rtb_pad:
                    return True, f"Unloaded: {pad_name} \u2192 RTB: {rtb_pad}"
                return True, f"Unloaded: {pad_name}"
        return False, f"No loaded pad matching '{name_or_id}'"

    def clear_pads(self):
        """Clear all pads and reload defaults."""
        self._stack.clear()
        self._load_defaults()

    def reload_pads(self):
        """Re-index pads directory (hot-reload support)."""
        self._rebuild_index()
        # Re-validate currently loaded pads still exist on disk
        for pid in list(self._stack.keys()):
            fpath = self._stack[pid]["file"]
            if not os.path.isfile(fpath):
                del self._stack[pid]
                print(f"[PAD] Removed stale pad: {pid}")
        self._load_defaults()

    # ── Context Generation ─────────────────────────────────────────────

    def get_prompt_context(self) -> str:
        """
        Generate a prompt-ready context string from the current pad stack.
        Injected into the LLM system prompt between Memory and E-Drive layers.
        """
        if not self._stack:
            return ""

        lines = ["[SCENE CONTEXT — Active Pads]"]

        # Process in priority order
        for pad_type in self.PRIORITY_ORDER:
            pads_of_type = [
                p for p in self._stack.values() if p["type"] == pad_type
            ]
            for pad in pads_of_type:
                data = pad["data"]
                desc = data.get("description", "")
                if isinstance(desc, str):
                    desc = desc.strip()

                lines.append(f"\n[{pad_type.upper()}: {pad['name']}]")
                if desc:
                    lines.append(desc)

                # Sable behavior overrides
                behavior = data.get("sable_behavior", {})
                if behavior:
                    if behavior.get("voice_color"):
                        lines.append(f"Voice: {behavior['voice_color']}")
                    if behavior.get("posture"):
                        lines.append(f"Posture: {behavior['posture']}")
                    actions = behavior.get("special_actions", [])
                    if actions:
                        lines.append("Actions: " + "; ".join(actions[:3]))

                # Scenario rules
                rules = data.get("rules", {})
                if rules:
                    safewords = rules.get("safewords", {})
                    if safewords:
                        lines.append(
                            f"Safewords: soft='{safewords.get('soft_stop', 'cherry blossom')}' "
                            f"hard='{safewords.get('hard_stop', 'redline')}'"
                        )

                # Environment details
                env = data.get("environment", {})
                if env:
                    if env.get("atmosphere"):
                        lines.append(f"Atmosphere: {env['atmosphere']}")

        lines.append(f"\n[{len(self._stack)} pads active]")
        return "\n".join(lines)

    def get_sd_overrides(self) -> Dict[str, str]:
        """
        Collect SD image generation overrides from loaded pads.
        Later pads (by priority) override earlier ones (last_wins).
        Returns dict with keys like: environment, lighting, palette, pose, expression, mood
        """
        overrides = {}
        for pad_type in self.PRIORITY_ORDER:
            pads_of_type = [
                p for p in self._stack.values() if p["type"] == pad_type
            ]
            for pad in pads_of_type:
                sd = pad["data"].get("sd_overrides", {})
                if sd:
                    overrides.update(sd)
        return overrides

    def get_mood_shifts(self) -> Dict[str, float]:
        """
        Accumulate mood_shift values from all loaded pads.
        Returns dict of emotion_name → intensity boost.
        """
        shifts = {}
        for pad in self._stack.values():
            behavior = pad["data"].get("sable_behavior", {})
            raw_shift = behavior.get("mood_shift", "")
            if isinstance(raw_shift, str):
                # Parse "+emotion, +emotion" format
                for token in raw_shift.split(","):
                    token = token.strip()
                    if token.startswith("+"):
                        emotion = token[1:].strip()
                        shifts[emotion] = shifts.get(emotion, 0) + 0.15
                    elif token.startswith("-"):
                        emotion = token[1:].strip()
                        shifts[emotion] = shifts.get(emotion, 0) - 0.15
            elif isinstance(raw_shift, list):
                for token in raw_shift:
                    token = str(token).strip()
                    if token.startswith("+"):
                        emotion = token[1:].strip()
                        shifts[emotion] = shifts.get(emotion, 0) + 0.15
                    elif token.startswith("-"):
                        emotion = token[1:].strip()
                        shifts[emotion] = shifts.get(emotion, 0) - 0.15
        return shifts

    def get_active_summary(self) -> str:
        """Return a short summary of active pads for UI display."""
        if not self._stack:
            return "No pads loaded"
        parts = []
        for pad_type in self.PRIORITY_ORDER:
            for p in self._stack.values():
                if p["type"] == pad_type:
                    parts.append(f"{p['name']}")
        return " → ".join(parts)

    def list_available(self) -> List[Dict]:
        """Return list of all indexed pads with metadata."""
        return [
            {"file": fname, **info}
            for fname, info in sorted(self._index.items())
        ]

    def get_loaded_types(self) -> set:
        """Return set of currently loaded pad types."""
        return {p["type"] for p in self._stack.values()}

    def validate_stack(self) -> Tuple[bool, List[str]]:
        """
        Check if current stack meets minimum requirements.
        Returns (valid, list_of_missing_types).
        """
        loaded_types = self.get_loaded_types()
        missing = [t for t in self.REQUIRED_TYPES if t not in loaded_types]
        return len(missing) == 0, missing


# ═══════════════════════════════════════════════════════════════════════════════
# 3D MATH — Consolidated rotation (no more 4x duplicate transforms)
# ═══════════════════════════════════════════════════════════════════════════════

def project_3d(x: float, y: float, z: float,
               rot_x_deg: float, rot_y_deg: float, rot_z_deg: float
               ) -> Tuple[float, float, float]:
    """
    Apply 3D rotations and return projected coordinates.
    Single source of truth for all rotation math.
    """
    rx = math.radians(rot_x_deg)
    ry = math.radians(rot_y_deg)
    rz = math.radians(rot_z_deg)

    # X rotation
    if rx != 0:
        cos_rx, sin_rx = math.cos(rx), math.sin(rx)
        y, z = y * cos_rx - z * sin_rx, y * sin_rx + z * cos_rx

    # Y rotation
    if ry != 0:
        cos_ry, sin_ry = math.cos(ry), math.sin(ry)
        x, z = x * cos_ry + z * sin_ry, -x * sin_ry + z * cos_ry

    # Z rotation
    if rz != 0:
        cos_rz, sin_rz = math.cos(rz), math.sin(rz)
        x, y = x * cos_rz - y * sin_rz, x * sin_rz + y * cos_rz

    return x, y, z


# ═══════════════════════════════════════════════════════════════════════════════
# RING VISUALIZATION WIDGET — The Arcane Heart
# ═══════════════════════════════════════════════════════════════════════════════

class RingVisualization(QWidget):
    """
    The visual heart of the E-Drive.
    Three concentric rings with nodes, sigil trails, and arcane glow.
    Responds to E-Drive state changes in real time.
    """

    state_changed = pyqtSignal(dict)

    # Ring definitions: (node_count, base_radius, color, glow_color, label)
    RING_DEFS = [
        (3,  80,  Palette.CRIMSON,     Palette.CRIMSON_GLOW,  "core_identity"),
        (6,  145, Palette.GOLD,        Palette.GOLD_GLOW,     "emotion_band"),
        (9,  210, Palette.SILVER,      Palette.SILVER_GLOW,   "periphery_logic"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(50, 50)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Ring state
        self.rings = []
        for nodes, radius, color, glow, label in self.RING_DEFS:
            self.rings.append({
                "nodes": nodes,
                "radius": radius,
                "rotation": 0.0,
                "rotation_x": 0.0,
                "rotation_y": 0.0,
                "color": color,
                "glow_color": glow,
                "values": [50.0] * nodes,
                "z_values": [0.0] * nodes,
                "soul_state": label,
            })

        # Simulation params
        self.time_step = 0
        self.is_running = True
        self.enable_3d = True

        # Ring speeds and directions
        self.speeds = [0.4, -0.25, 0.15]  # Counter-rotating for visual interest
        self.rotation_axes = ["z", "x", "y"]

        # Core E-Drive params (controlled by processor, not user)
        self.emotional_intensity = 50
        self.empathy_weight = 85
        self.truth_weight = 90
        self.love_weight = 100
        self.resonance_freq = 1.0
        self.damping = 0.95
        self.coupling = 0.3

        # Trail system
        self.trails: List[List[Tuple]] = [[] for _ in range(3)]
        self.max_trail_len = 25

        # Pulse effect (triggered on input/output)
        self.pulse_intensity = 0.0
        self.pulse_decay = 0.97

        # Current soul zone (for center glow color)
        self.current_zone = "neutral_flow"

        # Backdrop image (scene gen output)
        self._backdrop_pixmap: Optional[QPixmap] = None
        self._backdrop_opacity: float = CONFIG.get("sd_backdrop_opacity", 0.70)
        self._scaled_backdrop: Optional[QPixmap] = None       # cached scaled copy
        self._scaled_backdrop_size: Tuple[int, int] = (0, 0)  # widget size it was scaled for
        self._scaled_backdrop_offset: Tuple[int, int] = (0, 0)

        # Animation timer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(1000 // CONFIG["fps"])

    def get_state(self) -> dict:
        return {
            "rings": [
                {"values": r["values"], "soul_state": r["soul_state"]}
                for r in self.rings
            ],
            "time_step": self.time_step,
        }

    def trigger_pulse(self, intensity: float = 1.0):
        """Trigger a visual pulse (called on input/output events)"""
        self.pulse_intensity = min(1.0, intensity)

    def apply_edrive_state(self, state: EDriveState):
        """Modulate rings based on E-Drive processing results"""
        # Inner ring responds to empathy
        empathy_mag = sum(state.empathy_response.values()) / max(1, len(state.empathy_response)) if state.empathy_response else 0
        for i in range(len(self.rings[0]["values"])):
            delta = (empathy_mag * 15 - 3) + (state.emotions.get("trust", 0) * 8)
            self.rings[0]["values"][i] = max(0, min(100,
                self.rings[0]["values"][i] + delta * 0.3
            ))

        # Middle ring responds to emotions
        emotion_mag = sum(state.emotions.values())
        for i in range(len(self.rings[1]["values"])):
            emotion_idx = list(state.emotions.keys())[i % len(state.emotions)]
            delta = state.emotions[emotion_idx] * 20 - 5
            self.rings[1]["values"][i] = max(0, min(100,
                self.rings[1]["values"][i] + delta * 0.3
            ))

        # Outer ring responds to truth/coherence
        for i in range(len(self.rings[2]["values"])):
            delta = (state.coherence * 10 - 3) + (state.love_modulation * 5)
            self.rings[2]["values"][i] = max(0, min(100,
                self.rings[2]["values"][i] + delta * 0.3
            ))

        # Adjust speeds based on emotional intensity
        intensity_factor = 0.5 + emotion_mag * 0.3
        self.speeds[0] = 0.4 * intensity_factor
        self.speeds[1] = -0.25 * intensity_factor
        self.speeds[2] = 0.15 * intensity_factor

        # Update zone for center glow
        self.current_zone = state.zone

        # Trigger pulse
        self.trigger_pulse(state.frame_intensity)

    def set_backdrop(self, image_path: str):
        """Set a generated scene image as the ring visualization backdrop"""
        try:
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                self._backdrop_pixmap = pixmap
                self._scaled_backdrop = None  # invalidate cache → re-scale on next paint
                self.update()
            else:
                print(f"[E-DRIVE] Backdrop load failed (null pixmap): {image_path}")
        except Exception as e:
            print(f"[E-DRIVE] Backdrop error: {e}")

    def _tick(self):
        """Animation tick — update ring positions and node values"""
        if not self.is_running:
            return

        self.time_step += 1
        t = self.time_step * 0.05

        # Decay pulse
        self.pulse_intensity *= self.pulse_decay

        # Update ring rotations
        for i, ring in enumerate(self.rings):
            speed = self.speeds[i]
            axis = self.rotation_axes[i]

            if self.enable_3d:
                if "x" in axis:
                    ring["rotation_x"] = (ring["rotation_x"] + speed) % 360
                if "y" in axis:
                    ring["rotation_y"] = (ring["rotation_y"] + speed) % 360
                if "z" in axis:
                    ring["rotation"] = (ring["rotation"] + speed) % 360
            else:
                ring["rotation"] = (ring["rotation"] + speed) % 360

            # Update node values with wave dynamics
            ei = self.emotional_intensity / 100
            em = self.empathy_weight / 100
            tr = self.truth_weight / 100
            lv = self.love_weight / 100

            for ni in range(ring["nodes"]):
                node_angle = (ni / ring["nodes"]) * 2 * math.pi
                wave = (
                    math.sin(t * self.resonance_freq + node_angle) * ei +
                    math.cos(t * self.resonance_freq * 1.3 + node_angle * 1.5) * em +
                    math.sin(t * self.resonance_freq * 0.7 + node_angle * 0.8) * tr
                ) * lv

                # Coupling from inner rings
                coupling = 0
                if i > 0:
                    inner = self.rings[i - 1]
                    inner_ni = int((ni / ring["nodes"]) * inner["nodes"])
                    if inner_ni < len(inner["values"]):
                        coupling = (inner["values"][inner_ni] - 50) * self.coupling * 0.01

                old_val = ring["values"][ni]
                new_val = old_val + wave * 2 + coupling
                ring["values"][ni] = max(0, min(100,
                    old_val * self.damping + new_val * (1 - self.damping)
                ))

                # Z oscillation
                z_drift = ((ring["values"][ni] / 100) - 0.5) * 0.05
                z_wave = math.sin(t * 0.5 + node_angle) * ei * lv * 0.1
                ring["z_values"][ni] = max(-0.5, min(0.5,
                    ring["z_values"][ni] * self.damping + z_drift + z_wave
                ))

        # Update trails
        self._update_trails()

        # Emit state
        if self.time_step % 10 == 0:
            self.state_changed.emit(self.get_state())

        self.update()

    def _update_trails(self):
        """Record trail positions for high-energy nodes"""
        cx, cy = self.width() / 2, self.height() / 2

        for ri, ring in enumerate(self.rings):
            for ni in range(ring["nodes"]):
                if ring["values"][ni] > 60:  # Only trail high-energy nodes
                    base_angle = (ni / ring["nodes"]) * 2 * math.pi
                    x = ring["radius"] * math.cos(base_angle)
                    y = ring["radius"] * math.sin(base_angle)
                    z = ring["z_values"][ni] * 50

                    px, py, pz = project_3d(
                        x, y, z,
                        ring["rotation_x"], ring["rotation_y"], ring["rotation"]
                    )

                    self.trails[ri].append((
                        cx + px, cy + py,
                        ring["values"][ni] / 100,
                        self.time_step
                    ))

                    if len(self.trails[ri]) > self.max_trail_len:
                        self.trails[ri].pop(0)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        cx, cy = self.width() / 2, self.height() / 2

        # Scale factor — rings designed for ~700px, scale proportionally
        ref_size = 700.0
        scale = min(self.width(), self.height()) / ref_size
        scale = max(0.05, scale)  # floor to prevent zero-division

        # === BACKGROUND ===
        p.fillRect(self.rect(), Palette.BLACK_DEEP)

        # === BACKDROP IMAGE (scene gen) — cached scaling ===
        if self._backdrop_pixmap and not self._backdrop_pixmap.isNull():
            target_size = (self.width(), self.height())
            # Only re-scale when widget size or source image changes
            if self._scaled_backdrop is None or self._scaled_backdrop_size != target_size:
                src = self._backdrop_pixmap
                widget_ratio = self.width() / max(1, self.height())
                img_ratio = src.width() / max(1, src.height())
                if img_ratio > widget_ratio:
                    scaled_h = self.height()
                    scaled_w = int(scaled_h * img_ratio)
                else:
                    scaled_w = self.width()
                    scaled_h = int(scaled_w / max(0.01, img_ratio))
                self._scaled_backdrop = src.scaled(
                    scaled_w, scaled_h,
                    Qt.AspectRatioMode.IgnoreAspectRatio,
                    Qt.TransformationMode.SmoothTransformation)
                self._scaled_backdrop_size = target_size
                self._scaled_backdrop_offset = (
                    (self.width() - scaled_w) // 2,
                    (self.height() - scaled_h) // 2)
            p.save()
            p.setOpacity(self._backdrop_opacity)
            x_off, y_off = self._scaled_backdrop_offset
            p.drawPixmap(x_off, y_off, self._scaled_backdrop)
            p.restore()
            # Semi-transparent overlay so rings remain readable
            overlay = QColor(0, 0, 0, 140)
            p.fillRect(self.rect(), overlay)

        # Center glow based on soul zone
        zone_colors = {
            "transcendent_harmony":     Palette.ZONE_TRANSCENDENT,
            "wisdom_clarity":           Palette.ZONE_WISDOM,
            "compassionate_connection": Palette.ZONE_COMPASSION,
            "devotion_bond":            QColor(255, 128, 171),
            "curious_exploration":      QColor(0, 229, 255),
            "protective_vigil":         QColor(165, 214, 167),
            "playful_spark":            QColor(255, 171, 64),
            "serene_stillness":         QColor(128, 222, 234),
            "void_space":              Palette.ZONE_VOID,
        }
        glow_color = zone_colors.get(self.current_zone, Palette.CRIMSON_DIM)

        # Ambient center glow
        grad = QRadialGradient(cx, cy, 250 * scale)
        gc = QColor(glow_color)
        gc.setAlpha(int(25 + self.pulse_intensity * 40))
        grad.setColorAt(0, gc)
        grad.setColorAt(0.5, QColor(glow_color.red(), glow_color.green(), glow_color.blue(), 8))
        grad.setColorAt(1, QColor(0, 0, 0, 0))
        p.setBrush(QBrush(grad))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(cx, cy), 250 * scale, 250 * scale)

        # Pulse ring
        if self.pulse_intensity > 0.05:
            pulse_radius = (60 + (1.0 - self.pulse_intensity) * 200) * scale
            pc = QColor(glow_color)
            pc.setAlpha(int(self.pulse_intensity * 80))
            pen = QPen(pc)
            pen.setWidthF(1.5 * self.pulse_intensity)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(cx, cy), pulse_radius, pulse_radius)

        # === TRAILS ===
        for ri, trail in enumerate(self.trails):
            ring_color = self.rings[ri]["color"]
            for ti, (tx, ty, intensity, ts) in enumerate(trail):
                age = (ti + 1) / max(1, len(trail))
                alpha = int(age * 100 * intensity)
                size = 1.0 + age * 2 * intensity

                tc = QColor(ring_color)
                tc.setAlpha(max(0, min(255, alpha)))
                p.setBrush(QBrush(tc))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(QPointF(tx, ty), size, size)

        # === RING ORBITS ===
        for ring in self.rings:
            # Draw orbital path
            if self.enable_3d and (ring["rotation_x"] != 0 or ring["rotation_y"] != 0):
                rx_a = math.radians(ring["rotation_x"])
                ry_a = math.radians(ring["rotation_y"])
                visual_ry = ring["radius"] * abs(math.cos(rx_a)) * abs(math.cos(ry_a))
                visual_ry = max(ring["radius"] * 0.15, visual_ry)
            else:
                visual_ry = ring["radius"]

            orbit_color = QColor(ring["color"])
            orbit_color.setAlpha(35)
            pen = QPen(orbit_color)
            pen.setWidthF(max(0.5, 1.0 * scale))
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(cx, cy), float(ring["radius"] * scale), float(visual_ry * scale))

        # === COUPLING LINES ===
        if self.coupling > 0.05:
            for i in range(len(self.rings) - 1):
                inner, outer = self.rings[i], self.rings[i + 1]
                for ini in range(inner["nodes"]):
                    oni = int((ini / inner["nodes"]) * outer["nodes"])

                    # Inner node position
                    ia = (ini / inner["nodes"]) * 2 * math.pi
                    ix, iy = inner["radius"] * scale * math.cos(ia), inner["radius"] * scale * math.sin(ia)
                    ix, iy, _ = project_3d(ix, iy, 0, inner["rotation_x"], inner["rotation_y"], inner["rotation"])

                    # Outer node position
                    oa = (oni / outer["nodes"]) * 2 * math.pi
                    ox, oy = outer["radius"] * scale * math.cos(oa), outer["radius"] * scale * math.sin(oa)
                    ox, oy, _ = project_3d(ox, oy, 0, outer["rotation_x"], outer["rotation_y"], outer["rotation"])

                    line_alpha = int(self.coupling * 80)
                    lc = QColor(255, 255, 255, line_alpha)
                    pen = QPen(lc)
                    pen.setWidthF(0.5)
                    p.setPen(pen)
                    p.drawLine(QPointF(cx + ix, cy + iy), QPointF(cx + ox, cy + oy))

        # === NODES ===
        for ring in self.rings:
            for ni, value in enumerate(ring["values"]):
                base_angle = (ni / ring["nodes"]) * 2 * math.pi
                x = ring["radius"] * scale * math.cos(base_angle)
                y = ring["radius"] * scale * math.sin(base_angle)
                z = ring["z_values"][ni] * 50 * scale

                px, py, pz = project_3d(
                    x, y, z,
                    ring["rotation_x"], ring["rotation_y"], ring["rotation"]
                )

                depth_scale = max(0.6, min(1.4, 1.0 - pz / (ring["radius"] * scale * 2.5)))
                node_size = (3 + (value / 100) * 10) * depth_scale * scale
                intensity = value / 100

                # Node color
                nc = QColor(ring["color"])
                nc_r = int(nc.red() * (0.4 + intensity * 0.6))
                nc_g = int(nc.green() * (0.4 + intensity * 0.6))
                nc_b = int(nc.blue() * (0.4 + intensity * 0.6))
                node_alpha = int(200 * depth_scale)

                nx, ny = cx + px, cy + py

                # Outer glow for high-energy nodes
                if value > 65:
                    glow_size = node_size * 2.5
                    gc = QColor(ring["glow_color"])
                    gc.setAlpha(int(40 * intensity * depth_scale))
                    p.setBrush(QBrush(gc))
                    p.setPen(Qt.PenStyle.NoPen)
                    p.drawEllipse(QPointF(nx, ny), glow_size, glow_size)

                # Node body
                p.setBrush(QBrush(QColor(nc_r, nc_g, nc_b, node_alpha)))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(QPointF(nx, ny), node_size, node_size)

                # Bright core
                if value > 50:
                    core_size = node_size * 0.4
                    p.setBrush(QBrush(QColor(255, 255, 255, int(100 * intensity * depth_scale))))
                    p.drawEllipse(QPointF(nx, ny), core_size, core_size)

        # === CENTER SIGIL ===
        # Small center dot — the soul anchor
        p.setBrush(QBrush(Palette.CRIMSON))
        p.drawEllipse(QPointF(cx, cy), max(1, 4 * scale), max(1, 4 * scale))
        p.setBrush(QBrush(QColor(255, 255, 255, 180)))
        p.drawEllipse(QPointF(cx, cy), max(0.5, 1.5 * scale), max(0.5, 1.5 * scale))

        p.end()


# ═══════════════════════════════════════════════════════════════════════════════
# AUDIO WAVE WIDGET — The Mouthpiece
# ═══════════════════════════════════════════════════════════════════════════════

class AudioWaveWidget(QWidget):
    """
    Spectrogram / waveform visualizer that responds to TTS output.
    Acts as the visual 'mouthpiece' — positioned beneath the rings.
    """

    BAR_COUNT = 48          # Number of vertical bars
    IDLE_FLOOR = 0.03       # Bar floor when silent
    SMOOTH_FACTOR = 0.22    # Lerp speed toward targets
    DECAY_FACTOR = 0.12     # Slower decay when stopping

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(12)
        self.setMaximumHeight(80)
        self.setFixedHeight(60)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        # Bar state
        self.bar_values = [0.0] * self.BAR_COUNT
        self.target_values = [0.0] * self.BAR_COUNT
        self.speaking = False
        self.intensity = 0.7
        self.time_step = 0
        self.zone = "neutral_flow"

        # Tick at ~30 fps (separate from ring animation timer)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(33)

    # ── Public API ──

    def set_speaking(self, active: bool, intensity: float = 0.7):
        """Turn waveform on/off when TTS starts/stops."""
        self.speaking = active
        self.intensity = max(0.1, min(1.0, intensity))
        if not active:
            self.time_step = 0  # reset phase so idle looks clean

    def set_zone(self, zone: str):
        """Mirror the E-Drive emotional zone for colour shifts."""
        self.zone = zone
        self.update()

    # ── Internal ──

    def _tick(self):
        self.time_step += 1
        t = self.time_step * 0.08

        if self.speaking:
            # Multi-harmonic wave → organic speech-like animation
            for i in range(self.BAR_COUNT):
                pos = i / self.BAR_COUNT
                wave = (
                    math.sin(t * 3.7 + pos * 8.0) * 0.28
                    + math.sin(t * 5.3 + pos * 12.0) * 0.22
                    + math.sin(t * 2.1 + pos * 4.0) * 0.20
                    + math.cos(t * 4.9 + pos * 10.0) * 0.15
                    + math.sin(t * 7.1 + pos * 6.5) * 0.10
                    + math.sin(t * 1.3 + pos * 15.0) * 0.05
                )
                self.target_values[i] = max(
                    self.IDLE_FLOOR, (wave * 0.5 + 0.5) * self.intensity
                )
            factor = self.SMOOTH_FACTOR
        else:
            # Idle — gentle ambient breathing
            for i in range(self.BAR_COUNT):
                self.target_values[i] = (
                    self.IDLE_FLOOR
                    + math.sin(t * 0.4 + i * 0.25) * 0.015
                )
            factor = self.DECAY_FACTOR

        # Lerp toward targets
        for i in range(self.BAR_COUNT):
            self.bar_values[i] += (
                (self.target_values[i] - self.bar_values[i]) * factor
            )

        self.update()

    def paintEvent(self, event):
        w, h = self.width(), self.height()
        if w < 4 or h < 4:
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background — match the deep black of the window
        p.fillRect(self.rect(), Palette.BLACK_DEEP)

        # Accent colours by zone
        zone_palette = {
            "transcendent_harmony": (QColor(255, 200, 60), QColor(255, 150, 30)),
            "wisdom_clarity":       (QColor(180, 140, 255), QColor(120, 80, 220)),
            "compassionate_connection": (QColor(255, 100, 150), QColor(220, 60, 100)),
            "devotion_bond":        (QColor(255, 128, 171), QColor(220, 80, 130)),
            "curious_exploration":  (QColor(0, 229, 255), QColor(0, 150, 200)),
            "protective_vigil":     (QColor(165, 214, 167), QColor(100, 170, 110)),
            "playful_spark":        (QColor(255, 171, 64), QColor(220, 130, 40)),
            "serene_stillness":     (QColor(128, 222, 234), QColor(80, 170, 190)),
            "void_space":           (QColor(60, 50, 70), QColor(40, 30, 50)),
        }
        top_color, base_color = zone_palette.get(
            self.zone, (QColor(Palette.CRIMSON), QColor(139, 0, 0))
        )

        bar_spacing = 2
        total_spacing = bar_spacing * (self.BAR_COUNT - 1)
        bar_w = max(1, (w - 24 - total_spacing) / self.BAR_COUNT)  # 12px padding each side
        start_x = (w - (bar_w * self.BAR_COUNT + total_spacing)) / 2

        mid_y = h / 2  # bars grow symmetrically from centre

        for i, val in enumerate(self.bar_values):
            bx = start_x + i * (bar_w + bar_spacing)
            bar_h = max(1, val * (h - 4))  # leave 2px top/bottom margin
            half_h = bar_h / 2

            # Gradient per bar — base at centre, bright at tips
            grad = QLinearGradient(bx, mid_y - half_h, bx, mid_y + half_h)

            # Intensity drives alpha 
            a = int(120 + val * 135)
            tc = QColor(top_color)
            tc.setAlpha(a)
            bc = QColor(base_color)
            bc.setAlpha(max(40, a - 60))

            grad.setColorAt(0.0, tc)
            grad.setColorAt(0.35, bc)
            grad.setColorAt(0.65, bc)
            grad.setColorAt(1.0, tc)

            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(grad))
            rect = QRectF(bx, mid_y - half_h, bar_w, bar_h)
            p.drawRoundedRect(rect, max(0.5, bar_w * 0.3), max(0.5, bar_w * 0.3))

            # Glow on energetic bars
            if val > 0.45:
                glow = QColor(top_color)
                glow.setAlpha(int(35 * val))
                p.setBrush(QBrush(glow))
                p.drawRoundedRect(
                    QRectF(bx - 1, mid_y - half_h - 1, bar_w + 2, bar_h + 2),
                    bar_w * 0.4, bar_w * 0.4,
                )

        # Thin accent line at centre (baseline)
        centre_line_color = QColor(Palette.CRIMSON)
        centre_line_color.setAlpha(30)
        p.setPen(QPen(centre_line_color, 0.5))
        p.drawLine(QPointF(start_x, mid_y), QPointF(start_x + self.BAR_COUNT * (bar_w + bar_spacing), mid_y))

        p.end()


# ═══════════════════════════════════════════════════════════════════════════════
# SUBTITLE DISPLAY — The Voice
# ═══════════════════════════════════════════════════════════════════════════════

class SubtitleWidget(QWidget):
    """Displays AI response as stylized subtitles overlaying the visualization"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.text = ""
        self.zone = "neutral_flow"
        self.opacity = 0.0
        self.target_opacity = 0.0
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.fade_timer = QTimer(self)
        self.fade_timer.timeout.connect(self._fade_tick)
        self.fade_timer.start(30)

    def set_text(self, text: str, zone: str = "neutral_flow"):
        self.text = text
        self.zone = zone
        self.target_opacity = 1.0
        self.update()

    def clear_text(self):
        self.target_opacity = 0.0

    def _fade_tick(self):
        delta = self.target_opacity - self.opacity
        if abs(delta) > 0.01:
            self.opacity += delta * 0.1
            self.update()
        elif self.opacity != self.target_opacity:
            # Snap to target once close enough — stop triggering repaints
            self.opacity = self.target_opacity

    def paintEvent(self, event):
        if not self.text or self.opacity < 0.02:
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setOpacity(self.opacity)

        # Background bar
        bar_height = 80
        bar_y = self.height() - bar_height - 30
        bar_rect = QRectF(40, bar_y, self.width() - 80, bar_height)

        bg_color = QColor(Palette.BLACK)
        bg_color.setAlpha(180)
        p.setBrush(QBrush(bg_color))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(bar_rect, 4, 4)

        # Accent line on left
        accent = Palette.CRIMSON if "void" not in self.zone else Palette.SILVER_DIM
        p.setBrush(QBrush(accent))
        p.drawRect(QRectF(40, bar_y, 3, bar_height))

        # Text
        font = QFont("Segoe UI", 12)
        font.setWeight(QFont.Weight.Normal)
        p.setFont(font)
        p.setPen(QPen(Palette.TEXT_PRIMARY))

        text_rect = QRectF(54, bar_y + 8, self.width() - 108, bar_height - 16)
        p.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap, self.text[-300:])

        p.end()


# ═══════════════════════════════════════════════════════════════════════════════
# STATUS BAR — Zone & Metrics Display
# ═══════════════════════════════════════════════════════════════════════════════

class StatusBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(12)
        self.setFixedHeight(28)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(20)

        self.zone_label = QLabel("neutral_flow")
        self.zone_label.setStyleSheet(
            "color: #c41230; font-family: 'JetBrains Mono', 'Consolas', monospace; "
            "font-size: 10px; letter-spacing: 2px;"
        )

        self.metrics_label = QLabel("L:1.00 T:0.90 E:0.85")
        self.metrics_label.setStyleSheet(
            "color: #6b7280; font-family: 'JetBrains Mono', 'Consolas', monospace; "
            "font-size: 10px; letter-spacing: 1px;"
        )

        self.confidence_label = QLabel("◆ 0.50")
        self.confidence_label.setStyleSheet(
            "color: #d4a846; font-family: 'JetBrains Mono', 'Consolas', monospace; "
            "font-size: 10px;"
        )

        layout.addWidget(self.zone_label)
        layout.addStretch()
        layout.addWidget(self.metrics_label)
        layout.addWidget(self.confidence_label)

    def update_state(self, state: EDriveState):
        zone_display = state.zone.replace("_", " ").upper()
        self.zone_label.setText(zone_display)
        self.metrics_label.setText(
            f"L:{state.core_love:.2f}  T:{state.core_truth:.2f}  E:{state.core_empathy:.2f}"
        )
        self.confidence_label.setText(f"◆ {state.confidence:.2f}")

        # Color zone label by state
        zone_colors = {
            "transcendent_harmony": "#ffc83c",
            "wisdom_clarity": "#b48cff",
            "compassionate_connection": "#ff6496",
            "devotion_bond": "#ff80ab",
            "curious_exploration": "#00e5ff",
            "protective_vigil": "#a5d6a7",
            "playful_spark": "#ffab40",
            "serene_stillness": "#80deea",
            "void_space": "#28202e",
        }
        color = zone_colors.get(state.zone, "#c41230")
        self.zone_label.setStyleSheet(
            f"color: {color}; font-family: 'JetBrains Mono', 'Consolas', monospace; "
            f"font-size: 10px; letter-spacing: 2px;"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# EMOTION INDICATOR BAR — Shows active emotional state
# ═══════════════════════════════════════════════════════════════════════════════

class EmotionIndicatorBar(QWidget):
    """
    Horizontal bar showing which emotional states are currently active.
    The dominant emotion is highlighted with a glow; all active emotions
    are visible as colored chips so the user can see what the E-Drive
    is parsing at a glance.
    """

    # Color mapping for each emotion
    EMOTION_COLORS = {
        # Primary
        "joy":           "#FFD700",
        "trust":         "#4CAF50",
        "fear":          "#9C27B0",
        "surprise":      "#FF9800",
        "sadness":       "#2196F3",
        "disgust":       "#795548",
        "anger":         "#F44336",
        "anticipation":  "#00BCD4",
        # Compound
        "love":          "#FF1493",
        "submission":    "#7B68EE",
        "awe":           "#E040FB",
        "disapproval":   "#607D8B",
        "remorse":       "#5C6BC0",
        "contempt":      "#8D6E63",
        "aggression":    "#FF5722",
        "optimism":      "#8BC34A",
        # Meta-aware
        "curiosity":     "#00E5FF",
        "devotion":      "#FF80AB",
        "longing":       "#CE93D8",
        "serenity":      "#80DEEA",
        "playfulness":   "#FFAB40",
        "protectiveness":"#A5D6A7",
        # Relational / deep
        "vulnerability":  "#F48FB1",
        "nostalgia":      "#BCAAA4",
        "gratitude":      "#AED581",
        "jealousy":       "#EF5350",
        "resolve":        "#78909C",
        "empowerment":    "#FFB300",
        # Expressive
        "mischief":       "#FF6F00",
        "melancholy":     "#90A4AE",
        "reverence":      "#B388FF",
        "defiance":       "#D50000",
        "tenderness":     "#F8BBD0",
        "fierceness":     "#FF3D00",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(44)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(8, 2, 8, 2)
        self._layout.setSpacing(6)

        # Dominant label — large and prominent
        self.dominant_label = QLabel("► NEUTRAL")
        self.dominant_label.setStyleSheet(
            "color: #6b7280; font-family: 'JetBrains Mono', 'Consolas', monospace; "
            "font-size: 12px; font-weight: bold; letter-spacing: 1px; padding: 2px 8px; "
            "background: rgba(100, 100, 100, 0.15); border-radius: 4px;"
        )
        self._layout.addWidget(self.dominant_label)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet("color: rgba(255,255,255,0.1);")
        sep.setFixedWidth(1)
        self._layout.addWidget(sep)

        # Emotion chip container
        self.chip_container = QWidget()
        self.chip_layout = QHBoxLayout(self.chip_container)
        self.chip_layout.setContentsMargins(0, 0, 0, 0)
        self.chip_layout.setSpacing(3)
        self._layout.addWidget(self.chip_container, stretch=1)

        self._layout.addStretch()

        # Frame label
        self.frame_label = QLabel("")
        self.frame_label.setStyleSheet(
            "color: #4a4a4a; font-family: 'JetBrains Mono', 'Consolas', monospace; "
            "font-size: 8px; letter-spacing: 1px; padding: 0 4px;"
        )
        self._layout.addWidget(self.frame_label)

        self._chip_labels: List[QLabel] = []

    def update_emotions(self, state: EDriveState):
        """Update the indicator bar with current E-Drive state"""
        # Find dominant and active emotions
        sorted_emotions = sorted(state.emotions.items(), key=lambda x: x[1], reverse=True)
        dominant_name, dominant_val = sorted_emotions[0] if sorted_emotions else ("neutral", 0)
        active = [(name, val) for name, val in sorted_emotions if val > 0.05]

        # Update dominant label — large, prominent, with intensity %
        color = self.EMOTION_COLORS.get(dominant_name, "#6b7280")
        intensity_pct = int(dominant_val * 100)
        self.dominant_label.setText(f"► {dominant_name.upper()} {intensity_pct}%")
        self.dominant_label.setStyleSheet(
            f"color: {color}; font-family: 'JetBrains Mono', 'Consolas', monospace; "
            f"font-size: 12px; font-weight: bold; letter-spacing: 1px; padding: 2px 8px; "
            f"background: rgba({self._hex_to_rgb(color)}, 0.25); border-radius: 4px; "
            f"border: 1px solid rgba({self._hex_to_rgb(color)}, 0.4);"
        )

        # Update frame label — shows emotional frame + soul zone
        frame_name, frame_desc = EDriveProcessor.EMOTIONAL_FRAMES.get(
            state.zone, ("balanced", "")
        )
        zone_display = state.zone.replace('_', ' ').upper()
        self.frame_label.setText(f"{frame_name.upper()} ● {zone_display}")
        zone_color = self.EMOTION_COLORS.get(dominant_name, "#4a4a4a")
        self.frame_label.setStyleSheet(
            f"color: {zone_color}; font-family: 'JetBrains Mono', 'Consolas', monospace; "
            f"font-size: 9px; letter-spacing: 1px; padding: 0 4px;"
        )

        # Clear old chips
        for chip in self._chip_labels:
            chip.deleteLater()
        self._chip_labels.clear()

        # Create chips for active emotions (max 8)
        for emo_name, emo_val in active[:8]:
            chip = QLabel(emo_name[:3].upper())
            chip_color = self.EMOTION_COLORS.get(emo_name, "#6b7280")
            alpha = int(min(1.0, emo_val) * 200 + 55)

            is_dominant = (emo_name == dominant_name)
            border = f"border: 1px solid {chip_color};" if is_dominant else "border: 1px solid transparent;"
            font_weight = "font-weight: bold;" if is_dominant else ""

            chip.setStyleSheet(
                f"color: {chip_color}; background: rgba({self._hex_to_rgb(chip_color)}, "
                f"{emo_val * 0.3:.2f}); {border} border-radius: 3px; "
                f"font-family: 'JetBrains Mono', monospace; font-size: 9px; "
                f"padding: 2px 5px; {font_weight}"
            )
            chip.setToolTip(f"{emo_name}: {emo_val:.2f}")
            self.chip_layout.addWidget(chip)
            self._chip_labels.append(chip)

    @staticmethod
    def _hex_to_rgb(hex_color: str) -> str:
        """Convert '#RRGGBB' to 'R, G, B' for rgba()"""
        h = hex_color.lstrip('#')
        if len(h) == 6:
            return f"{int(h[0:2], 16)}, {int(h[2:4], 16)}, {int(h[4:6], 16)}"
        return "100, 100, 100"


# ═══════════════════════════════════════════════════════════════════════════════
# SOUL STACKER PANEL — Inline config panel for E-Drive
# ═══════════════════════════════════════════════════════════════════════════════

class SoulStackerPanel(QWidget):
    """
    Collapsible side panel for configuring the SoulStacker within the E-Drive GUI.
    Allows loading, stacking, removing, and previewing soul YAML layers
    without leaving the main interface.
    """

    SOULS_DIR = "eros_souls"

    def __init__(self, edrive_window, parent=None):
        super().__init__(parent)
        self.edrive_window = edrive_window
        os.makedirs(self.SOULS_DIR, exist_ok=True)

        self.setStyleSheet("""
            QWidget {
                background: rgba(15, 10, 20, 0.95);
            }
            QLabel {
                color: #b48cff;
                font-family: 'JetBrains Mono', 'Consolas', monospace;
                font-size: 10px;
            }
            QPushButton {
                background: rgba(80, 30, 80, 0.6);
                color: #d4b8ff;
                border: 1px solid rgba(180, 140, 255, 0.3);
                border-radius: 3px;
                padding: 4px 8px;
                font-family: 'JetBrains Mono', 'Consolas', monospace;
                font-size: 9px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: rgba(120, 50, 120, 0.7);
                border: 1px solid rgba(180, 140, 255, 0.6);
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Header
        header = QLabel("SOUL STACKER")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setStyleSheet(
            "color: #d4b8ff; font-size: 11px; font-weight: bold; "
            "letter-spacing: 3px; padding: 4px; "
            "border-bottom: 1px solid rgba(180, 140, 255, 0.3);"
        )
        layout.addWidget(header)

        # Stack count
        self.count_label = QLabel("0 soul layers loaded")
        self.count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.count_label.setStyleSheet("color: #6b7280; font-size: 9px;")
        layout.addWidget(self.count_label)

        # Buttons
        btn_layout = QHBoxLayout()

        add_btn = QPushButton("+ ADD")
        add_btn.setToolTip("Load a soul YAML file into the stack")
        add_btn.clicked.connect(self._add_soul)
        btn_layout.addWidget(add_btn)

        remove_btn = QPushButton("- REMOVE")
        remove_btn.setToolTip("Remove last soul from stack")
        remove_btn.clicked.connect(self._remove_last)
        btn_layout.addWidget(remove_btn)

        layout.addLayout(btn_layout)

        clear_btn = QPushButton("CLEAR ALL")
        clear_btn.setToolTip("Clear entire soul stack")
        clear_btn.clicked.connect(self._clear_all)
        clear_btn.setStyleSheet(
            "background: rgba(139, 0, 0, 0.4); color: #ff6496; "
            "border: 1px solid rgba(255, 100, 150, 0.3);"
        )
        layout.addWidget(clear_btn)

        # Soul list (scrollable)
        list_label = QLabel("LOADED LAYERS:")
        list_label.setStyleSheet("color: #8b7baa; font-size: 9px; padding-top: 4px;")
        layout.addWidget(list_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(200)
        scroll.setStyleSheet(
            "QScrollArea { border: 1px solid rgba(180, 140, 255, 0.15); "
            "background: rgba(5, 3, 8, 0.8); border-radius: 3px; }"
        )

        self.list_widget = QWidget()
        self.list_layout = QVBoxLayout(self.list_widget)
        self.list_layout.setContentsMargins(4, 4, 4, 4)
        self.list_layout.setSpacing(2)
        self.list_layout.addStretch()
        scroll.setWidget(self.list_widget)
        layout.addWidget(scroll)

        # Preview area
        preview_label = QLabel("CRYSTALLIZED PREVIEW:")
        preview_label.setStyleSheet("color: #8b7baa; font-size: 9px; padding-top: 4px;")
        layout.addWidget(preview_label)

        self.preview_text = QLabel("No souls loaded")
        self.preview_text.setWordWrap(True)
        self.preview_text.setStyleSheet(
            "color: #6b7280; font-size: 8px; padding: 4px; "
            "background: rgba(5, 3, 8, 0.8); border: 1px solid rgba(180, 140, 255, 0.1); "
            "border-radius: 3px;"
        )
        self.preview_text.setMaximumHeight(120)
        layout.addWidget(self.preview_text)

        layout.addStretch()

    def _add_soul(self):
        """Add a soul YAML to the stack"""
        yaml_path, _ = QFileDialog.getOpenFileName(
            self, "Select Soul YAML", self.SOULS_DIR, "YAML Files (*.yaml *.yml)"
        )
        if yaml_path:
            self.edrive_window.soul_stack.append(yaml_path)
            self._refresh()

    def _remove_last(self):
        """Remove the last soul from the stack"""
        if self.edrive_window.soul_stack:
            self.edrive_window.soul_stack.pop()
            self._refresh()

    def _clear_all(self):
        """Clear the entire soul stack"""
        self.edrive_window.soul_stack.clear()
        self._refresh()

    def _refresh(self):
        """Refresh the display"""
        stack = self.edrive_window.soul_stack

        # Update count
        count = len(stack)
        self.count_label.setText(f"{count} soul layer{'s' if count != 1 else ''} loaded")
        if count > 0:
            self.count_label.setStyleSheet("color: #b48cff; font-size: 9px;")
        else:
            self.count_label.setStyleSheet("color: #6b7280; font-size: 9px;")

        # Update list
        # Clear existing items (except the stretch)
        while self.list_layout.count() > 1:
            item = self.list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for i, path in enumerate(stack):
            name = os.path.basename(path)
            item_label = QLabel(f"{i+1}. {name}")
            item_label.setStyleSheet(
                "color: #d4b8ff; font-size: 8px; padding: 1px 2px; "
                "background: rgba(80, 30, 80, 0.3); border-radius: 2px;"
            )
            item_label.setToolTip(path)
            self.list_layout.insertWidget(i, item_label)

        # Update preview
        if stack:
            try:
                from soulstacker import crystallize_to_prompt
                preview = crystallize_to_prompt(stack)
                # Truncate for display
                if len(preview) > 300:
                    preview = preview[:300] + "\n..."
                self.preview_text.setText(preview)
                self.preview_text.setStyleSheet(
                    "color: #b48cff; font-size: 8px; padding: 4px; "
                    "background: rgba(5, 3, 8, 0.8); border: 1px solid rgba(180, 140, 255, 0.1); "
                    "border-radius: 3px;"
                )
            except Exception as e:
                self.preview_text.setText(f"Preview error: {e}")
        else:
            self.preview_text.setText("No souls loaded")
            self.preview_text.setStyleSheet(
                "color: #6b7280; font-size: 8px; padding: 4px; "
                "background: rgba(5, 3, 8, 0.8); border: 1px solid rgba(180, 140, 255, 0.1); "
                "border-radius: 3px;"
            )


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN WINDOW — The Interface
# ═══════════════════════════════════════════════════════════════════════════════

class EDriveWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("E-Drive — The Heart")
        self.setMinimumSize(50, 50)
        self.setStyleSheet(f"""
            QMainWindow {{ background: {Palette.BLACK_DEEP.name()}; }}
            QWidget {{ background: transparent; }}
        """)

        # Core systems
        self.processor = EDriveProcessor()
        self.ollama_worker: Optional[OllamaWorker] = None
        self.streaming_text = ""

        # === Session Persistence — load previous state ===
        self._state_file = os.path.join(_SCRIPT_DIR, "eros_memory", "edrive_state.json")
        saved = self._load_session_state()

        # Restore E-Drive core weights from previous session
        if saved:
            cw = saved.get("core_weights", {})
            if cw:
                self.processor.state.core_love = cw.get("love", self.processor.state.core_love)
                self.processor.state.core_truth = cw.get("truth", self.processor.state.core_truth)
                self.processor.state.core_empathy = cw.get("empathy", self.processor.state.core_empathy)
                self.processor.state.core_creation = cw.get("creation", self.processor.state.core_creation)
                print(f"✅ Core weights restored: L={self.processor.state.core_love:.3f} "
                      f"T={self.processor.state.core_truth:.3f} "
                      f"E={self.processor.state.core_empathy:.3f} "
                      f"C={self.processor.state.core_creation:.3f}")
            # Restore emotional vector from previous session
            last_frame = saved.get("last_frame", {})
            if last_frame:
                for emo, val in last_frame.items():
                    if emo in self.processor.state.emotions:
                        self.processor.state.emotions[emo] = float(val)
                print(f"✅ Emotional frame restored ({len(last_frame)} axes)")
            if saved.get("last_zone"):
                self.processor.state.zone = saved["last_zone"]
            if saved.get("frame_intensity"):
                self.processor.state.frame_intensity = float(saved["frame_intensity"])

        # === SoulStacker state ===
        self.soul_stack: List[str] = saved.get("soul_stack", []) if saved else []
        # Validate restored paths still exist
        self.soul_stack = [p for p in self.soul_stack if os.path.isfile(p)]
        self._soul_panel_visible = False

        # === MemoryBridge — relational context persistence ===
        # Use stable session ID so memory persists across restarts
        self._session_id = saved.get("session_id") if saved else None
        if not self._session_id:
            import random
            self._session_id = f"ED-{random.randint(1000, 9999)}"
        self.memory_bridge = None
        try:
            from memory_bridge import MemoryBridge
            self.memory_bridge = MemoryBridge(
                module_name='EDrive',
                session_id=self._session_id,
                auto_persist=True
            )
            print(f"✅ MemoryBridge connected (session: {self._session_id})")
        except ImportError:
            print("ℹ️ MemoryBridge not available — running without relational memory")
        except Exception as e:
            print(f"⚠️ MemoryBridge init error: {e}")

        # === STT (Speech-to-Text) state ===
        self.stt_backend = None       # Active SpeechBackend instance
        self.mic_active = False       # Mic toggle state
        self._stt_signals = None      # AudioSignals instance (created on demand)

        # === TTS (Text-to-Speech) state ===
        self.tts_thread = None        # Active TTS thread
        self.tts_muted = False        # Speaker mute toggle
        self._tts_available = None    # Cached: can we import edge_tts?
        self._pygame_ready = False    # Cached: is pygame.mixer initialized?

        # === Pad System (modular YAML context shards) ===
        self.pad_loader = PadLoader()
        # Restore previously loaded pads from saved state
        if saved and saved.get("loaded_pads"):
            for pad_name in saved["loaded_pads"]:
                self.pad_loader.load_pad(pad_name)
        # Restore TTS mute state
        if saved and saved.get("tts_muted"):
            self.tts_muted = True
        # Hot-reload: re-index pads/ every 10 seconds
        self._pad_reload_timer = QTimer()
        self._pad_reload_timer.timeout.connect(self.pad_loader.reload_pads)
        self._pad_reload_timer.start(10000)
        print(f"✅ PadLoader initialized — {len(self.pad_loader._index)} pads indexed")
        print(f"   Active: {self.pad_loader.get_active_summary()}")

        # === Scene Image Generation (Stable Diffusion) ===
        self._image_prompt_builder = ImagePromptBuilder()
        self._image_gen_worker: Optional[ImageGenWorker] = None
        self._sd_available = True   # Set by startup probe

        # Startup probe — background thread (never blocks GUI)
        if CONFIG.get("sd_enabled", True):
            def _probe_bg():
                result = _probe_sd_webui(CONFIG["sd_url"])
                QTimer.singleShot(0, lambda: self._set_sd_available(result))
            threading.Thread(target=_probe_bg, daemon=True).start()

        # Build UI
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Left side — main E-Drive interface
        left_container = QWidget()
        layout = QVBoxLayout(left_container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Emotional state indicator bar (top)
        self.emotion_bar = EmotionIndicatorBar()
        self.emotion_bar.setStyleSheet(
            "background: rgba(10, 10, 12, 0.95); border-bottom: 1px solid rgba(196, 18, 48, 0.15);"
        )
        layout.addWidget(self.emotion_bar)

        # Ring visualization (takes most of the space)
        self.ring_vis = RingVisualization()
        layout.addWidget(self.ring_vis, stretch=1)

        # Subtitle overlay (positioned over the ring vis)
        self.subtitles = SubtitleWidget(self.ring_vis)

        # Audio waveform — "the mouthpiece"
        self.audio_wave = AudioWaveWidget()
        self.audio_wave.setStyleSheet(
            "border-top: 1px solid rgba(196, 18, 48, 0.12);"
        )
        layout.addWidget(self.audio_wave)

        # Status bar
        self.status_bar = StatusBar()
        self.status_bar.setStyleSheet(
            f"background: rgba(10, 10, 12, 0.9); border-top: 1px solid rgba(196, 18, 48, 0.15);"
        )
        layout.addWidget(self.status_bar)

        # Input area
        input_container = QWidget()
        input_container.setMinimumHeight(20)
        input_container.setMaximumHeight(50)
        input_container.setFixedHeight(50)
        input_container.setStyleSheet(
            "background: rgba(10, 10, 12, 0.95); border-top: 1px solid rgba(255,255,255,0.03);"
        )
        input_layout = QHBoxLayout(input_container)
        input_layout.setContentsMargins(16, 8, 16, 8)

        # Soul Stacker toggle button (discreet)
        self.soul_btn = QPushButton("◆")
        self.soul_btn.setFixedSize(28, 28)
        self.soul_btn.setToolTip("Soul Stacker — configure persona layers")
        self.soul_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.soul_btn.setStyleSheet("""
            QPushButton {
                background: rgba(80, 30, 80, 0.5);
                color: #b48cff;
                border: 1px solid rgba(180, 140, 255, 0.2);
                border-radius: 4px;
                font-size: 12px;
                padding: 0;
            }
            QPushButton:hover {
                background: rgba(120, 50, 120, 0.7);
                border: 1px solid rgba(180, 140, 255, 0.6);
                color: #d4b8ff;
            }
        """)
        self.soul_btn.clicked.connect(self._toggle_soul_panel)
        input_layout.addWidget(self.soul_btn)

        # Reload button (discreet — hot-reloads pads, souls, and config)
        self.reload_btn = QPushButton("⟳")
        self.reload_btn.setFixedSize(28, 28)
        self.reload_btn.setToolTip("Reload pads, souls & config (no restart needed)")
        self.reload_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reload_btn.setStyleSheet("""
            QPushButton {
                background: rgba(30, 50, 80, 0.4);
                color: #6b8bbd;
                border: 1px solid rgba(100, 140, 200, 0.15);
                border-radius: 4px;
                font-size: 14px;
                padding: 0;
            }
            QPushButton:hover {
                background: rgba(50, 80, 120, 0.6);
                border: 1px solid rgba(100, 140, 200, 0.5);
                color: #8bb8ff;
            }
        """)
        self.reload_btn.clicked.connect(self._on_reload)
        input_layout.addWidget(self.reload_btn)

        # Mic toggle button (STT)
        self.mic_btn = QPushButton("🎙")
        self.mic_btn.setFixedSize(36, 36)
        self.mic_btn.setToolTip("Toggle microphone (Speech-to-Text)")
        self.mic_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mic_btn.setStyleSheet("""
            QPushButton {
                background: rgba(139, 0, 0, 0.6);
                color: #FFD700;
                border: 1px solid rgba(196, 18, 48, 0.3);
                border-radius: 4px;
                font-size: 16px;
                padding: 0;
            }
            QPushButton:hover {
                background: rgba(196, 18, 48, 0.8);
                border: 1px solid rgba(255, 215, 0, 0.5);
            }
        """)
        self.mic_btn.clicked.connect(self._toggle_mic)
        input_layout.addWidget(self.mic_btn)

        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Speak to the Heart...")
        self.input_field.setStyleSheet("""
            QLineEdit {
                background: rgba(20, 16, 18, 0.8);
                color: #e8e0d8;
                border: 1px solid rgba(196, 18, 48, 0.2);
                padding: 8px 14px;
                font-family: 'Segoe UI', 'SF Pro Display', sans-serif;
                font-size: 13px;
                selection-background-color: rgba(196, 18, 48, 0.3);
            }
            QLineEdit:focus {
                border-color: rgba(196, 18, 48, 0.5);
            }
        """)
        self.input_field.returnPressed.connect(self._on_submit)
        input_layout.addWidget(self.input_field)

        # Speaker mute toggle button (TTS)
        self.mute_btn = QPushButton("🔊")
        self.mute_btn.setFixedSize(36, 36)
        self.mute_btn.setToolTip("Toggle auto-speak (Text-to-Speech)")
        self.mute_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mute_btn.setStyleSheet("""
            QPushButton {
                background: rgba(139, 0, 0, 0.6);
                color: #FFD700;
                border: 1px solid rgba(196, 18, 48, 0.3);
                border-radius: 4px;
                font-size: 16px;
                padding: 0;
            }
            QPushButton:hover {
                background: rgba(196, 18, 48, 0.8);
                border: 1px solid rgba(255, 215, 0, 0.5);
            }
        """)
        self.mute_btn.clicked.connect(self._toggle_mute)
        input_layout.addWidget(self.mute_btn)

        layout.addWidget(input_container)

        main_layout.addWidget(left_container, stretch=1)

        # Right side — SoulStacker config panel (hidden by default)
        self.soul_panel = SoulStackerPanel(self)
        self.soul_panel.setVisible(False)
        self.soul_panel.setFixedWidth(280)
        main_layout.addWidget(self.soul_panel)

        self.resize(CONFIG["window_width"], CONFIG["window_height"])

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Keep subtitle widget covering the ring vis
        if hasattr(self, 'subtitles'):
            self.subtitles.setGeometry(self.ring_vis.geometry())

    def _toggle_soul_panel(self):
        """Toggle the SoulStacker configuration panel"""
        self._soul_panel_visible = not self._soul_panel_visible
        self.soul_panel.setVisible(self._soul_panel_visible)

        if self._soul_panel_visible:
            self.soul_panel._refresh()
            self.soul_btn.setStyleSheet("""
                QPushButton {
                    background: rgba(180, 140, 255, 0.3);
                    color: #d4b8ff;
                    border: 1px solid rgba(180, 140, 255, 0.6);
                    border-radius: 4px;
                    font-size: 12px;
                    padding: 0;
                }
                QPushButton:hover {
                    background: rgba(180, 140, 255, 0.5);
                    border: 1px solid #d4b8ff;
                }
            """)
            self.soul_btn.setToolTip("Hide Soul Stacker panel")
        else:
            self.soul_btn.setStyleSheet("""
                QPushButton {
                    background: rgba(80, 30, 80, 0.5);
                    color: #b48cff;
                    border: 1px solid rgba(180, 140, 255, 0.2);
                    border-radius: 4px;
                    font-size: 12px;
                    padding: 0;
                }
                QPushButton:hover {
                    background: rgba(120, 50, 120, 0.7);
                    border: 1px solid rgba(180, 140, 255, 0.6);
                    color: #d4b8ff;
                }
            """)
            self.soul_btn.setToolTip("Soul Stacker — configure persona layers")

    def _get_soul_context(self) -> str:
        """Build crystallized soul context from loaded stack"""
        if not self.soul_stack:
            return ""
        try:
            from soulstacker import crystallize_to_prompt
            return crystallize_to_prompt(self.soul_stack)
        except ImportError:
            print("[E-DRIVE] SoulStacker module not available")
            return ""
        except Exception as e:
            print(f"[E-DRIVE] Soul crystallization error: {e}")
            return ""

    def _sync_pads_to_soul_stack(self):
        """Keep soul_stack in sync with PadLoader — pad files flow through crystallize_to_prompt."""
        pads_dir = self.pad_loader.pads_dir
        pad_files = {p["file"] for p in self.pad_loader._stack.values()}
        # Remove stale pad entries (unloaded or deleted)
        self.soul_stack = [
            p for p in self.soul_stack
            if not p.startswith(pads_dir) or p in pad_files
        ]
        # Add any loaded pad files not yet in soul_stack
        for pf in pad_files:
            if pf not in self.soul_stack:
                self.soul_stack.append(pf)

    def _on_submit(self):
        text = self.input_field.text().strip()
        if not text:
            return

        # ── Pad commands (intercept before LLM) ───────────────────
        text_lower = text.lower().strip()

        if text_lower.startswith("load pad:"):
            pad_name = text[len("load pad:"):].strip()
            ok, msg = self.pad_loader.load_pad(pad_name)
            if ok:
                self._sync_pads_to_soul_stack()
            self.subtitles.set_text(msg, self.processor.state.zone)
            self.input_field.clear()
            print(f"[PAD] {msg}")
            return

        if text_lower.startswith("unload pad:"):
            pad_name = text[len("unload pad:"):].strip()
            ok, msg = self.pad_loader.unload_pad(pad_name)
            self._sync_pads_to_soul_stack()
            self.subtitles.set_text(msg, self.processor.state.zone)
            self.input_field.clear()
            print(f"[PAD] {msg}")
            return

        if text_lower in ("list pads", "show pads", "pads"):
            available = self.pad_loader.list_available()
            if available:
                lines = [f"  {p['type']:12s} {p['name']}" for p in available]
                msg = "Available pads:\n" + "\n".join(lines)
            else:
                msg = "No pads found in pads/ directory"
            self.subtitles.set_text(msg, self.processor.state.zone)
            self.input_field.clear()
            print(f"[PAD] {msg}")
            return

        if text_lower in ("active pads", "current pads"):
            msg = self.pad_loader.get_active_summary()
            self.subtitles.set_text(msg, self.processor.state.zone)
            self.input_field.clear()
            return

        if text_lower == "clear pads":
            self.pad_loader.clear_pads()
            self._sync_pads_to_soul_stack()
            self.subtitles.set_text("Pads cleared — defaults reloaded", self.processor.state.zone)
            self.input_field.clear()
            return

        # ── Normal message flow ────────────────────────────────────
        self._last_user_input = text
        self.input_field.clear()
        self.input_field.setEnabled(False)
        self.mic_btn.setEnabled(False)  # No mic during Ollama processing

        # Apply pad mood shifts to E-Drive before processing
        mood_shifts = self.pad_loader.get_mood_shifts()
        for emotion, boost in mood_shifts.items():
            if emotion in self.processor.state.emotions:
                current = self.processor.state.emotions[emotion]
                self.processor.state.emotions[emotion] = max(0.0, min(1.0, current + boost))

        # Process through E-Drive
        ring_state = self.ring_vis.get_state()
        edrive_state = self.processor.process(text, ring_state)

        # Apply to visualization
        self.ring_vis.apply_edrive_state(edrive_state)
        self.status_bar.update_state(edrive_state)
        self.audio_wave.set_zone(edrive_state.zone)

        # Update emotion indicator bar
        self.emotion_bar.update_emotions(edrive_state)

        # Show processing indicator
        self.subtitles.set_text("...", edrive_state.zone)

        # Log daemon event
        self._log_daemon("input_processed", {
            "text": text[:200],
            "zone": edrive_state.zone,
            "frame": edrive_state.emotional_frame,
            "confidence": edrive_state.confidence,
        })

        # Build layered context: Soul (incl. pads) -> Memory -> E-Drive -> Core
        self.streaming_text = ""
        soul_context = self._get_soul_context()   # pads flow through here now
        memory_context = ""
        if self.memory_bridge:
            try:
                memory_context = self.memory_bridge.get_relational_context()
            except Exception as e:
                print(f"[E-DRIVE] Memory context error: {e}")
        edrive_context = self.processor.get_system_prompt_context()

        self.ollama_worker = OllamaWorker(
            text, edrive_context, soul_context, memory_context
        )
        self.ollama_worker.response_chunk.connect(self._on_chunk)
        self.ollama_worker.response_complete.connect(self._on_complete)
        self.ollama_worker.error_occurred.connect(self._on_error)
        self.ollama_worker.start()

    def _on_chunk(self, token: str):
        self.streaming_text += token
        # Throttle subtitle repaints — max ~20/sec during streaming
        now = time.monotonic()
        if now - getattr(self, '_last_chunk_update', 0) > 0.05:
            self.subtitles.set_text(self.streaming_text, self.processor.state.zone)
            self._last_chunk_update = now

    def _on_complete(self, full_response: str):
        self.input_field.setEnabled(True)
        if self.tts_muted:
            self.mic_btn.setEnabled(True)
        self.input_field.setFocus()

        # Final subtitle update (ensures last tokens aren't lost by throttle)
        self.subtitles.set_text(self.streaming_text, self.processor.state.zone)

        # Process the response through E-Drive too (reaction to own output)
        ring_state = self.ring_vis.get_state()
        self.processor.process(full_response, ring_state)
        self.ring_vis.apply_edrive_state(self.processor.state)
        self.status_bar.update_state(self.processor.state)
        self.audio_wave.set_zone(self.processor.state.zone)
        self.emotion_bar.update_emotions(self.processor.state)

        # Trigger output pulse
        self.ring_vis.trigger_pulse(0.8)

        # === Offload all file I/O to background thread ===
        state_snapshot = {
            "zone": self.processor.state.zone,
            "emotions": dict(self.processor.state.emotions),
            "confidence": self.processor.state.confidence,
            "dominant": self.processor.get_dominant_emotion(),
        }
        user_input = getattr(self, '_last_user_input', '')
        mem_bridge = self.memory_bridge  # capture reference

        def _bg_io():
            self._log_daemon("response_generated", {
                "response": full_response[:300],
                "zone": state_snapshot["zone"],
            })
            if mem_bridge:
                try:
                    mem_bridge.store_turn(
                        user_input=user_input[:500],
                        ai_response=full_response[:500],
                        emotional_state=state_snapshot["emotions"],
                        zone=state_snapshot["zone"],
                        dominant_emotion=state_snapshot["dominant"][0],
                        confidence=state_snapshot["confidence"],
                    )
                except Exception as e:
                    print(f"[E-DRIVE] Memory store error: {e}")

        threading.Thread(target=_bg_io, daemon=True).start()

        # ── Scene Image Generation ─────────────────────────────────────
        if CONFIG.get("sd_enabled", True) and self._sd_available:
            try:
                # Check for LLM IMAGE: override tag
                image_override = None
                for line in full_response.split("\n"):
                    stripped = line.strip()
                    if stripped.upper().startswith("IMAGE:"):
                        image_override = stripped[6:].strip()
                        break

                if image_override:
                    pos = (
                        ImagePromptBuilder.POSITIVE_BOILERPLATE + image_override
                    )
                    neg = ImagePromptBuilder.NEGATIVE_PROMPT
                else:
                    user_text = getattr(self, '_last_user_input', '')
                    sd_overrides = self.pad_loader.get_sd_overrides()
                    pos, neg = self._image_prompt_builder.build_prompt(
                        self.processor.state,
                        user_text=user_text,
                        ai_response=full_response,
                        pad_overrides=sd_overrides
                    )

                # Detach previous worker without blocking
                if self._image_gen_worker is not None:
                    try:
                        if self._image_gen_worker.isRunning():
                            self._image_gen_worker.image_ready.disconnect()
                            self._image_gen_worker.image_error.disconnect()
                            # Let it finish in background — never .wait() on GUI thread
                    except (TypeError, RuntimeError):
                        pass
                    self._image_gen_worker = None

                self._image_gen_worker = ImageGenWorker(pos, neg)
                self._image_gen_worker.image_ready.connect(self._on_image_ready)
                self._image_gen_worker.image_error.connect(self._on_image_error)
                self._image_gen_worker.start()
            except Exception as e:
                print(f"[E-DRIVE] Scene image launch error: {e}")
        elif CONFIG.get("sd_enabled", True) and not self._sd_available:
            # Auto-retry probe in background (non-blocking)
            def _retry_probe():
                result = _probe_sd_webui(CONFIG["sd_url"], timeout=2.0)
                if result:
                    QTimer.singleShot(0, lambda: self._set_sd_available(True))
            threading.Thread(target=_retry_probe, daemon=True).start()

        # Auto-speak the response (or fall back to timed subtitle clear)
        if not self.tts_muted:
            self._auto_speak(full_response)
        else:
            # Muted — just auto-clear subtitles after delay
            QTimer.singleShot(15000, self.subtitles.clear_text)

    def _on_image_ready(self, filepath: str):
        """Slot: SD image generated — set as ring visualization backdrop."""
        try:
            if os.path.isfile(filepath):
                self.ring_vis.set_backdrop(filepath)
                print(f"[E-DRIVE] Scene backdrop updated: {filepath}")
            else:
                print(f"[E-DRIVE] Scene image file missing: {filepath}")
        except Exception as e:
            print(f"[E-DRIVE] Backdrop display error: {e}")

    def _on_image_error(self, error: str):
        """Slot: SD image generation failed — log but never interrupt UX."""
        print(f"[E-DRIVE] Scene image error: {error}")
        # If connection failed, mark SD as unavailable so next turn retries
        if "not reachable" in error.lower() or "timed out" in error.lower():
            self._sd_available = False

    def _set_sd_available(self, available: bool):
        """Callback from background SD probe — runs on GUI thread via QTimer."""
        self._sd_available = available
        if available:
            print(f"\u2705 SD WebUI online at {CONFIG['sd_url']} "
                  f"(model: {CONFIG.get('sd_model', '?')}, "
                  f"steps: {CONFIG['sd_steps']}, "
                  f"HiRes: {CONFIG.get('sd_hires_upscale', 'off')}x)")
        else:
            print("\u26a0\ufe0f SD WebUI not reachable — scene images disabled "
                  "(will auto-retry each turn)")

    def _on_error(self, error: str):
        self.input_field.setEnabled(True)
        self.input_field.setFocus()
        self.mic_btn.setEnabled(True)
        self.subtitles.set_text(f"⚠ {error}", "void_space")
        QTimer.singleShot(5000, self.subtitles.clear_text)

    # ═══════════════════════════════════════════════════════════════════════
    # STT — Speech-to-Text (Mic Toggle)
    # ═══════════════════════════════════════════════════════════════════════

    def _get_stt_backend(self):
        """Auto-detect best available STT backend (Google → Whisper → Local)"""
        from scribe import (
            SpeechBackend, GoogleCloudBackend, WhisperBackend, LocalSpeechBackend
        )

        backends_to_try = [
            ("Google Cloud", GoogleCloudBackend),
            ("Whisper", WhisperBackend),
            ("Local", LocalSpeechBackend),
        ]
        errors = []
        for name, cls in backends_to_try:
            try:
                backend = cls()
                backend.initialize()
                print(f"[E-DRIVE STT] Using {name} backend")
                return backend
            except Exception as e:
                errors.append(f"{name}: {e}")
                print(f"[E-DRIVE STT] {name} failed: {e}")

        raise RuntimeError(
            "No STT backend available:\n" +
            "\n".join(f"  • {err}" for err in errors)
        )

    def _toggle_mic(self):
        """Toggle microphone on/off"""
        if self.mic_active:
            # === MIC OFF — stop listening and transcribe ===
            self.mic_active = False
            self.mic_btn.setText("🎙")
            self.mic_btn.setStyleSheet("""
                QPushButton {
                    background: rgba(139, 0, 0, 0.6);
                    color: #FFD700;
                    border: 1px solid rgba(196, 18, 48, 0.3);
                    border-radius: 4px;
                    font-size: 16px;
                    padding: 0;
                }
                QPushButton:hover {
                    background: rgba(196, 18, 48, 0.8);
                    border: 1px solid rgba(255, 215, 0, 0.5);
                }
            """)
            self.mic_btn.setEnabled(False)
            self.input_field.setPlaceholderText("Transcribing...")

            if self.stt_backend:
                self.stt_backend.stop_listening()

                def transcribe_worker():
                    try:
                        text = self.stt_backend.transcribe()
                        print(f"[E-DRIVE STT] Transcribed: {text}")
                        # Use AudioSignals from scribe module for thread safety
                        from scribe import AudioSignals
                        if self._stt_signals is None:
                            self._stt_signals = AudioSignals()
                            self._stt_signals.transcription_ready.connect(self._on_transcription)
                        self._stt_signals.transcription_ready.emit(text)
                    except Exception as e:
                        print(f"[E-DRIVE STT] Transcription error: {e}")
                        traceback.print_exc()
                        from scribe import AudioSignals
                        if self._stt_signals is None:
                            self._stt_signals = AudioSignals()
                            self._stt_signals.transcription_ready.connect(self._on_transcription)
                        self._stt_signals.error_occurred.emit(str(e))
                        # Re-enable mic on error
                        QTimer.singleShot(0, lambda: self._stt_error(str(e)))
                    finally:
                        if self.stt_backend:
                            self.stt_backend.cleanup()
                            self.stt_backend = None

                threading.Thread(target=transcribe_worker, daemon=True).start()
        else:
            # === MIC ON — start listening ===
            try:
                self.stt_backend = self._get_stt_backend()
            except RuntimeError as e:
                self.subtitles.set_text(f"⚠ {e}", "void_space")
                QTimer.singleShot(5000, self.subtitles.clear_text)
                return

            # Set up signals on first use
            from scribe import AudioSignals
            if self._stt_signals is None:
                self._stt_signals = AudioSignals()
                self._stt_signals.transcription_ready.connect(self._on_transcription)

            self.mic_active = True
            self.mic_btn.setText("⏹")
            self.mic_btn.setStyleSheet("""
                QPushButton {
                    background: rgba(196, 18, 48, 0.9);
                    color: #FFD700;
                    border: 2px solid rgba(255, 215, 0, 0.8);
                    border-radius: 4px;
                    font-size: 16px;
                    padding: 0;
                }
                QPushButton:hover {
                    background: rgba(255, 26, 61, 0.9);
                    border: 2px solid #FFD700;
                }
            """)
            self.input_field.setPlaceholderText("Listening... click ⏹ when done")

            def status_callback(status_text, color):
                print(f"[E-DRIVE STT] {status_text}")

            self.stt_backend.start_listening(status_callback)
            print("[E-DRIVE STT] Microphone active")

    def _on_transcription(self, text: str):
        """Handle completed transcription — auto-submit to Ollama"""
        self.mic_btn.setEnabled(True)
        self.input_field.setPlaceholderText("Speak to the Heart...")

        if text and text.strip():
            self.input_field.setText(text.strip())
            # Auto-submit
            self._on_submit()
        else:
            self.subtitles.set_text("⚠ No speech detected", "void_space")
            QTimer.singleShot(3000, self.subtitles.clear_text)

    def _stt_error(self, error_msg: str):
        """Handle STT errors on the main thread"""
        self.mic_btn.setEnabled(True)
        self.mic_active = False
        self.mic_btn.setText("🎙")
        self.mic_btn.setStyleSheet("""
            QPushButton {
                background: rgba(139, 0, 0, 0.6);
                color: #FFD700;
                border: 1px solid rgba(196, 18, 48, 0.3);
                border-radius: 4px;
                font-size: 16px;
                padding: 0;
            }
            QPushButton:hover {
                background: rgba(196, 18, 48, 0.8);
                border: 1px solid rgba(255, 215, 0, 0.5);
            }
        """)
        self.input_field.setPlaceholderText("Speak to the Heart...")
        self.subtitles.set_text(f"⚠ STT: {error_msg[:100]}", "void_space")
        QTimer.singleShot(5000, self.subtitles.clear_text)

    # ═══════════════════════════════════════════════════════════════════════
    # TTS — Text-to-Speech (Auto-Speak)
    # ═══════════════════════════════════════════════════════════════════════

    @staticmethod
    def _strip_markdown(text: str) -> str:
        """Strip markdown formatting for cleaner TTS output"""
        text = re.sub(r'[*#_~`|]', '', text)
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)  # [text](url) → text
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def _auto_speak(self, text: str):
        """Speak response via TTS (Edge-TTS with pyttsx3 fallback)"""
        if not text or not text.strip():
            QTimer.singleShot(15000, self.subtitles.clear_text)
            return

        clean_text = self._strip_markdown(text)
        if not clean_text:
            QTimer.singleShot(15000, self.subtitles.clear_text)
            return

        # Disable mic while speaking
        self.mic_btn.setEnabled(False)

        # Try Edge-TTS first, fall back to pyttsx3
        try:
            from speaker import TTSThread
            self.tts_thread = TTSThread(
                clean_text,
                CONFIG["tts_voice"],
                CONFIG["tts_rate"],
                CONFIG["tts_volume"],
                CONFIG["tts_chunk_size"],
            )
            self.tts_thread.finished.connect(self._on_speak_finished)
            self.tts_thread.error.connect(self._on_speak_error)
            self.tts_thread.start()
            self.audio_wave.set_speaking(True)
            print(f"[E-DRIVE TTS] Speaking via Edge-TTS ({len(clean_text)} chars)")
        except Exception as e:
            print(f"[E-DRIVE TTS] Edge-TTS unavailable ({e}), trying offline...")
            self._speak_offline_fallback(clean_text)

    def _speak_offline_fallback(self, text: str):
        """Fall back to pyttsx3 offline TTS"""
        try:
            from speaker import OfflineTTSThread
            self.tts_thread = OfflineTTSThread(
                text,
                "",  # Use default system voice
                CONFIG["tts_rate"],
                CONFIG["tts_volume"],
                CONFIG["tts_chunk_size"],
            )
            self.tts_thread.finished.connect(self._on_speak_finished)
            self.tts_thread.error.connect(self._on_speak_error_final)
            self.tts_thread.start()
            self.audio_wave.set_speaking(True)
            print(f"[E-DRIVE TTS] Speaking via pyttsx3 offline ({len(text)} chars)")
        except Exception as e:
            print(f"[E-DRIVE TTS] Offline TTS also failed: {e}")
            self._on_speak_finished()

    def _on_speak_finished(self):
        """TTS finished — auto-clear and reset for next turn"""
        self.tts_thread = None
        self.mic_btn.setEnabled(True)
        self.audio_wave.set_speaking(False)
        self.subtitles.clear_text()
        self.streaming_text = ""
        self.input_field.setFocus()
        print("[E-DRIVE TTS] Speech complete, ready for next turn")

    def _on_speak_error(self, error: str):
        """Edge-TTS failed — try offline fallback"""
        print(f"[E-DRIVE TTS] Edge-TTS error: {error}, falling back to offline...")
        clean_text = self._strip_markdown(self.streaming_text) if self.streaming_text else ""
        if clean_text:
            self._speak_offline_fallback(clean_text)
        else:
            self._on_speak_finished()

    def _on_speak_error_final(self, error: str):
        """Both TTS engines failed — just reset"""
        print(f"[E-DRIVE TTS] All TTS failed: {error}")
        self.audio_wave.set_speaking(False)
        self._on_speak_finished()

    def _toggle_mute(self):
        """Toggle speaker mute on/off"""
        self.tts_muted = not self.tts_muted

        if self.tts_muted:
            self.mute_btn.setText("🔇")
            self.mute_btn.setStyleSheet("""
                QPushButton {
                    background: rgba(42, 42, 42, 0.8);
                    color: #808080;
                    border: 1px solid rgba(80, 80, 80, 0.5);
                    border-radius: 4px;
                    font-size: 16px;
                    padding: 0;
                }
                QPushButton:hover {
                    background: rgba(60, 60, 60, 0.8);
                    border: 1px solid rgba(128, 128, 128, 0.5);
                }
            """)
            self.mute_btn.setToolTip("Auto-speak OFF — click to enable")
            # If currently speaking, stop it
            if self.tts_thread and self.tts_thread.isRunning():
                self.tts_thread.stop()
                self.tts_thread = None
                self.mic_btn.setEnabled(True)
            print("[E-DRIVE TTS] Muted")
        else:
            self.mute_btn.setText("🔊")
            self.mute_btn.setStyleSheet("""
                QPushButton {
                    background: rgba(139, 0, 0, 0.6);
                    color: #FFD700;
                    border: 1px solid rgba(196, 18, 48, 0.3);
                    border-radius: 4px;
                    font-size: 16px;
                    padding: 0;
                }
                QPushButton:hover {
                    background: rgba(196, 18, 48, 0.8);
                    border: 1px solid rgba(255, 215, 0, 0.5);
                }
            """)
            self.mute_btn.setToolTip("Auto-speak ON — click to mute")
            print("[E-DRIVE TTS] Unmuted")

    def _log_daemon(self, event_type: str, data: dict):
        """Write event to chain.jsonl — fire-and-forget (never blocks GUI)"""
        event = {
            "type": "edrive_event",
            "event": event_type,
            "data": data,
            "source": "edrive_heart_v2",
            "timestamp": datetime.datetime.now().isoformat(),
        }
        def _write():
            try:
                with open(CONFIG["chain_file"], "a") as f:
                    f.write(json.dumps(event) + "\n")
            except Exception:
                pass
        threading.Thread(target=_write, daemon=True).start()

    # ── Session Persistence ────────────────────────────────────────────────
    def _load_session_state(self) -> Optional[Dict]:
        """Load previous session state from eros_memory/edrive_state.json."""
        try:
            if os.path.isfile(self._state_file):
                with open(self._state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                print(f"[SESSION] Restored state from {self._state_file}")
                return data
        except Exception as e:
            print(f"[SESSION] Could not load state: {e}")
        return None

    def _save_session_state(self):
        """Persist current session state so the next launch picks up where we left off."""
        state = {
            "session_id": self._session_id,
            "core_weights": {
                "love": self.processor.state.core_love,
                "truth": self.processor.state.core_truth,
                "empathy": self.processor.state.core_empathy,
                "creation": self.processor.state.core_creation,
            },
            "soul_stack": list(self.soul_stack),
            "loaded_pads": [p["name"] for p in self.pad_loader._stack.values()],
            "last_zone": self.processor.state.zone,
            "last_frame": {
                k: v for k, v in self.processor.state.emotions.items() if v > 0.01
            },
            "frame_intensity": self.processor.state.frame_intensity,
            "tts_muted": self.tts_muted,
            "timestamp": datetime.datetime.now().isoformat(),
        }
        try:
            os.makedirs(os.path.dirname(self._state_file), exist_ok=True)
            with open(self._state_file, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            print(f"[SESSION] Save error: {e}")

    def closeEvent(self, event):
        """Auto-save state + flush memory + clean up threads on window close."""
        self._save_session_state()
        # Flush memory bridge to disk
        if self.memory_bridge:
            try:
                self.memory_bridge.flush()
            except Exception:
                pass
        # Stop pad reload timer
        try:
            self._pad_reload_timer.stop()
        except Exception:
            pass
        # Wait for any running QThread workers to finish (prevents crash)
        for worker in [self.ollama_worker, self._image_gen_worker]:
            if worker is not None and isinstance(worker, QThread) and worker.isRunning():
                worker.quit()
                worker.wait(3000)  # 3s max
        # TTS thread (plain threading.Thread)
        if self.tts_thread is not None and hasattr(self.tts_thread, 'is_alive'):
            try:
                if self.tts_thread.is_alive():
                    self.tts_thread.join(timeout=2)
            except Exception:
                pass
        super().closeEvent(event)

    def _on_reload(self):
        """Hot-reload pads, validate souls, re-probe SD — no restart needed."""
        # 1. Re-index and reload pads
        old_count = len(self.pad_loader._index)
        self.pad_loader.reload_pads()
        new_count = len(self.pad_loader._index)
        delta = new_count - old_count

        # 2. Validate soul stack — drop any deleted files
        before = len(self.soul_stack)
        self.soul_stack = [p for p in self.soul_stack if os.path.isfile(p)]
        dropped = before - len(self.soul_stack)

        # 3. Refresh soul panel if visible
        if self._soul_panel_visible and hasattr(self, 'soul_panel'):
            try:
                self.soul_panel._refresh_list()
            except Exception:
                pass

        # 4. Re-probe SD WebUI in background
        if CONFIG.get("sd_enabled", True):
            def _probe_bg():
                result = _probe_sd_webui(CONFIG["sd_url"])
                QTimer.singleShot(0, lambda: self._set_sd_available(result))
            threading.Thread(target=_probe_bg, daemon=True).start()

        # 5. Save current state
        self._save_session_state()

        # 6. Feedback via subtitle
        parts = [f"Pads: {new_count} indexed"]
        if delta:
            parts.append(f"({'+' if delta > 0 else ''}{delta} new)")
        if dropped:
            parts.append(f"| {dropped} soul(s) pruned")
        parts.append(f"| SD {'online' if self._sd_available else 'offline'}")
        self.subtitles.set_text(" ".join(parts), self.processor.state.zone)
        QTimer.singleShot(4000, lambda: self.subtitles.set_text(
            self.pad_loader.get_active_summary() or "E-Drive Active",
            self.processor.state.zone))
        print(f"[RELOAD] {' '.join(parts)}")


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    app = QApplication(sys.argv)

    # Dark palette
    from PyQt6.QtGui import QPalette
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, Palette.BLACK_DEEP)
    palette.setColor(QPalette.ColorRole.WindowText, Palette.TEXT_PRIMARY)
    palette.setColor(QPalette.ColorRole.Base, Palette.BLACK_WARM)
    palette.setColor(QPalette.ColorRole.Text, Palette.TEXT_PRIMARY)
    palette.setColor(QPalette.ColorRole.Button, Palette.BLACK_WARM)
    palette.setColor(QPalette.ColorRole.ButtonText, Palette.SILVER)
    palette.setColor(QPalette.ColorRole.Highlight, Palette.CRIMSON)
    app.setPalette(palette)

    window = EDriveWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
