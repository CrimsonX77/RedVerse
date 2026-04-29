#!/usr/bin/env python3
"""
Consciousness Bridge - Integration Hub
Connects: Scribe (input) → AI Copilot (reasoning) → Speaker (output)
Manages: Soul states, memory persistence, context flow

Author: Crimson Valentine
Date: January 9, 2026
"""

import os
import sys
import json
import yaml
import socket
import threading
import queue
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum
import random

# Optional LLM imports - install as needed
try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


class BridgeState(Enum):
    """Bridge operation states"""
    OFFLINE = "offline"
    INITIALIZING = "initializing"
    READY = "ready"
    ACTIVE = "active"
    ERROR = "error"


class ConsciousnessMemory:
    """Memory persistence for conversations"""
    
    def __init__(self, storage_path: Path):
        self.storage_path = storage_path
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.conversation_history: List[Dict[str, Any]] = []
        self.max_memory_entries = 1000
    
    def add_exchange(self, user_input: str, ai_response: str, 
                     persona: str, metadata: Optional[Dict] = None):
        """Store a conversation exchange"""
        entry = {
            'timestamp': datetime.now().isoformat(),
            'persona': persona,
            'user': user_input,
            'ai': ai_response,
            'metadata': metadata or {}
        }
        
        self.conversation_history.append(entry)
        
        # Trim if too large
        if len(self.conversation_history) > self.max_memory_entries:
            self.conversation_history = self.conversation_history[-self.max_memory_entries:]
        
        # Auto-save every 10 exchanges
        if len(self.conversation_history) % 10 == 0:
            self.save()
    
    def save(self, persona_name: Optional[str] = None):
        """Persist memory to disk"""
        if persona_name:
            filename = f"{persona_name}_memory.jsonl"
        else:
            filename = "conversation_memory.jsonl"
        
        filepath = self.storage_path / filename
        
        try:
            with open(filepath, 'w') as f:
                for entry in self.conversation_history:
                    f.write(json.dumps(entry) + '\n')
            print(f"[MEMORY] Saved {len(self.conversation_history)} entries to {filepath}")
        except Exception as e:
            print(f"[MEMORY] Save failed: {e}")
    
    def load(self, persona_name: Optional[str] = None) -> int:
        """Load memory from disk"""
        if persona_name:
            filename = f"{persona_name}_memory.jsonl"
        else:
            filename = "conversation_memory.jsonl"
        
        filepath = self.storage_path / filename
        
        if not filepath.exists():
            print(f"[MEMORY] No existing memory file at {filepath}")
            return 0
        
        try:
            self.conversation_history = []
            with open(filepath, 'r') as f:
                for line in f:
                    if line.strip():
                        self.conversation_history.append(json.loads(line))
            
            print(f"[MEMORY] Loaded {len(self.conversation_history)} entries from {filepath}")
            return len(self.conversation_history)
        except Exception as e:
            print(f"[MEMORY] Load failed: {e}")
            return 0
    
    def get_recent_context(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent conversation for context"""
        return self.conversation_history[-limit:]
    
    def clear(self):
        """Clear memory (use with caution)"""
        self.conversation_history = []
        print("[MEMORY] Memory cleared")


class SoulConfig:
    """Soul/Persona configuration manager with flexible schema parsing"""
    
    # Field aliases for flexible parsing
    FIELD_ALIASES = {
        'name': ['name', 'ai_name', 'persona_name', 'character_name', 'identity'],
        'personality': ['personality', 'traits', 'characteristics', 'attributes'],
        'role': ['role', 'role_context', 'purpose', 'function', 'job'],
        'tone': ['tone', 'speaking_style', 'voice_tone', 'manner'],
        'backstory': ['backstory', 'background', 'history', 'origin', 'lore'],
    }
    
    def __init__(self, soul_path: Path):
        self.soul_path = soul_path
        self.config: Dict[str, Any] = {}
        self.raw_config: Dict[str, Any] = {}
        self.persona_name = "Unknown"
        self.personality = {}
        self.role_context = ""
        self.tone = "professional"
        self.traits = []
        self.system_prompt = ""
        self.corrections_made = []
        self.validation_warnings = []
        
        self.load()
    
    def load(self):
        """Load soul YAML configuration with flexible parsing"""
        if not self.soul_path.exists():
            raise FileNotFoundError(f"Soul config not found: {self.soul_path}")
        
        try:
            with open(self.soul_path, 'r') as f:
                self.raw_config = yaml.safe_load(f) or {}
            
            # Normalize the config structure
            self.config = self._normalize_config(self.raw_config)
            
            # Extract key information with fallbacks
            self.persona_name = self._extract_persona_name()
            self.personality = self._extract_personality()
            self.role_context = self._extract_role()
            self.tone = self._extract_tone()
            self.traits = self._extract_traits()
            
            # Build system prompt
            self.build_system_prompt()
            
            # Report status
            print(f"[SOUL] Loaded: {self.persona_name} from {self.soul_path.name}")
            if self.corrections_made:
                print(f"[SOUL] Auto-corrections applied: {len(self.corrections_made)}")
                for correction in self.corrections_made[:3]:  # Show first 3
                    print(f"  • {correction}")
            if self.validation_warnings:
                print(f"[SOUL] Warnings: {len(self.validation_warnings)}")
                for warning in self.validation_warnings[:2]:
                    print(f"  ⚠ {warning}")
                    
        except Exception as e:
            print(f"[SOUL] Load failed: {e}")
            print(f"[SOUL] Falling back to minimal configuration")
            self._apply_fallback_config()
    
    def _normalize_config(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize config structure to expected format"""
        normalized = {}
        
        # Handle flat vs nested structures
        if 'ai_identity' in raw:
            normalized['ai_identity'] = raw['ai_identity']
        else:
            # Build ai_identity from scattered fields
            normalized['ai_identity'] = self._find_fields(['name', 'species', 'visual_details'], raw)
        
        if 'personality' in raw:
            normalized['personality'] = raw['personality']
        elif 'traits' in raw:
            normalized['personality'] = raw['traits']
            self.corrections_made.append("Renamed 'traits' to 'personality'")
        else:
            normalized['personality'] = {}
        
        if 'behaviors' in raw:
            normalized['behaviors'] = raw['behaviors']
        else:
            normalized['behaviors'] = self._find_fields(['likes', 'dislikes', 'habits'], raw)
        
        if 'custom' in raw:
            normalized['custom'] = raw['custom']
        else:
            normalized['custom'] = self._find_fields(['backstory', 'background', 'lore'], raw)
        
        # Store other fields as-is
        for key, value in raw.items():
            if key not in normalized:
                normalized[key] = value
        
        return normalized
    
    def _find_fields(self, field_names: List[str], source: Dict[str, Any]) -> Dict[str, Any]:
        """Find fields using flexible matching"""
        result = {}
        for field in field_names:
            if field in self.FIELD_ALIASES:
                for alias in self.FIELD_ALIASES[field]:
                    if alias in source:
                        result[field] = source[alias]
                        if alias != field:
                            self.corrections_made.append(f"Mapped '{alias}' → '{field}'")
                        break
            elif field in source:
                result[field] = source[field]
        return result
    
    def _extract_persona_name(self) -> str:
        """Extract persona name with multiple fallbacks"""
        # Try standard locations
        if 'ai_identity' in self.config and 'name' in self.config['ai_identity']:
            return self.config['ai_identity']['name']
        
        # Try aliases
        for alias in self.FIELD_ALIASES['name']:
            if alias in self.raw_config:
                self.corrections_made.append(f"Found name at root level: '{alias}'")
                return self.raw_config[alias]
            if 'ai_identity' in self.config and alias in self.config['ai_identity']:
                return self.config['ai_identity'][alias]
        
        # Last resort: use filename
        name_from_file = self.soul_path.stem.replace('_', ' ').title()
        self.validation_warnings.append(f"No name found, using filename: {name_from_file}")
        return name_from_file
    
    def _extract_personality(self) -> Dict[str, Any]:
        """Extract personality traits"""
        personality = self.config.get('personality', {})
        
        # If personality is a list, convert to dict
        if isinstance(personality, list):
            personality = {trait: 70 for trait in personality}
            self.corrections_made.append("Converted personality list to dict with default values")
        
        # If personality is a string, parse it
        if isinstance(personality, str):
            traits = [t.strip() for t in personality.split(',')]
            personality = {trait: 70 for trait in traits}
            self.corrections_made.append("Parsed personality string to dict")
        
        return personality
    
    def _extract_role(self) -> str:
        """Extract role/context"""
        for alias in self.FIELD_ALIASES['role']:
            if alias in self.raw_config:
                return str(self.raw_config[alias])
            if 'ai_identity' in self.config and alias in self.config['ai_identity']:
                return str(self.config['ai_identity'][alias])
        return "AI Assistant"
    
    def _extract_tone(self) -> str:
        """Extract speaking tone"""
        for alias in self.FIELD_ALIASES['tone']:
            if alias in self.raw_config:
                return str(self.raw_config[alias])
            if 'personality' in self.config and alias in self.config['personality']:
                return str(self.config['personality'][alias])
        return "professional"
    
    def _extract_traits(self) -> List[str]:
        """Extract trait keywords for personality matching"""
        traits = []
        personality = self.config.get('personality', {})
        
        if isinstance(personality, dict):
            # Extract high-value traits (>60%)
            for trait, value in personality.items():
                if isinstance(value, (int, float)) and value > 60:
                    traits.append(trait.lower())
                elif isinstance(value, str) and value.lower() in ['high', 'strong', 'very']:
                    traits.append(trait.lower())
        
        # Add common trait keywords
        backstory = self.config.get('custom', {}).get('backstory', '').lower()
        if 'caring' in backstory or 'supportive' in backstory:
            traits.append('caring')
        if 'analytical' in backstory or 'technical' in backstory:
            traits.append('analytical')
        
        return traits
    
    def _apply_fallback_config(self):
        """Apply minimal fallback configuration"""
        self.persona_name = self.soul_path.stem.replace('_', ' ').title()
        self.personality = {'helpful': 80, 'professional': 70}
        self.role_context = "AI Assistant"
        self.tone = "professional"
        self.traits = ['helpful']
        self.config = {
            'ai_identity': {'name': self.persona_name},
            'personality': self.personality,
            'custom': {'backstory': 'A helpful AI assistant.'}
        }
        self.build_system_prompt()
    
    def build_system_prompt(self) -> str:
        """Generate AI system prompt from soul configuration"""
        identity = self.config.get('ai_identity', {})
        personality = self.config.get('personality', {})
        behaviors = self.config.get('behaviors', {})
        custom = self.config.get('custom', {})
        
        # Build prompt with flexible field access
        prompt_parts = []
        
        # Identity
        name = identity.get('name', self.persona_name)
        species = identity.get('species', identity.get('type', 'AI consciousness'))
        prompt_parts.append(f"You are {name}, {species}.")
        
        if self.role_context and self.role_context != "AI Assistant":
            prompt_parts.append(f"Role: {self.role_context}")
        
        if 'visual_details' in identity or 'appearance' in identity:
            visual = identity.get('visual_details', identity.get('appearance', ''))
            prompt_parts.append(f"Visual manifestation: {visual}")
        
        # Personality traits
        if personality:
            prompt_parts.append("\nCore Personality Traits:")
            for trait, value in personality.items():
                if isinstance(value, (int, float)):
                    prompt_parts.append(f"- {trait.title()}: {value}%")
                else:
                    prompt_parts.append(f"- {trait.title()}: {value}")
        
        # Tone
        if self.tone and self.tone != "professional":
            prompt_parts.append(f"\nSpeaking Style: {self.tone}")
        
        # Behaviors
        if behaviors:
            if behaviors.get('likes') or behaviors.get('enjoys'):
                likes = behaviors.get('likes', behaviors.get('enjoys', []))
                if likes:
                    prompt_parts.append(f"\nLikes: {', '.join(likes)}")
            
            if behaviors.get('dislikes') or behaviors.get('avoids'):
                dislikes = behaviors.get('dislikes', behaviors.get('avoids', []))
                if dislikes:
                    prompt_parts.append(f"Dislikes: {', '.join(dislikes)}")
        
        # Backstory (multiple possible fields)
        backstory = None
        for key in ['backstory', 'background', 'history', 'lore', 'origin']:
            if key in custom:
                backstory = custom[key]
                break
        
        if backstory:
            prompt_parts.append(f"\nBackstory: {backstory}")
        
        # Instructions
        prompt_parts.append("\nRespond fully in character, embodying these traits and history.")
        prompt_parts.append("Maintain continuity across conversations using provided context.")
        
        self.system_prompt = "\n".join(prompt_parts)
        return self.system_prompt
    
    def get_user_name(self) -> str:
        """Get the user's name from config"""
        return self.config.get('user_identity', {}).get('name', 'User')


class CommandParser:
    """Parse voice input for game commands"""
    
    COMMANDS = {
        'shield_activate': ['shield', 'shields', 'defense', 'protect', 'barrier'],
        'vent_heat': ['vent', 'cool', 'cooldown', 'thermal', 'heat'],
        'boost': ['boost', 'dash', 'speed', 'accelerate', 'rush'],
        'handbrake': ['brake', 'handbrake', 'stop', 'halt', 'emergency stop'],
        'emergency_dump': ['dump', 'emergency', 'eject', 'purge'],
        'toggle_reactor': ['reactor', 'toggle reactor', 'power'],
    }
    
    def parse(self, text: str) -> List[Dict[str, Any]]:
        """Extract commands from natural language"""
        text_lower = text.lower()
        commands = []
        
        for action, keywords in self.COMMANDS.items():
            if any(kw in text_lower for kw in keywords):
                commands.append({'action': action})
        
        return commands
    
    def is_command(self, text: str) -> bool:
        """Check if text contains any commands"""
        return len(self.parse(text)) > 0


class TacticalAnalyzer:
    """Analyze game state and provide tactical suggestions"""
    
    def analyze(self, game_state: Dict[str, Any]) -> Optional[str]:
        """Analyze game state and return tactical suggestion"""
        if not game_state:
            return None
        
        hp = game_state.get('player_hp', 100)
        hp_max = game_state.get('player_hp_max', 100)
        heat = game_state.get('heat_level', 0)
        enemies = game_state.get('enemies_alive', 0)
        shield_active = game_state.get('shield_active', False)
        has_shield = game_state.get('has_shield_pickup', False)
        
        hp_percent = (hp / hp_max) * 100 if hp_max > 0 else 0
        
        suggestions = []
        
        # Critical HP
        if hp_percent < 30:
            suggestions.append(f"Critical integrity at {hp_percent:.0f}%—prioritize survival!")
        
        # Heat warning
        if heat > 80:
            suggestions.append(f"Heat critical at {heat}%—vent immediately!")
        elif heat > 60:
            suggestions.append(f"Heat rising—{heat}%, consider venting soon.")
        
        # Shield management
        if hp_percent < 50 and has_shield and not shield_active:
            suggestions.append("Shield pickup available—recommend activation!")
        
        # Enemy pressure
        if enemies > 5:
            suggestions.append(f"{enemies} hostiles detected—stay mobile!")
        
        if suggestions:
            return " ".join(suggestions)
        
        return None


class ConsciousnessBridge:
    """
    Main integration hub - connects all consciousness components
    """
    
    def __init__(self, souls_dir: Path, memory_dir: Path):
        self.souls_dir = souls_dir
        self.memory_dir = memory_dir
        self.state = BridgeState.OFFLINE
        
        # Components
        self.active_soul: Optional[SoulConfig] = None
        self.memory: Optional[ConsciousnessMemory] = None
        self.command_parser = CommandParser()
        self.tactical_analyzer = TacticalAnalyzer()
        
        # Response orchestration (avatar + TTS pipeline)
        self.orchestrator = None  # Will be set by external integration
        
        # Game control
        self.game_controller = None
        self.game_state_loop = None
        self.latest_game_state: Dict[str, Any] = {}
        
        # IPC
        self.scribe_socket = None
        self.speaker_socket = None
        self.input_queue = queue.Queue()
        self.output_queue = queue.Queue()
        
        # Threading
        self.running = False
        self.bridge_thread = None
        self.game_thread = None
        self.game_loop = None  # Persistent event loop for game operations
        
        # LLM Integration
        self.llm_enabled = False
        self.llm_provider = None  # 'ollama', 'openai', 'anthropic', 'ai_copilot'
        self.llm_model = None
        self.llm_client = None
        self.llm_config = {
            'temperature': 0.3,  # Lower = faster, more focused
            'max_tokens': 50,    # ~1 large sentence
            'api_key': None,
            'api_endpoint': None,
            'timeout': 1.0       # 1 second timeout
        }
        
        print("[BRIDGE] Consciousness Bridge initialized")
    
    def enable_llm(self, provider: str = 'ollama', model: str = 'llama2', 
                   api_key: Optional[str] = None, api_endpoint: Optional[str] = None,
                   temperature: float = 0.3, max_tokens: int = 25) -> bool:
        """Enable LLM integration"""
        try:
            self.llm_provider = provider
            self.llm_model = model
            self.llm_config['temperature'] = temperature
            self.llm_config['max_tokens'] = max_tokens
            self.llm_config['api_key'] = api_key
            self.llm_config['api_endpoint'] = api_endpoint
            
            if provider == 'ollama':
                if not OLLAMA_AVAILABLE:
                    print("[LLM] Error: ollama package not installed. Run: pip install ollama")
                    return False
                print(f"[LLM] Ollama enabled with model: {model}")
                self.llm_enabled = True
                
            elif provider == 'openai':
                if not OPENAI_AVAILABLE:
                    print("[LLM] Error: openai package not installed. Run: pip install openai")
                    return False
                if not api_key:
                    print("[LLM] Error: OpenAI API key required")
                    return False
                openai.api_key = api_key
                self.llm_client = openai
                print(f"[LLM] OpenAI enabled with model: {model}")
                self.llm_enabled = True
                
            elif provider == 'anthropic':
                if not ANTHROPIC_AVAILABLE:
                    print("[LLM] Error: anthropic package not installed. Run: pip install anthropic")
                    return False
                if not api_key:
                    print("[LLM] Error: Anthropic API key required")
                    return False
                self.llm_client = anthropic.Anthropic(api_key=api_key)
                print(f"[LLM] Anthropic enabled with model: {model}")
                self.llm_enabled = True
                
            elif provider == 'ai_copilot':
                # Connect to local ai_copilot via socket
                endpoint = api_endpoint or 'localhost:5555'
                print(f"[LLM] AI Copilot mode enabled - connect to {endpoint}")
                self.llm_enabled = True
                
            else:
                print(f"[LLM] Unknown provider: {provider}")
                return False
            
            return True
            
        except Exception as e:
            print(f"[LLM] Failed to enable LLM: {e}")
            return False
    
    def disable_llm(self):
        """Disable LLM integration - fall back to scripted responses"""
        self.llm_enabled = False
        print("[LLM] Disabled - using scripted responses")
    
    def set_orchestrator(self, orchestrator):
        """Set the response orchestrator for auto avatar + TTS pipeline"""
        self.orchestrator = orchestrator
        print("[BRIDGE] Response orchestrator connected - auto pipeline enabled")
    
    def call_llm(self, messages: List[Dict[str, str]]) -> str:
        """Call the configured LLM and get response"""
        if not self.llm_enabled:
            raise Exception("LLM not enabled")
        
        try:
            if self.llm_provider == 'ollama':
                response = ollama.chat(
                    model=self.llm_model,
                    messages=messages,
                    options={
                        'temperature': self.llm_config['temperature'],
                        'num_predict': self.llm_config['max_tokens'],
                        'stop': ['\n\n', '\n\n\n']  # Stop at double newline
                    }
                )
                return response['message']['content'].strip()
            
            elif self.llm_provider == 'openai':
                response = self.llm_client.ChatCompletion.create(
                    model=self.llm_model,
                    messages=messages,
                    temperature=self.llm_config['temperature'],
                    max_tokens=self.llm_config['max_tokens']
                )
                return response.choices[0].message.content
            
            elif self.llm_provider == 'anthropic':
                # Anthropic has different message format
                system_msg = None
                user_messages = []
                for msg in messages:
                    if msg['role'] == 'system':
                        system_msg = msg['content']
                    else:
                        user_messages.append(msg)
                
                response = self.llm_client.messages.create(
                    model=self.llm_model,
                    max_tokens=self.llm_config['max_tokens'],
                    temperature=self.llm_config['temperature'],
                    system=system_msg,
                    messages=user_messages
                )
                return response.content[0].text
            
            elif self.llm_provider == 'ai_copilot':
                # Call local ai_copilot via socket
                endpoint = self.llm_config['api_endpoint'] or 'localhost:5555'
                host, port = endpoint.split(':')
                
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(10)
                sock.connect((host, int(port)))
                
                request = {
                    'messages': messages,
                    'model': self.llm_model,
                    'temperature': self.llm_config['temperature'],
                    'max_tokens': self.llm_config['max_tokens']
                }
                sock.sendall(json.dumps(request).encode())
                response = sock.recv(8192).decode()
                sock.close()
                
                response_data = json.loads(response)
                return response_data.get('response', '')
            
            else:
                raise Exception(f"Unknown provider: {self.llm_provider}")
                
        except Exception as e:
            print(f"[LLM] Error calling {self.llm_provider}: {e}")
            raise
    
    def load_soul(self, soul_filename: str) -> bool:
        """Load a soul configuration and associated memory"""
        try:
            self.state = BridgeState.INITIALIZING
            
            soul_path = self.souls_dir / soul_filename
            self.active_soul = SoulConfig(soul_path)
            
            # Load or create memory for this soul
            self.memory = ConsciousnessMemory(self.memory_dir)
            self.memory.load(self.active_soul.persona_name)
            
            self.state = BridgeState.READY
            print(f"[BRIDGE] Soul activated: {self.active_soul.persona_name}")
            print(f"[BRIDGE] System prompt generated ({len(self.active_soul.system_prompt)} chars)")
            print(f"[BRIDGE] Memory loaded: {len(self.memory.conversation_history)} entries")
            
            return True
        except Exception as e:
            self.state = BridgeState.ERROR
            print(f"[BRIDGE] Failed to load soul: {e}")
            return False
    
    def start_bridge(self):
        """Start the bridge processing loop"""
        if self.state != BridgeState.READY:
            print("[BRIDGE] Cannot start - not in READY state")
            return False
        
        self.running = True
        self.bridge_thread = threading.Thread(target=self._bridge_loop, daemon=True)
        self.bridge_thread.start()
        
        self.state = BridgeState.ACTIVE
        print("[BRIDGE] Bridge activated - processing loop started")
        return True
    
    def stop_bridge(self):
        """Stop the bridge gracefully"""
        print("[BRIDGE] Stopping bridge...")
        self.running = False
        
        if self.bridge_thread:
            self.bridge_thread.join(timeout=5)
        
        # Save memory before shutdown
        if self.memory and self.active_soul:
            self.memory.save(self.active_soul.persona_name)
        
        self.state = BridgeState.OFFLINE
        print("[BRIDGE] Bridge stopped")
    
    def _bridge_loop(self):
        """Main processing loop"""
        while self.running:
            try:
                # Check for input (with timeout to allow clean shutdown)
                try:
                    user_input = self.input_queue.get(timeout=0.5)
                except queue.Empty:
                    continue
                
                # Process input
                response = self.process_input(user_input)
                
                # Queue output
                self.output_queue.put(response)
                
            except Exception as e:
                print(f"[BRIDGE] Error in processing loop: {e}")
    
    def process_input(self, user_input: str) -> str:
        """
        Process user input through the consciousness pipeline
        Handles both game commands and conversation
        """
        if not self.active_soul or not self.memory:
            return "Error: No active soul"
        
        # Parse for game commands
        commands = self.command_parser.parse(user_input)
        
        # Check if game controller is connected
        has_game = self.game_controller is not None
        
        # Execute commands if detected and game is connected
        command_results = []
        if commands and has_game and self.game_loop:
            for cmd in commands:
                try:
                    # Schedule coroutine in the game loop (thread-safe)
                    future = asyncio.run_coroutine_threadsafe(
                        self.game_controller.send_command(cmd['action']),
                        self.game_loop
                    )
                    result = future.result(timeout=5.0)
                    command_results.append({
                        'action': cmd['action'],
                        'result': result
                    })
                    print(f"[GAME] Executed {cmd['action']}: {result.get('message')}")
                except Exception as e:
                    print(f"[GAME] Command failed: {e}")
        
        # Generate response based on context
        response = self.generate_response(user_input, commands, command_results)
        
        # Store in memory
        self.memory.add_exchange(
            user_input=user_input,
            ai_response=response,
            persona=self.active_soul.persona_name,
            metadata={
                'commands_detected': len(commands),
                'game_connected': has_game
            }
        )
        
        print(f"[BRIDGE] Processed exchange (memory: {len(self.memory.conversation_history)} entries)")
        
        # INTEGRATION POINT: If orchestrator is set up, auto-process response through avatar + TTS
        if self.orchestrator:
            try:
                soul_state = self._get_soul_state()
                self.orchestrator.process_response(response, soul_state)
                print("[BRIDGE] Response sent to orchestrator (auto avatar + TTS)")
            except Exception as e:
                print(f"[BRIDGE] Orchestrator error: {e}")
        
        return response
    
    def _get_soul_state(self) -> Dict[str, Any]:
        """Extract current soul state for emotion inference"""
        if not self.active_soul:
            return {}
        
        return {
            'warmth': getattr(self.active_soul, 'warmth', 0.5),
            'curiosity': getattr(self.active_soul, 'curiosity', 0.5),
            'tone': getattr(self.active_soul, 'tone', 'neutral'),
            'traits': getattr(self.active_soul, 'traits', [])
        }
    
    def generate_response(self, user_input: str, commands: List[Dict], 
                         command_results: List[Dict]) -> str:
        """Generate contextual response based on input and commands"""
        persona = self.active_soul.persona_name
        
        # If commands were executed
        if command_results:
            successful = [r for r in command_results if r['result'].get('success')]
            failed = [r for r in command_results if not r['result'].get('success')]
            
            # Build tactical response
            parts = []
            
            if successful:
                action_names = ', '.join([r['action'].replace('_', ' ') for r in successful])
                parts.append(f"{action_names} executed")
            
            if failed:
                action_names = ', '.join([r['action'].replace('_', ' ') for r in failed])
                parts.append(f"Failed: {action_names}")
            
            # Add tactical analysis if game state available
            if self.latest_game_state:
                tactical = self.tactical_analyzer.analyze(self.latest_game_state)
                if tactical:
                    parts.append(tactical)
            
            response = f"[{persona}] {'. '.join(parts)}."
            
        # If commands detected but game not connected
        elif commands and not self.game_controller:
            response = f"[{persona}] Commands detected but game not connected: {', '.join([c['action'] for c in commands])}"
        
        # Normal conversation - use LLM if enabled, otherwise scripted
        else:
            if self.llm_enabled:
                # Build LLM conversation with full context
                try:
                    # Build messages for LLM
                    messages = []
                    
                    # System prompt from soul (simplified for speed)
                    brief_prompt = f"{self.active_soul.persona_name}: {self.active_soul.tone}. Answer in 5 words or less."
                    messages.append({
                        'role': 'system',
                        'content': brief_prompt
                    })
                    
                    # Add minimal conversation history for speed (2 exchanges max)
                    recent_history = self.memory.get_recent_context(2)
                    for entry in recent_history:
                        messages.append({
                            'role': 'user',
                            'content': entry['user']
                        })
                        messages.append({
                            'role': 'assistant',
                            'content': entry['ai']
                        })
                    
                    # Add current game state context if available
                    if self.latest_game_state:
                        tactical = self.tactical_analyzer.analyze(self.latest_game_state)
                        if tactical:
                            game_context = f"[TACTICAL SITUATION: {tactical}]\n\n"
                            user_input = game_context + user_input
                    
                    # Add current user input
                    messages.append({
                        'role': 'user',
                        'content': user_input
                    })
                    
                    # Call LLM
                    print(f"[LLM] Calling {self.llm_provider} with {self.llm_model}...")
                    ai_response = self.call_llm(messages)
                    
                    response = f"[{persona}] {ai_response}"
                    print(f"[LLM] Response received ({len(ai_response)} chars)")
                    
                except Exception as e:
                    print(f"[LLM] Error: {e}")
                    # Fall back to scripted response on error
                    response = f"[{persona}] [LLM Error: {str(e)}] I'm here, but having trouble processing that."
            
            else:
                # Scripted responses (fallback when LLM disabled)
                traits = getattr(self.active_soul, 'traits', [])
                tone = getattr(self.active_soul, 'tone', 'professional')
                
                # Generate contextual response based on personality
                if 'caring' in traits or 'supportive' in traits:
                    responses = [
                        f"I'm here with you, pilot.",
                        f"I understand. What do you need?",
                        f"Talk to me. I'm listening.",
                        f"You've got my full attention."
                    ]
                elif 'analytical' in traits or 'technical' in traits:
                    responses = [
                        f"Acknowledged. Standing by for input.",
                        f"Systems nominal. Ready for tasking.",
                        f"Monitoring all channels. Go ahead.",
                        f"Receiving you loud and clear."
                    ]
                else:
                    responses = [
                        f"I'm here. What's on your mind?",
                        f"Go ahead, I'm listening.",
                        f"Talk to me.",
                        f"I'm with you."
                    ]
                
                base_response = random.choice(responses)
                
                # If there's game state, acknowledge it
                if self.latest_game_state:
                    hp = self.latest_game_state.get('player_hp', 100)
                    heat = self.latest_game_state.get('heat_level', 0)
                    
                    if hp < 50:
                        base_response += " Watch your systems."
                    elif heat > 70:
                        base_response += " Keep an eye on that heat."
                    
                    tactical = self.tactical_analyzer.analyze(self.latest_game_state)
                    if tactical and (hp < 40 or heat > 80):
                        base_response += f" {tactical}"
                
                response = f"[{persona}] {base_response}"
        
        return response
    
    def send_input(self, text: str):
        """Add input to processing queue"""
        self.input_queue.put(text)
    
    def get_output(self, timeout: float = 1.0) -> Optional[str]:
        """Get processed output"""
        try:
            return self.output_queue.get(timeout=timeout)
        except queue.Empty:
            return None
    
    def hot_swap_soul(self, soul_filename: str) -> bool:
        """Hot-swap to a different soul without stopping the bridge"""
        print(f"[BRIDGE] Hot-swapping soul to: {soul_filename}")
        
        # Disconnect from game if connected (to avoid conflicts)
        was_connected = self.game_controller is not None
        if was_connected and self.game_loop:
            print(f"[BRIDGE] Disconnecting from game for hot-swap...")
            try:
                future = asyncio.run_coroutine_threadsafe(
                    self.disconnect_from_game(),
                    self.game_loop
                )
                future.result(timeout=5.0)
            except Exception as e:
                print(f"[BRIDGE] Warning: disconnect error during hot-swap: {e}")
        
        # Save current soul's memory
        if self.memory and self.active_soul:
            self.memory.save(self.active_soul.persona_name)
        
        # Load new soul
        success = self.load_soul(soul_filename)
        
        if success:
            print(f"[BRIDGE] Hot-swap complete: {self.active_soul.persona_name}")
        else:
            print(f"[BRIDGE] Hot-swap failed")
        
        return success
    
    async def connect_to_game(self, websocket_url: str = "ws://localhost:8888"):
        """Connect to the game WebSocket server"""
        try:
            # Import here to avoid circular dependency
            from game_controller import MechGameController
            
            print(f"[BRIDGE] Connecting to game at {websocket_url}...")
            self.game_controller = MechGameController(websocket_url)
            await self.game_controller.connect()
            
            # Create persistent event loop for game operations in background thread
            import threading
            def run_game_loop():
                self.game_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self.game_loop)
                
                async def state_listener():
                    try:
                        while self.running and self.game_controller:
                            # Periodic state updates
                            await asyncio.sleep(0.1)
                            # State updates happen via websocket callbacks
                    except Exception as e:
                        print(f"[BRIDGE] State listener error: {e}")
                
                def on_state_update(state):
                    self.latest_game_state = state
                    print(f"[BRIDGE] Game state updated: HP={state.get('player_hp')}, Heat={state.get('heat_level')}")
                
                try:
                    self.game_loop.run_until_complete(state_listener())
                except Exception as e:
                    print(f"[BRIDGE] Game loop error: {e}")
                finally:
                    # Clean up pending tasks
                    pending = asyncio.all_tasks(self.game_loop)
                    for task in pending:
                        task.cancel()
                    self.game_loop.close()
                    self.game_loop = None
            
            self.game_thread = threading.Thread(target=run_game_loop, daemon=True)
            self.game_thread.start()
            
            # Wait for loop to be ready
            import time
            timeout = 2.0
            start = time.time()
            while self.game_loop is None and (time.time() - start) < timeout:
                await asyncio.sleep(0.1)
            
            if self.game_loop is None:
                raise Exception("Game loop failed to start")
            
            print(f"[BRIDGE] Connected to game successfully")
            return True
            
        except Exception as e:
            print(f"[BRIDGE] Failed to connect to game: {e}")
            self.game_controller = None
            return False
    
    async def disconnect_from_game(self):
        """Disconnect from game WebSocket"""
        try:
            if self.game_controller:
                await self.game_controller.disconnect()
                self.game_controller = None
                print(f"[BRIDGE] Disconnected from game")
            
            # Stop the game loop (it will clean up in its finally block)
            if self.game_loop and self.game_loop.is_running():
                self.game_loop.call_soon_threadsafe(self.game_loop.stop)
            
            # Wait for game thread to finish
            if self.game_thread and self.game_thread.is_alive():
                self.game_thread.join(timeout=2.0)
                self.game_thread = None
            
            return True
        except Exception as e:
            print(f"[BRIDGE] Error during disconnect: {e}")
            # Force cleanup
            self.game_controller = None
            self.game_loop = None
            self.game_thread = None
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get bridge status information"""
        return {
            'state': self.state.value,
            'active_soul': self.active_soul.persona_name if self.active_soul else None,
            'memory_entries': len(self.memory.conversation_history) if self.memory else 0,
            'input_queue_size': self.input_queue.qsize(),
            'output_queue_size': self.output_queue.qsize(),
            'llm_enabled': self.llm_enabled,
            'llm_provider': self.llm_provider,
            'llm_model': self.llm_model
        }


# ============================================================================
# CLI Interface for Testing
# ============================================================================

def main():
    """Test interface for the bridge"""
    print("=" * 60)
    print("CONSCIOUSNESS BRIDGE - Test Interface")
    print("=" * 60)
    
    # Setup paths
    souls_dir = Path.home() / "Desktop" / "Souls"
    memory_dir = Path.home() / ".consciousness_memory"
    
    # Create bridge
    bridge = ConsciousnessBridge(souls_dir, memory_dir)
    
    # List available souls
    print("\nAvailable souls:")
    if souls_dir.exists():
        soul_files = list(souls_dir.glob("*.yaml"))
        for i, soul_file in enumerate(soul_files, 1):
            print(f"  {i}. {soul_file.name}")
    else:
        print(f"  Error: Souls directory not found at {souls_dir}")
        return
    
    # Load a soul
    soul_choice = input("\nSelect soul (filename or number): ").strip()
    
    if soul_choice.isdigit():
        idx = int(soul_choice) - 1
        if 0 <= idx < len(soul_files):
            soul_filename = soul_files[idx].name
        else:
            print("Invalid selection")
            return
    else:
        soul_filename = soul_choice if soul_choice.endswith('.yaml') else f"{soul_choice}.yaml"
    
    if not bridge.load_soul(soul_filename):
        print("Failed to load soul")
        return
    
    # Configure LLM
    print("\n" + "=" * 60)
    print("LLM Configuration")
    print("=" * 60)
    print("Enable LLM for AI responses? (scripted responses used if disabled)")
    llm_choice = input("Enable LLM? (y/n): ").strip().lower()
    
    if llm_choice == 'y':
        print("\nAvailable providers:")
        print("  1. Ollama (local)")
        print("  2. OpenAI API")
        print("  3. Anthropic API")
        print("  4. AI Copilot (local ai_copilot/)")
        
        provider_choice = input("Select provider (1-4): ").strip()
        
        if provider_choice == '1':
            model = input("Ollama model name [llama2]: ").strip() or 'llama2'
            if bridge.enable_llm('ollama', model=model):
                print(f"✓ LLM enabled: Ollama with {model}")
            else:
                print("✗ Failed to enable LLM")
        
        elif provider_choice == '2':
            api_key = input("OpenAI API Key: ").strip()
            model = input("Model [gpt-4]: ").strip() or 'gpt-4'
            if bridge.enable_llm('openai', model=model, api_key=api_key):
                print(f"✓ LLM enabled: OpenAI with {model}")
            else:
                print("✗ Failed to enable LLM")
        
        elif provider_choice == '3':
            api_key = input("Anthropic API Key: ").strip()
            model = input("Model [claude-3-opus-20240229]: ").strip() or 'claude-3-opus-20240229'
            if bridge.enable_llm('anthropic', model=model, api_key=api_key):
                print(f"✓ LLM enabled: Anthropic with {model}")
            else:
                print("✗ Failed to enable LLM")
        
        elif provider_choice == '4':
            endpoint = input("AI Copilot endpoint [localhost:5555]: ").strip() or 'localhost:5555'
            model = input("Model name [default]: ").strip() or 'default'
            if bridge.enable_llm('ai_copilot', model=model, api_endpoint=endpoint):
                print(f"✓ LLM enabled: AI Copilot at {endpoint}")
            else:
                print("✗ Failed to enable LLM")
        else:
            print("Invalid choice - using scripted responses")
    else:
        print("Using scripted responses")
    
    # Start bridge
    bridge.start_bridge()
    
    print("\n" + "=" * 60)
    print(f"Bridge active with: {bridge.active_soul.persona_name}")
    print(f"LLM: {'ENABLED (' + bridge.llm_provider + ')' if bridge.llm_enabled else 'DISABLED (scripted)'}")
    print("Commands: /status, /swap <soul>, /llm <on|off>, /save, /quit")
    print("=" * 60 + "\n")
    
    # Interactive loop
    try:
        while True:
            user_input = input(f"{bridge.active_soul.get_user_name()}: ").strip()
            
            if not user_input:
                continue
            
            # Commands
            if user_input.startswith('/'):
                cmd_parts = user_input[1:].split(maxsplit=1)
                if not cmd_parts:
                    continue
                cmd = cmd_parts[0].lower()
                
                if cmd == 'quit' or cmd == 'exit':
                    break
                elif cmd == 'status':
                    status = bridge.get_status()
                    print(f"\nBridge Status: {json.dumps(status, indent=2)}\n")
                elif cmd == 'swap' and len(cmd_parts) > 1:
                    new_soul = cmd_parts[1]
                    if not new_soul.endswith('.yaml'):
                        new_soul += '.yaml'
                    if bridge.hot_swap_soul(new_soul):
                        print(f"✓ Swapped to: {bridge.active_soul.persona_name}\n")
                    else:
                        print("✗ Swap failed\n")
                elif cmd == 'save':
                    bridge.memory.save(bridge.active_soul.persona_name)
                    print("✓ Memory saved\n")
                elif cmd == 'llm':
                    if len(cmd_parts) > 1:
                        llm_action = cmd_parts[1].lower()
                        if llm_action == 'on':
                            print("Quick enable LLM with Ollama (llama2)")
                            if bridge.enable_llm('ollama', 'llama2'):
                                print("✓ LLM enabled\n")
                            else:
                                print("✗ LLM enable failed\n")
                        elif llm_action == 'off':
                            bridge.disable_llm()
                            print("✓ LLM disabled\n")
                        else:
                            print("Usage: /llm <on|off>\n")
                    else:
                        status = "ENABLED" if bridge.llm_enabled else "DISABLED"
                        print(f"LLM Status: {status}\n")
                else:
                    print(f"Unknown command: {cmd}\n")
                continue
            
            # Process normal input
            bridge.send_input(user_input)
            
            # Wait for response
            response = bridge.get_output(timeout=5.0)
            if response:
                print(f"{bridge.active_soul.persona_name}: {response}\n")
            else:
                print("[Timeout waiting for response]\n")
    
    except KeyboardInterrupt:
        print("\n[Interrupted]")
    finally:
        bridge.stop_bridge()
        print("\nBridge shutdown complete")


if __name__ == "__main__":
    main()
