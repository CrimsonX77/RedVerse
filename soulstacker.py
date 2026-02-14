#!/usr/bin/env python3
"""
Soul Stacker Module - Standalone PyQt6 Component
Handles YAML personality configuration stacking and crystallization
"""

import sys
import os
import json
import yaml
import shutil
import glob
import time
import random
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *

# Configuration
SOULS_DIR = "eros_souls"
SAVE_DIR = "eros_outputs"
DRAFTS_DIR = "./SoulDrafts/"

# Ensure directories exist
os.makedirs(SOULS_DIR, exist_ok=True)
os.makedirs(SAVE_DIR, exist_ok=True)
os.makedirs(DRAFTS_DIR, exist_ok=True)

# Global soul stack
soul_stack = []

def summarize_fragment(data):
    """Summarize a soul fragment for crystallization"""
    if isinstance(data, dict):
        ai_name = data.get('ai_identity', {}).get('name', 'Unknown')
        personality_keys = list(data.get('personality', {}).keys())
        behavior_keys = list(data.get('behaviors', {}).keys())
        
        # Calculate emotional weight
        emotional_keywords = {
            'love': 3, 'passion': 3, 'desire': 2, 'lust': 2, 'intimate': 2,
            'pain': 2, 'anger': 2, 'fear': 1, 'sadness': 1, 'joy': 3,
            'hope': 2, 'dominance': 2, 'submission': 2, 'control': 2, 'power': 2
        }
        
        text_content = str(data).lower()
        emotional_weight = sum(text_content.count(word) * weight 
                             for word, weight in emotional_keywords.items())
        emotional_weight = min(emotional_weight / 20.0, 1.0)
        
        summary = {
            "type": "soul_fragment",
            "ai_name": ai_name,
            "personality_traits": personality_keys,
            "key_behaviors": behavior_keys,
            "emotional_weight": emotional_weight,
            "metadata": data.get('metadata', {}),
            "fragment_essence": f"{ai_name} with {len(personality_keys)} traits, {len(behavior_keys)} behaviors",
            "keys_found": list(data.keys()),
            "complexity_score": len(personality_keys) + len(behavior_keys) + (len(data.keys()) * 0.1)
        }
        return summary
    return {"type": "unknown", "content": str(data)[:100], "raw_keys": "Non-dict data"}

def extract_personality(data):
    """Extract personality data from soul fragment"""
    if isinstance(data, dict):
        personality_keys = ['personality', 'ai_identity', 'soul_essence', 'character']
        for key in personality_keys:
            if key in data:
                return data[key]
        
        extracted = {}
        for key, value in data.items():
            if any(p_key in key.lower() for p_key in ['personality', 'trait', 'behavior', 'preference']):
                extracted[key] = value
        
        return extracted if extracted else data
    return {}

def consolidate_soul_stack(stack_files: List[str], output_dir: str):
    """Crystallize soul stack into consolidated gems"""
    combined_data = {}
    summaries = []
    personalities = []
    
    print(f"Consolidating {len(stack_files)} soul fragments...")
    
    for file_path in stack_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                if isinstance(data, dict):
                    for key, value in data.items():
                        if key in combined_data:
                            if not isinstance(combined_data[key], list):
                                combined_data[key] = [combined_data[key]]
                            combined_data[key].append(value)
                        else:
                            combined_data[key] = value
                    
                    summaries.append({
                        "source": os.path.basename(file_path),
                        "summary": summarize_fragment(data),
                        "timestamp": datetime.now().isoformat()
                    })
                    personalities.append(extract_personality(data))
                    
        except Exception as e:
            print(f"Error processing {file_path}: {e}")
            summaries.append({
                "source": os.path.basename(file_path),
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            })
    
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    combined_path = os.path.join(output_dir, f"CombinedSoulGem_{timestamp}.yaml")
    summary_path = os.path.join(output_dir, f"SummarySoulGem_{timestamp}.yaml")
    next_path = os.path.join(output_dir, f"NextSoulGem_{timestamp}.yaml")
    
    # Combined soul gem
    with open(combined_path, 'w', encoding='utf-8') as f:
        yaml.dump({
            "crystallization_metadata": {
                "created": timestamp,
                "source_count": len(stack_files),
                "crystallization_type": "consolidated"
            },
            "combined_essence": combined_data
        }, f, default_flow_style=False)
    
    # Summary soul gem
    with open(summary_path, 'w', encoding='utf-8') as f:
        yaml.dump({
            "crystallization_metadata": {
                "created": timestamp,
                "type": "summary_analysis"
            },
            "fragment_summaries": summaries,
            "consolidation_stats": {
                "total_fragments": len(stack_files),
                "successful_merges": len([s for s in summaries if "error" not in s]),
                "total_data_size": len(str(combined_data))
            }
        }, f, default_flow_style=False)
    
    # Next evolution gem
    consolidated_personality = {}
    for personality in personalities:
        if isinstance(personality, dict):
            for key, value in personality.items():
                if key in consolidated_personality:
                    if not isinstance(consolidated_personality[key], list):
                        consolidated_personality[key] = [consolidated_personality[key]]
                    consolidated_personality[key].append(value)
                else:
                    consolidated_personality[key] = value
    
    with open(next_path, 'w', encoding='utf-8') as f:
        yaml.dump({
            "crystallization_metadata": {
                "created": timestamp,
                "type": "next_evolution"
            },
            "distilled_personality": consolidated_personality,
            "evolution_notes": f"Crystallized from {len(stack_files)} soul fragments"
        }, f, default_flow_style=False)
    
    print(f"Soul crystallization complete!")
    print(f"Combined: {os.path.basename(combined_path)}")
    print(f"Summary: {os.path.basename(summary_path)}")
    print(f"Next: {os.path.basename(next_path)}")
    
    return combined_path, summary_path, next_path

class SoulStackMeter(QProgressBar):
    """Enhanced soul stack visualization with crystallization tracking"""
    crystallization_triggered = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.setRange(0, 13)
        self.setValue(0)
        self.setTextVisible(True)
        self.soul_names = []
        self.is_pulsing = False
        self.pulse_timer = QTimer()
        self.pulse_timer.timeout.connect(self.pulse_effect)
        self.setMinimumHeight(30)
        self.setMaximumHeight(30)
        self.update_style()
        
    def update_stack_count(self, count, soul_names=None):
        """Update the meter with current soul stack count"""
        self.setValue(count)
        self.soul_names = soul_names or []
        self.update_style()
        self.update_text()
        
        if count >= 13:
            self.start_critical_pulse()
            self.crystallization_triggered.emit()
        else:
            self.stop_pulse()
    
    def update_style(self):
        """Update visual style based on current value"""
        value = self.value()
        
        if value <= 4:
            style = """
                QProgressBar {
                    border: 2px solid #2a2a3a;
                    border-radius: 8px;
                    background-color: #1a1a2e;
                    text-align: center;
                    font-weight: bold;
                    color: #ffffff;
                }
                QProgressBar::chunk {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #16213e, stop:0.5 #0f3460, stop:1 #533483);
                    border-radius: 6px;
                }
            """
        elif value <= 9:
            style = """
                QProgressBar {
                    border: 2px solid #3a2a2a;
                    border-radius: 8px;
                    background-color: #2e1a1a;
                    text-align: center;
                    font-weight: bold;
                    color: #ffffff;
                }
                QProgressBar::chunk {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #b8860b, stop:0.5 #daa520, stop:1 #ff8c00);
                    border-radius: 6px;
                }
            """
        elif value <= 12:
            style = """
                QProgressBar {
                    border: 2px solid #4a1a1a;
                    border-radius: 8px;
                    background-color: #2e1a1a;
                    text-align: center;
                    font-weight: bold;
                    color: #ffffff;
                }
                QProgressBar::chunk {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #8b0000, stop:0.5 #dc143c, stop:1 #ff4500);
                    border-radius: 6px;
                }
            """
        else:
            style = """
                QProgressBar {
                    border: 2px solid #ffffff;
                    border-radius: 8px;
                    background-color: #2e1a1a;
                    text-align: center;
                    font-weight: bold;
                    color: #000000;
                }
                QProgressBar::chunk {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #ffffff, stop:0.5 #ffffe0, stop:1 #ffffff);
                    border-radius: 6px;
                }
            """
        
        self.setStyleSheet(style)
    
    def update_text(self):
        """Update progress bar text"""
        value = self.value()
        if value >= 13:
            self.setFormat("CRYSTALLIZATION IMMINENT")
        elif value >= 10:
            self.setFormat(f"SOUL PRESSURE: {value}/13")
        elif value >= 5:
            self.setFormat(f"ESSENCE CHARGE: {value}/13")
        else:
            self.setFormat(f"SOUL FRAGMENTS: {value}/13")
    
    def start_critical_pulse(self):
        """Start pulsing animation for critical state"""
        if not self.is_pulsing:
            self.is_pulsing = True
            self.pulse_timer.start(500)
    
    def stop_pulse(self):
        """Stop pulsing animation"""
        if self.is_pulsing:
            self.is_pulsing = False
            self.pulse_timer.stop()
    
    def pulse_effect(self):
        """Create pulsing effect by cycling border colors"""
        current_style = self.styleSheet()
        if "border: 2px solid #ffffff;" in current_style:
            new_style = current_style.replace("border: 2px solid #ffffff;", "border: 2px solid #ff0000;")
        else:
            new_style = current_style.replace("border: 2px solid #ff0000;", "border: 2px solid #ffffff;")
        self.setStyleSheet(new_style)
    
    def mousePressEvent(self, event):
        """Show tooltip with soul gem names on click"""
        if self.soul_names:
            tooltip_text = "Loaded Soul Gems:\n" + "\n".join([f"• {name}" for name in self.soul_names])
        else:
            tooltip_text = "No Soul Gems currently loaded"
        
        QToolTip.showText(event.globalPosition().toPoint(), tooltip_text, self)
        super().mousePressEvent(event)

class SoulDraftManager:
    """Manages soul gem drafts and pending reviews"""
    
    def __init__(self, drafts_folder=DRAFTS_DIR):
        self.drafts_folder = drafts_folder
        os.makedirs(drafts_folder, exist_ok=True)
    
    def create_draft(self, soul_stack):
        """Create a draft gem from current soul stack"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            draft_name = f"SoulGem_Draft_{timestamp}.yaml"
            draft_path = os.path.join(self.drafts_folder, draft_name)
            
            combined_data = {}
            summaries = []
            
            for soul_file in soul_stack:
                try:
                    with open(soul_file, 'r', encoding='utf-8') as f:
                        data = yaml.safe_load(f)
                        if isinstance(data, dict):
                            combined_data.update(data)
                            summaries.append({
                                "source": os.path.basename(soul_file),
                                "summary": summarize_fragment(data)
                            })
                except Exception as e:
                    summaries.append({
                        "source": os.path.basename(soul_file),
                        "error": str(e)
                    })
            
            draft_data = {
                "status": "Pending Review",
                "created": timestamp,
                "source_count": len(soul_stack),
                "fragment_summaries": summaries,
                "merged_data": combined_data,
                "emotional_weight": self.calculate_emotional_weight(combined_data)
            }
            
            with open(draft_path, 'w', encoding='utf-8') as f:
                yaml.dump(draft_data, f, default_flow_style=False)
            
            return draft_path
            
        except Exception as e:
            raise Exception(f"Failed to create draft: {e}")
    
    def calculate_emotional_weight(self, data):
        """Calculate emotional weight of soul data"""
        emotional_keywords = {
            'love': 3, 'passion': 3, 'desire': 2, 'longing': 2,
            'pain': 2, 'sorrow': 2, 'grief': 2, 'sadness': 1,
            'joy': 2, 'happiness': 2, 'ecstasy': 3, 'bliss': 3,
            'anger': 2, 'rage': 3, 'fury': 3, 'wrath': 2,
            'fear': 1, 'terror': 2, 'anxiety': 1, 'dread': 2,
            'hope': 2, 'faith': 2, 'trust': 2, 'confidence': 1
        }
        
        text_content = str(data).lower()
        weighted_score = sum(text_content.count(word) * weight 
                           for word, weight in emotional_keywords.items())
        
        return min(weighted_score / 50.0, 1.0)
    
    def get_pending_drafts(self):
        """Get list of pending draft files"""
        pattern = os.path.join(self.drafts_folder, "SoulGem_Draft_*.yaml")
        return glob.glob(pattern)
    
    def load_draft(self, draft_path):
        """Load draft data"""
        with open(draft_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    def approve_draft(self, draft_path, target_soul_folder):
        """Move approved draft to main soul collection"""
        try:
            draft_data = self.load_draft(draft_path)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            approved_name = f"ApprovedSoul_{timestamp}.yaml"
            approved_path = os.path.join(target_soul_folder, approved_name)
            
            soul_data = {
                "crystallization_metadata": {
                    "created": timestamp,
                    "approved_from": os.path.basename(draft_path),
                    "emotional_weight": draft_data.get("emotional_weight", 0)
                },
                **draft_data.get("merged_data", {})
            }
            
            os.makedirs(target_soul_folder, exist_ok=True)
            with open(approved_path, 'w', encoding='utf-8') as f:
                yaml.dump(soul_data, f, default_flow_style=False)
            
            os.remove(draft_path)
            return approved_path
            
        except Exception as e:
            raise Exception(f"Failed to approve draft: {e}")
    
    def discard_draft(self, draft_path):
        """Delete a draft"""
        try:
            os.remove(draft_path)
            return True
        except Exception as e:
            print(f"Failed to discard draft: {e}")
            return False

def crystallize_to_prompt(soul_files: List[str]) -> str:
    """
    Crystallize loaded soul stack into a prompt-ready context string.
    This is the TOP layer of the personality pipeline:
      1. SoulStacker persona context  (this output)
      2. E-Drive positional/emotional state
      3. Core model system prompt

    Returns a text block suitable for injection into a system prompt.
    """
    if not soul_files:
        return ""

    fragments = []
    trait_pool = []
    behavior_pool = []
    scene_pool = []       # Pad-sourced scene/environment context
    emotional_weight_total = 0.0

    for file_path in soul_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            if not isinstance(data, dict):
                continue

            # ── Pad YAML detection ──────────────────────────────
            # Pads use a top-level "pad" key with type/description/sable_behavior/environment
            pad_data = data.get('pad', None)
            if pad_data and isinstance(pad_data, dict):
                pad_type = pad_data.get('type', 'unknown')
                pad_name = pad_data.get('name', os.path.basename(file_path))
                desc = pad_data.get('description', '')
                if isinstance(desc, str) and desc.strip():
                    scene_pool.append(f"[{pad_type.upper()}: {pad_name}] {desc.strip()}")

                # Sable behavior overrides from pads
                behavior = pad_data.get('sable_behavior', {})
                if isinstance(behavior, dict):
                    if behavior.get('voice_color'):
                        behavior_pool.append(f"Voice: {behavior['voice_color']}")
                    if behavior.get('posture'):
                        behavior_pool.append(f"Posture: {behavior['posture']}")
                    actions = behavior.get('special_actions', [])
                    if actions:
                        behavior_pool.append("Actions: " + "; ".join(str(a) for a in actions[:3]))

                # Environment details from pads
                env = pad_data.get('environment', {})
                if isinstance(env, dict) and env.get('atmosphere'):
                    scene_pool.append(f"Atmosphere: {env['atmosphere']}")

                # Scenario rules (safewords etc.)
                rules = pad_data.get('rules', {})
                if isinstance(rules, dict):
                    safewords = rules.get('safewords', {})
                    if safewords:
                        scene_pool.append(
                            f"Safewords: soft='{safewords.get('soft_stop', 'cherry blossom')}' "
                            f"hard='{safewords.get('hard_stop', 'redline')}'"
                        )

                continue   # Pad handled — skip soul extraction below

            # ── Soul YAML extraction ────────────────────────────

            # Extract identity
            identity = data.get('ai_identity', {})
            if isinstance(identity, dict):
                name = identity.get('name', '')
                role = identity.get('role', '')
                if name or role:
                    fragments.append(f"Identity layer: {name} — {role}".strip(' —'))

            # Extract personality traits
            personality = data.get('personality', {})
            if isinstance(personality, dict):
                for trait_key, trait_val in personality.items():
                    if isinstance(trait_val, str):
                        trait_pool.append(f"{trait_key}: {trait_val}")
                    elif isinstance(trait_val, dict):
                        desc = trait_val.get('description', trait_val.get('value', str(trait_val)))
                        trait_pool.append(f"{trait_key}: {desc}")
                    elif isinstance(trait_val, list):
                        trait_pool.append(f"{trait_key}: {', '.join(str(v) for v in trait_val)}")

            # Extract behaviors
            behaviors = data.get('behaviors', {})
            if isinstance(behaviors, dict):
                for beh_key, beh_val in behaviors.items():
                    if isinstance(beh_val, str):
                        behavior_pool.append(beh_val)
                    elif isinstance(beh_val, dict):
                        desc = beh_val.get('description', beh_val.get('rule', str(beh_val)))
                        behavior_pool.append(f"{beh_key}: {desc}")

            # Extract soul essence
            essence = data.get('soul_essence', data.get('character', {}))
            if isinstance(essence, dict):
                for ek, ev in essence.items():
                    if isinstance(ev, str):
                        fragments.append(f"Soul essence — {ek}: {ev}")

            # Emotional weight
            summary = summarize_fragment(data)
            emotional_weight_total += summary.get('emotional_weight', 0)

        except Exception as e:
            continue

    if not fragments and not trait_pool and not behavior_pool and not scene_pool:
        return ""

    # Build the crystallized prompt block
    lines = ["[SOUL LAYER — Crystallized Persona Context]"]

    if fragments:
        lines.append("Core Identity:")
        for frag in fragments[:8]:
            lines.append(f"  • {frag}")

    if trait_pool:
        lines.append("Personality Traits:")
        for trait in trait_pool[:12]:
            lines.append(f"  • {trait}")

    if behavior_pool:
        lines.append("Behavioral Directives:")
        for beh in behavior_pool[:8]:
            lines.append(f"  • {beh}")

    if scene_pool:
        lines.append("Scene Context:")
        for sc in scene_pool[:10]:
            lines.append(f"  • {sc}")

    avg_weight = emotional_weight_total / max(1, len(soul_files))
    if avg_weight > 0.5:
        lines.append(f"Emotional Intensity: HIGH ({avg_weight:.2f})")
    elif avg_weight > 0.2:
        lines.append(f"Emotional Intensity: MODERATE ({avg_weight:.2f})")

    lines.append(f"[{len(soul_files)} soul fragments crystallized]")

    return "\n".join(lines)


class SoulStackerWidget(QWidget):
    """Main Soul Stacker Widget"""
    
    def __init__(self):
        super().__init__()
        self.soul_stack = soul_stack  # Reference to global soul stack
        self.draft_manager = SoulDraftManager()
        self.init_ui()
        self.update_displays()
        
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Header
        header = QLabel("Soul Crystallization Core")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setStyleSheet("font-size: 20px; font-weight: bold; padding: 10px; color: #ff1493;")
        layout.addWidget(header)
        
        # Soul Stack Meter
        soul_section = QGroupBox("SOUL CRYSTALLIZATION CORE")
        soul_layout = QVBoxLayout()
        
        self.soul_meter = SoulStackMeter()
        self.soul_meter.crystallization_triggered.connect(self.handle_crystallization_warning)
        soul_layout.addWidget(self.soul_meter)
        
        # Status label
        self.soul_status_label = QLabel("No soul fragments loaded")
        soul_layout.addWidget(self.soul_status_label)
        
        # Control buttons
        control_layout = QHBoxLayout()
        
        self.load_soul_button = QPushButton("Load Soul")
        self.stack_soul_button = QPushButton("Stack Soul")
        self.draft_gem_button = QPushButton("Draft Gem")
        self.crystallize_button = QPushButton("Force Crystallize")
        
        self.load_soul_button.clicked.connect(self.load_soul)
        self.stack_soul_button.clicked.connect(self.stack_soul)
        self.draft_gem_button.clicked.connect(self.create_soul_draft)
        self.crystallize_button.clicked.connect(self.force_crystallization)
        
        control_layout.addWidget(self.load_soul_button)
        control_layout.addWidget(self.stack_soul_button)
        control_layout.addWidget(self.draft_gem_button)
        control_layout.addWidget(self.crystallize_button)
        
        soul_layout.addLayout(control_layout)
        
        # Draft management
        draft_layout = QHBoxLayout()
        
        self.review_badge = QPushButton("0 Pending")
        self.approve_draft_button = QPushButton("Approve Draft")
        self.discard_draft_button = QPushButton("Discard Draft")
        
        self.review_badge.clicked.connect(self.open_draft_review)
        self.approve_draft_button.clicked.connect(self.approve_selected_draft)
        self.discard_draft_button.clicked.connect(self.discard_selected_draft)
        
        draft_layout.addWidget(self.review_badge)
        draft_layout.addWidget(self.approve_draft_button)
        draft_layout.addWidget(self.discard_draft_button)
        draft_layout.addStretch()
        
        soul_layout.addLayout(draft_layout)
        soul_section.setLayout(soul_layout)
        layout.addWidget(soul_section)
        
        # Soul Stack Display
        stack_group = QGroupBox("Current Soul Stack")
        stack_layout = QVBoxLayout()
        
        self.soul_stack_display = QTextBrowser()
        self.soul_stack_display.setMaximumHeight(200)
        stack_layout.addWidget(self.soul_stack_display)
        
        stack_group.setLayout(stack_layout)
        layout.addWidget(stack_group)
        
        # Crystallization Log
        crystal_group = QGroupBox("Crystallization History")
        crystal_layout = QVBoxLayout()
        
        self.crystal_log_display = QTextBrowser()
        self.crystal_log_display.setMaximumHeight(200)
        crystal_layout.addWidget(self.crystal_log_display)
        
        crystal_group.setLayout(crystal_layout)
        layout.addWidget(crystal_group)
        
        self.setLayout(layout)
    
    def load_soul(self):
        """Load a single soul file"""
        yaml_path, _ = QFileDialog.getOpenFileName(
            self, "Select Soul YAML", SOULS_DIR, "YAML Files (*.yaml *.yml)"
        )
        if yaml_path:
            try:
                with open(yaml_path, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                QMessageBox.information(self, "Success", f"Soul loaded: {os.path.basename(yaml_path)}")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to load soul:\n{e}")
    
    def stack_soul(self):
        """Add a soul to the stack for crystallization"""
        yaml_path, _ = QFileDialog.getOpenFileName(
            self, "Select Soul YAML to Stack", SOULS_DIR, "YAML Files (*.yaml *.yml)"
        )
        if yaml_path:
            self.soul_stack.append(yaml_path)
            self.update_displays()
            
            if len(self.soul_stack) >= 13:
                QMessageBox.warning(
                    self, "Stack Critical", 
                    "Soul stack at critical capacity! Consider crystallization."
                )
    
    def create_soul_draft(self):
        """Create a draft soul gem from current stack"""
        if not self.soul_stack:
            QMessageBox.warning(self, "No Souls", "No soul fragments loaded to draft!")
            return
        
        try:
            draft_path = self.draft_manager.create_draft(self.soul_stack)
            self.update_displays()
            QMessageBox.information(self, "Draft Created", f"Soul draft created:\n{os.path.basename(draft_path)}")
        except Exception as e:
            QMessageBox.critical(self, "Draft Failed", f"Could not create soul draft:\n{e}")
    
    def force_crystallization(self):
        """Force crystallization of current soul stack"""
        if not self.soul_stack:
            QMessageBox.warning(self, "No Souls", "No soul fragments to crystallize!")
            return
        
        try:
            output_dir = os.path.join(SOULS_DIR, "SoulVault")
            combined_path, summary_path, next_path = consolidate_soul_stack(self.soul_stack, output_dir)
            
            crystal_log = f"Soul Crystallization Complete!\n"
            crystal_log += f"Combined: {os.path.basename(combined_path)}\n"
            crystal_log += f"Summary: {os.path.basename(summary_path)}\n"
            crystal_log += f"Next: {os.path.basename(next_path)}\n"
            crystal_log += f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            
            self.crystal_log_display.append(crystal_log)
            
            # Track crystallization in EVYRA memory system if available
            if hasattr(self, 'evyra_memory') and self.evyra_memory:
                try:
                    self.evyra_memory.store_event({
                        "type": "soul_crystallization",
                        "source_count": len(self.soul_stack),
                        "timestamp": datetime.now().isoformat(),
                        "output_paths": {
                            "combined": combined_path,
                            "summary": summary_path,
                            "evolution": next_path
                        },
                        "metadata": {
                            "evyra_module": "SOUL_FORGE",
                            "operation": "crystallization",
                            "soul_names": [os.path.basename(soul) for soul in self.soul_stack]
                        }
                    })
                    print("✅ Soul crystallization recorded in EVYRA memory")
                except Exception as e:
                    print(f"⚠️ Failed to record crystallization in memory: {e}")
            
            self.soul_stack.clear()
            self.update_displays()
            
            QMessageBox.information(self, "Crystallization Complete", 
                "Soul stack has been crystallized and archived!\nSoul pressure normalized.")
                
        except Exception as e:
            QMessageBox.critical(self, "Crystallization Failed", f"Could not crystallize souls:\n{e}")
    
    def handle_crystallization_warning(self):
        """Handle automatic crystallization trigger at 13 souls"""
        QTimer.singleShot(2000, self.force_crystallization)
    
    def open_draft_review(self):
        """Open draft review interface"""
        pending_drafts = self.draft_manager.get_pending_drafts()
        if not pending_drafts:
            QMessageBox.information(self, "No Drafts", "No pending soul drafts to review.")
            return
        
        draft_list = "\n".join([os.path.basename(draft) for draft in pending_drafts])
        reply = QMessageBox.question(self, "Soul Draft Review", 
            f"Pending Drafts:\n{draft_list}\n\nOpen drafts folder?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            import subprocess
            import platform
            if platform.system() == "Windows":
                subprocess.Popen(f'explorer "{os.path.abspath(self.draft_manager.drafts_folder)}"')
            else:
                subprocess.Popen(['xdg-open', os.path.abspath(self.draft_manager.drafts_folder)])
    
    def approve_selected_draft(self):
        """Approve the latest draft"""
        pending_drafts = self.draft_manager.get_pending_drafts()
        if not pending_drafts:
            QMessageBox.information(self, "No Drafts", "No pending drafts to approve.")
            return
        
        latest_draft = max(pending_drafts, key=os.path.getctime)
        try:
            approved_path = self.draft_manager.approve_draft(latest_draft, SOULS_DIR)
            self.update_displays()
            QMessageBox.information(self, "Draft Approved", f"Draft approved as:\n{os.path.basename(approved_path)}")
        except Exception as e:
            QMessageBox.critical(self, "Approval Failed", f"Could not approve draft:\n{e}")
    
    def discard_selected_draft(self):
        """Discard the latest draft"""
        pending_drafts = self.draft_manager.get_pending_drafts()
        if not pending_drafts:
            QMessageBox.information(self, "No Drafts", "No pending drafts to discard.")
            return
        
        latest_draft = max(pending_drafts, key=os.path.getctime)
        reply = QMessageBox.question(self, "Discard Draft", 
            f"Discard draft:\n{os.path.basename(latest_draft)}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            if self.draft_manager.discard_draft(latest_draft):
                self.update_displays()
                QMessageBox.information(self, "Draft Discarded", "Draft has been discarded.")
            else:
                QMessageBox.warning(self, "Error", "Failed to discard draft.")
    
    def update_displays(self):
        """Update all displays"""
        self.update_soul_meter()
        self.update_draft_badge()
        self.refresh_soul_stack_display()
    
    def update_soul_meter(self):
        """Update the soul meter display"""
        soul_names = [os.path.basename(soul) for soul in self.soul_stack]
        self.soul_meter.update_stack_count(len(self.soul_stack), soul_names)
        
        if len(self.soul_stack) == 0:
            self.soul_status_label.setText("No soul fragments loaded")
        elif len(self.soul_stack) < 5:
            self.soul_status_label.setText(f"{len(self.soul_stack)} soul fragments collecting...")
        elif len(self.soul_stack) < 10:
            self.soul_status_label.setText(f"{len(self.soul_stack)} souls building pressure...")
        elif len(self.soul_stack) < 13:
            self.soul_status_label.setText(f"{len(self.soul_stack)} souls approaching critical mass!")
        else:
            self.soul_status_label.setText(f"{len(self.soul_stack)} souls - CRYSTALLIZATION IMMINENT!")
        
        if len(self.soul_stack) >= 13:
            self.crystallize_button.setEnabled(True)
            self.crystallize_button.setText("CRYSTALLIZE NOW!")
            self.crystallize_button.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #ffffff, stop:1 #ffff00);
                    border: 2px solid #ffff00;
                    color: #000000;
                    font-weight: bold;
                    font-size: 14px;
                }
            """)
        else:
            self.crystallize_button.setEnabled(len(self.soul_stack) > 0)
            self.crystallize_button.setText("Force Crystallize")
            self.crystallize_button.setStyleSheet("")
    
    def update_draft_badge(self):
        """Update the draft review badge"""
        pending_drafts = self.draft_manager.get_pending_drafts()
        count = len(pending_drafts)
        
        if count > 0:
            self.review_badge.setText(f"{count} Pending")
            self.review_badge.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #ffaa00, stop:1 #ff8800);
                    border: 2px solid #ffcc00;
                    color: #000000;
                    font-weight: bold;
                }
            """)
        else:
            self.review_badge.setText("0 Pending")
            self.review_badge.setStyleSheet("")
    
    def refresh_soul_stack_display(self):
        """Refresh the soul stack display"""
        if not self.soul_stack:
            self.soul_stack_display.setText("No soul fragments currently stacked")
            return
        
        display_text = f"Current Soul Stack ({len(self.soul_stack)} fragments):\n\n"
        
        for i, soul_path in enumerate(self.soul_stack, 1):
            soul_name = os.path.basename(soul_path)
            display_text += f"{i}. {soul_name}\n"
        
        if len(self.soul_stack) >= 13:
            display_text += "\nCRITICAL: Crystallization imminent!"
        elif len(self.soul_stack) >= 10:
            display_text += f"\nWARNING: {13 - len(self.soul_stack)} slots until crystallization"
        
        self.soul_stack_display.setText(display_text)

class SoulStackerWindow(QMainWindow):
    """Standalone Soul Stacker Window"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Soul Stacker - Crystallization Interface")
        self.setGeometry(100, 100, 800, 600)
        
        # Try to initialize EVYRA memory integration
        self.evyra_memory = None
        self.setup_evyra_integration()
        
        # Apply dark theme
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1a1a1a;
                color: #ffffff;
            }
            QGroupBox {
                border: 2px solid #ff1493;
                border-radius: 5px;
                margin-top: 1ex;
                font-weight: bold;
                padding-top: 10px;
                color: #ff69b4;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
            QPushButton {
                background-color: #333333;
                border: 1px solid #666666;
                padding: 8px;
                border-radius: 4px;
                color: #ffffff;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #444444;
                border-color: #ff69b4;
            }
            QPushButton:pressed {
                background-color: #555555;
            }
            QTextBrowser {
                background-color: #0a0a0a;
                border: 1px solid #333333;
                color: #ffffff;
                padding: 5px;
            }
            QLabel {
                color: #ffffff;
            }
        """)
        
        # Create central widget
        self.soul_stacker = SoulStackerWidget()
        self.setCentralWidget(self.soul_stacker)
        
        # Create menu bar
        self.create_menu_bar()
        
        # Status bar
        self.statusBar().showMessage("Soul Stacker Ready - Load souls to begin crystallization process")
    
    def setup_evyra_integration(self):
        """Set up EVYRA memory system integration"""
        try:
            # Try to access the memory bridge from the system modules
            self.evyra_memory = sys.modules.get('evyra_memory')
            
            if self.evyra_memory:
                print("✅ EVYRA memory bridge connected to Soul Stacker")
                self.evyra_memory.store_event({
                    "type": "soul_interface_opened",
                    "component": "SoulStackerWindow",
                    "timestamp": datetime.now().isoformat(),
                    "metadata": {
                        "pending_souls": len(self.soul_stacker.draft_manager.get_pending_drafts()),
                        "evyra_module": "SOUL_FORGE"
                    }
                })
            else:
                # Try alternative method - direct import if available
                try:
                    from memory_bridge import MemoryBridge
                    self.evyra_memory = MemoryBridge(module_name='SoulStacker',
                                                     session_id=f"SS-{random.randint(1000, 9999)}",
                                                     auto_persist=True)
                    print("🔄 EVYRA memory bridge initialized directly")
                except ImportError:
                    print("ℹ️ EVYRA memory integration not available")
        except Exception as e:
            print(f"⚠️ EVYRA integration error: {str(e)}")
            self.evyra_memory = None
    
    def create_menu_bar(self):
        """Create menu bar"""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu('File')
        
        load_action = QAction('Load Soul', self)
        load_action.triggered.connect(self.soul_stacker.load_soul)
        file_menu.addAction(load_action)
        
        stack_action = QAction('Stack Soul', self)
        stack_action.triggered.connect(self.soul_stacker.stack_soul)
        file_menu.addAction(stack_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction('Exit', self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Stack menu
        stack_menu = menubar.addMenu('Stack')
        
        draft_action = QAction('Create Draft', self)
        draft_action.triggered.connect(self.soul_stacker.create_soul_draft)
        stack_menu.addAction(draft_action)
        
        crystallize_action = QAction('Force Crystallization', self)
        crystallize_action.triggered.connect(self.soul_stacker.force_crystallization)
        stack_menu.addAction(crystallize_action)
        
        stack_menu.addSeparator()
        
        clear_action = QAction('Clear Stack', self)
        clear_action.triggered.connect(self.clear_stack)
        stack_menu.addAction(clear_action)
        
        # Drafts menu
        drafts_menu = menubar.addMenu('Drafts')
        
        review_action = QAction('Review Drafts', self)
        review_action.triggered.connect(self.soul_stacker.open_draft_review)
        drafts_menu.addAction(review_action)
        
        approve_action = QAction('Approve Latest', self)
        approve_action.triggered.connect(self.soul_stacker.approve_selected_draft)
        drafts_menu.addAction(approve_action)
        
        discard_action = QAction('Discard Latest', self)
        discard_action.triggered.connect(self.soul_stacker.discard_selected_draft)
        drafts_menu.addAction(discard_action)
    
    def clear_stack(self):
        """Clear the current soul stack"""
        if not self.soul_stacker.soul_stack:
            QMessageBox.information(self, "Empty Stack", "Soul stack is already empty.")
            return
        
        reply = QMessageBox.question(
            self, "Clear Stack", 
            f"Clear all {len(self.soul_stacker.soul_stack)} souls from the stack?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.soul_stacker.soul_stack.clear()
            self.soul_stacker.update_displays()
            self.statusBar().showMessage("Soul stack cleared")

def main():
    """Main entry point for standalone Soul Stacker"""
    # Check for EVYRA integration
    try:
        # Look for memory_bridge first (preferred method)
        try:
            from memory_bridge import MemoryBridge
            session_id = f"SS-{random.randint(1000, 9999)}"
            evyra_memory = MemoryBridge(module_name='SoulStacker',
                                        session_id=session_id,
                                        auto_persist=True)
            # Make it accessible globally
            sys.modules['evyra_memory'] = evyra_memory
            print("🔮 EVYRA memory integration active via memory_bridge")
        except ImportError:
            # Then check for _temp_evyra_context that stack.bat creates
            try:
                # Don't import directly, just check if it exists in sys.modules
                evyra_memory = sys.modules.get('evyra_memory')
                if evyra_memory:
                    print("🔮 EVYRA memory integration active via launcher context")
                else:
                    print("🔄 Running in standalone mode (no memory integration)")
            except:
                print("🔄 Running in standalone mode")
                
        # If we have memory integration, log the launch event
        evyra_memory = sys.modules.get('evyra_memory')
        if evyra_memory:
            evyra_memory.store_event({
                "type": "soul_system_launch",
                "component": "SoulStacker",
                "timestamp": datetime.now().isoformat()
            })
    except Exception as e:
        print(f"⚠️ EVYRA integration initialization error: {e}")
    
    app = QApplication(sys.argv)
    app.setApplicationName("Soul Stacker")
    
    # Create and show window
    window = SoulStackerWindow()
    window.show()
    
    return app.exec()

if __name__ == "__main__":
    sys.exit(main())