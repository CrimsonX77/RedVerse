#!/usr/bin/env python3
"""
embodiment_mcp_server.py — MCP Server for AI Character Control
Exposes embodiment animation tools via Model Context Protocol.

AI agents (Claude, navigator_buddy, etc.) can call tools to:
  • Play animations on the 3D character
  • Set facial expressions
  • Control camera angles
  • Trigger visual effects
  • Execute composite action sequences
  • Query available capabilities

Commands are forwarded to the embodiment_server via HTTP,
which broadcasts them to connected viewers via WebSocket.

Usage:
  python embodiment_mcp_server.py                    # stdio mode (default)
  python embodiment_mcp_server.py --transport sse    # SSE mode for web
  
MCP Config (add to claude_desktop_config.json or VS Code settings):
  {
    "mcpServers": {
      "embodiment": {
        "command": "python",
        "args": ["/path/to/embodiment_mcp_server.py"],
        "env": {"EMBODIMENT_SERVER": "http://localhost:5000"}
      }
    }
  }
"""

import os
import sys
import json
import logging
import asyncio
import tempfile
import base64
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

import yaml
import requests

# ═══════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════

BASE_DIR = Path(__file__).parent.resolve()
MAPPING_FILE = BASE_DIR / "embodiment_mapping.yaml"
EMBODIMENT_SERVER = os.getenv("EMBODIMENT_SERVER", "http://localhost:5000")
MEMORY_DB_PATH = os.getenv("MEMORY_DB_PATH", str(BASE_DIR / "navigator-buddy" / "luna_memory.db"))

# Add navigator-buddy to sys.path for luna_memory import
_nav_dir = str(BASE_DIR / "navigator-buddy")
if _nav_dir not in sys.path:
    sys.path.insert(0, _nav_dir)

# Add user_tools to sys.path for VisionEngine
_user_tools_dir = str(BASE_DIR / "user_tools")
if _user_tools_dir not in sys.path:
    sys.path.insert(0, _user_tools_dir)

# VisionEngine — cognitive vision analysis
try:
    from vision_engine import VisionEngine
    HAS_VISION_ENGINE = True
except ImportError:
    HAS_VISION_ENGINE = False
    VisionEngine = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("embodiment-mcp")

# ═══════════════════════════════════════════════════════════════
# RedVerse imports (narrator + recorder utilities)
# ═══════════════════════════════════════════════════════════════

# Narrator functions — speaker detection & TTS rendering
try:
    from redverse_narrator import (
        load_config as narrator_load_config,
        save_config as narrator_save_config,
        detect_speakers_ollama,
        detect_speakers_claude,
        detect_speakers_openai,
        render_segment,
        get_api_key,
        DEFAULT_EDGE_VOICES,
        HAS_EDGE_TTS,
        HAS_PYTTSX3,
        HAS_PYDUB,
        HAS_OLLAMA,
    )
    HAS_NARRATOR = True
    log.info("RedVerse Narrator module loaded")
except ImportError as e:
    HAS_NARRATOR = False
    log.warning("RedVerse Narrator not available: %s", e)

# Recorder utilities — audio device listing
try:
    import sounddevice as sd
    HAS_SOUNDDEVICE = True
    log.info("sounddevice available for audio device listing")
except ImportError:
    HAS_SOUNDDEVICE = False
    log.warning("sounddevice not available; audio device tools disabled")

# ═══════════════════════════════════════════════════════════════
# Load mapping for tool descriptions
# ═══════════════════════════════════════════════════════════════

def load_mapping() -> dict:
    if MAPPING_FILE.exists():
        with open(MAPPING_FILE) as f:
            return yaml.safe_load(f) or {}
    return {}

mapping = load_mapping()

# ═══════════════════════════════════════════════════════════════
# Helper: Forward command to embodiment server
# ═══════════════════════════════════════════════════════════════

def send_command(cmd: dict) -> dict:
    """Send a command to the embodiment server via REST API."""
    try:
        resp = requests.post(
            f"{EMBODIMENT_SERVER}/api/command",
            json=cmd,
            timeout=5
        )
        return resp.json()
    except requests.ConnectionError:
        return {"error": "Embodiment server not running. Start it with: python embodiment_server.py"}
    except Exception as e:
        return {"error": str(e)}

def send_sequence(commands: list, delay: float = 0.5) -> dict:
    """Send a command sequence to the embodiment server."""
    try:
        resp = requests.post(
            f"{EMBODIMENT_SERVER}/api/sequence",
            json={"commands": commands, "delay": delay},
            timeout=5
        )
        return resp.json()
    except requests.ConnectionError:
        return {"error": "Embodiment server not running. Start it with: python embodiment_server.py"}
    except Exception as e:
        return {"error": str(e)}

def send_composite(name: str) -> dict:
    """Trigger a composite action."""
    try:
        resp = requests.post(
            f"{EMBODIMENT_SERVER}/api/composite/{name}",
            timeout=5
        )
        return resp.json()
    except requests.ConnectionError:
        return {"error": "Embodiment server not running."}
    except Exception as e:
        return {"error": str(e)}

def get_capabilities() -> dict:
    """Get viewer capabilities."""
    try:
        resp = requests.get(f"{EMBODIMENT_SERVER}/api/capabilities", timeout=5)
        return resp.json()
    except:
        return {"error": "Could not reach embodiment server"}

def get_status() -> dict:
    """Get server status."""
    try:
        resp = requests.get(f"{EMBODIMENT_SERVER}/api/status", timeout=5)
        return resp.json()
    except:
        return {"error": "Could not reach embodiment server"}

# ═══════════════════════════════════════════════════════════════
# MCP Server Implementation (JSON-RPC over stdio)
# ═══════════════════════════════════════════════════════════════

class EmbodimentMCPServer:
    """Lightweight MCP server implementing the JSON-RPC protocol over stdio."""

    def __init__(self):
        self.tools = self._define_tools()
        self.tool_handlers = {
            "play_animation": self._handle_play_animation,
            "set_expression": self._handle_set_expression,
            "move_camera": self._handle_move_camera,
            "trigger_effect": self._handle_trigger_effect,
            "run_composite": self._handle_run_composite,
            "get_capabilities": self._handle_get_capabilities,
            "send_raw_command": self._handle_send_raw_command,
            # Memory tools
            "store_memory": self._handle_store_memory,
            "recall_memories": self._handle_recall_memories,
            "get_memory_stats": self._handle_get_memory_stats,
            # RedVerse Narrator tools
            "redverse_narrate": self._handle_redverse_narrate,
            "redverse_list_voices": self._handle_redverse_list_voices,
            "redverse_narrator_config": self._handle_redverse_narrator_config,
            # RedVerse Recorder tools
            "redverse_list_audio_devices": self._handle_redverse_list_audio_devices,
            "redverse_recorder_info": self._handle_redverse_recorder_info,
            # Vision tools
            "vision_analyze": self._handle_vision_analyze,
            "vision_recall": self._handle_vision_recall,
            "vision_recent": self._handle_vision_recent,
            "vision_stats": self._handle_vision_stats,
        }

        # Thread pool for async vision analysis
        self._vision_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="vision")

        # Persistent memory (shared with navigator-buddy via same DB)
        self._memory = None
        try:
            from luna_memory import MemoryManager
            self._memory = MemoryManager(MEMORY_DB_PATH)
            log.info("Memory system connected: %s", MEMORY_DB_PATH)
        except ImportError:
            log.warning("luna_memory module not available; memory tools disabled")
        except Exception as e:
            log.warning("Memory system unavailable: %s", e)

        # Visual memory database
        self._visual_memory = None
        try:
            from visual_memory import VisualMemoryDB
            _vm_path = os.getenv(
                "VISUAL_MEMORY_DB_PATH",
                str(BASE_DIR / "navigator-buddy" / "visual_memory.db"),
            )
            self._visual_memory = VisualMemoryDB(_vm_path)
            log.info("Visual memory connected: %s", _vm_path)
        except ImportError:
            log.warning("visual_memory module not available; vision tools disabled")
        except Exception as e:
            log.warning("Visual memory unavailable: %s", e)

        # Cognitive VisionEngine (replaces simple Ollama-only analysis)
        self._vision_engine = None
        if HAS_VISION_ENGINE:
            try:
                self._vision_engine = VisionEngine(
                    db_path=os.getenv(
                        "VISUAL_MEMORY_DB_PATH",
                        str(BASE_DIR / "navigator-buddy" / "visual_memory.db"),
                    ),
                )
                log.info("VisionEngine loaded (cognitive analysis enabled)")
            except Exception as e:
                log.warning("VisionEngine failed to initialize: %s", e)

    def _define_tools(self) -> list:
        """Define available MCP tools."""
        gestures = list(mapping.get("gestures", {}).keys())
        expressions_list = list(mapping.get("expressions", {}).keys())
        composites = list(mapping.get("composites", {}).keys())
        camera_presets = list(mapping.get("camera_presets", {}).keys())

        return [
            {
                "name": "play_animation",
                "description": (
                    f"Play an animation on the 3D character. "
                    f"Available animations: {', '.join(gestures) if gestures else 'check capabilities'}. "
                    f"Controls a rigged 3D model with skeletal animations."
                ),
                "inputSchema": {
                    "type": "object",
                    "required": ["animation_name"],
                    "properties": {
                        "animation_name": {
                            "type": "string",
                            "description": f"Animation to play. Options: {', '.join(gestures)}"
                        },
                        "fade_in": {
                            "type": "number",
                            "description": "Fade-in duration in seconds (default: 0.4)",
                            "default": 0.4
                        },
                        "loop": {
                            "type": "boolean",
                            "description": "Whether to loop the animation (default: true)",
                            "default": True
                        },
                        "time_scale": {
                            "type": "number",
                            "description": "Playback speed multiplier (default: 1.0)",
                            "default": 1.0
                        }
                    }
                }
            },
            {
                "name": "set_expression",
                "description": (
                    f"Set a facial expression on the character using morph targets. "
                    f"Available expressions: {', '.join(expressions_list)}."
                ),
                "inputSchema": {
                    "type": "object",
                    "required": ["expression"],
                    "properties": {
                        "expression": {
                            "type": "string",
                            "description": f"Expression name. Options: {', '.join(expressions_list)}"
                        },
                        "intensity": {
                            "type": "number",
                            "description": "Expression intensity from 0.0 to 1.0 (default: 0.8)",
                            "default": 0.8
                        },
                        "duration": {
                            "type": "number",
                            "description": "Transition duration in seconds (default: 0.4)",
                            "default": 0.4
                        }
                    }
                }
            },
            {
                "name": "move_camera",
                "description": (
                    f"Move the viewer camera to a preset or custom position. "
                    f"Presets: {', '.join(camera_presets)}. "
                    f"Or specify custom position/target as [x, y, z] arrays."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "preset": {
                            "type": "string",
                            "description": f"Camera preset name. Options: {', '.join(camera_presets)}"
                        },
                        "position": {
                            "type": "array",
                            "items": {"type": "number"},
                            "description": "Custom camera position [x, y, z]"
                        },
                        "target": {
                            "type": "array",
                            "items": {"type": "number"},
                            "description": "Camera look-at target [x, y, z]"
                        },
                        "duration": {
                            "type": "number",
                            "description": "Transition duration in seconds",
                            "default": 1.0
                        }
                    }
                }
            },
            {
                "name": "trigger_effect",
                "description": (
                    "Trigger a visual effect on the character. "
                    "Effects: pulse (crimson energy burst), glow (emissive toggle), "
                    "blink (eye blink), particles (ambient particles)."
                ),
                "inputSchema": {
                    "type": "object",
                    "required": ["effect"],
                    "properties": {
                        "effect": {
                            "type": "string",
                            "enum": ["pulse", "glow", "blink", "particles"],
                            "description": "Effect to trigger"
                        },
                        "action": {
                            "type": "string",
                            "enum": ["trigger", "enable", "disable", "toggle"],
                            "description": "Action to perform (default: trigger)",
                            "default": "trigger"
                        },
                        "color": {
                            "type": "string",
                            "description": "Hex color for pulse effect (default: #ff22aa)",
                            "default": "#ff22aa"
                        }
                    }
                }
            },
            {
                "name": "run_composite",
                "description": (
                    f"Run a pre-built composite action sequence. "
                    f"Available composites: {', '.join(composites)}. "
                    f"Each composite is a choreographed sequence of animations, "
                    f"expressions, effects, and camera movements."
                ),
                "inputSchema": {
                    "type": "object",
                    "required": ["name"],
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": f"Composite action name. Options: {', '.join(composites)}"
                        }
                    }
                }
            },
            {
                "name": "get_capabilities",
                "description": (
                    "Query the current capabilities of the connected 3D character viewer. "
                    "Returns available animations, morph targets, bone names, and effects."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "send_raw_command",
                "description": (
                    "Send a raw JSON command directly to the embodiment viewer. "
                    "Use animation-schema.json format. For advanced use when "
                    "pre-built tools don't cover the use case."
                ),
                "inputSchema": {
                    "type": "object",
                    "required": ["command"],
                    "properties": {
                        "command": {
                            "type": "object",
                            "description": "Raw command object matching animation-schema.json"
                        }
                    }
                }
            },
            # ── Memory tools ──────────────────────────────────
            {
                "name": "store_memory",
                "description": (
                    "Store a fact, preference, or insight in Luna's persistent memory. "
                    "Memories persist across sessions and can be recalled later."
                ),
                "inputSchema": {
                    "type": "object",
                    "required": ["content", "type"],
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "The fact or insight to remember"
                        },
                        "type": {
                            "type": "string",
                            "enum": ["semantic", "procedural", "episodic"],
                            "description": "Memory type: semantic (facts), procedural (how-to), episodic (events)"
                        },
                        "tags": {
                            "type": "string",
                            "description": "Comma-separated tags for categorization"
                        },
                        "importance": {
                            "type": "number",
                            "description": "Importance score 0.0-1.0 (default: 0.5)",
                            "default": 0.5
                        }
                    }
                }
            },
            {
                "name": "recall_memories",
                "description": (
                    "Search Luna's persistent memory for relevant facts, preferences, "
                    "or past interactions. Returns ranked results."
                ),
                "inputSchema": {
                    "type": "object",
                    "required": ["query"],
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query (keywords or natural language)"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Max results to return (default: 5)",
                            "default": 5
                        },
                        "type": {
                            "type": "string",
                            "enum": ["semantic", "procedural", "episodic"],
                            "description": "Filter by memory type (optional)"
                        }
                    }
                }
            },
            {
                "name": "get_memory_stats",
                "description": "Get statistics about Luna's persistent memory system.",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            },
            # ── RedVerse Narrator tools ───────────────────────
            {
                "name": "redverse_narrate",
                "description": (
                    "Parse prose text for character dialogue, detect speakers using AI, "
                    "render each segment with text-to-speech (edge-tts / pyttsx3 / GPT-SoVITS), "
                    "and combine into a single MP3 file. Returns the output file path. "
                    "Supports multiple characters with individual voice assignments."
                ),
                "inputSchema": {
                    "type": "object",
                    "required": ["text"],
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "The prose/story text to narrate. Can include dialogue in quotes."
                        },
                        "output_path": {
                            "type": "string",
                            "description": "Output MP3 file path (default: ~/Music/RedVerse/narration_<timestamp>.mp3)"
                        },
                        "model": {
                            "type": "string",
                            "description": "Ollama model for speaker detection (default: from narrator config, e.g. qwen2.5:3b)"
                        },
                        "silence_ms": {
                            "type": "integer",
                            "description": "Silence between segments in milliseconds (default: 400)",
                            "default": 400
                        }
                    }
                }
            },
            {
                "name": "redverse_list_voices",
                "description": (
                    "List available text-to-speech voices for the RedVerse Narrator. "
                    "Returns voice names grouped by TTS engine (edge-tts, pyttsx3, GPT-SoVITS). "
                    "Use these voice names when configuring character voices."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "engine": {
                            "type": "string",
                            "enum": ["edge-tts", "pyttsx3", "gptsovits", "all"],
                            "description": "Which TTS engine to list voices for (default: all)",
                            "default": "all"
                        }
                    }
                }
            },
            {
                "name": "redverse_narrator_config",
                "description": (
                    "Get or update the RedVerse Narrator configuration. "
                    "Returns current config if no updates provided. "
                    "Can update character voice assignments, default engine, Ollama model, etc."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["get", "set"],
                            "description": "Get current config or set values (default: get)",
                            "default": "get"
                        },
                        "updates": {
                            "type": "object",
                            "description": "Config fields to update (only used with action=set). Keys: default_engine, ollama_model, ollama_url, gptsovits_url, output_dir, silence_ms, characters"
                        }
                    }
                }
            },
            # ── RedVerse Recorder tools ───────────────────────
            {
                "name": "redverse_list_audio_devices",
                "description": (
                    "List available audio input devices for voice recording. "
                    "Returns device names, IDs, sample rates, and channel counts. "
                    "Use to identify the correct microphone for recording."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "input_only": {
                            "type": "boolean",
                            "description": "Only list input (microphone) devices (default: true)",
                            "default": True
                        }
                    }
                }
            },
            {
                "name": "redverse_recorder_info",
                "description": (
                    "Get information about the RedVerse Voice Recorder capabilities. "
                    "Returns available features, supported formats, and system status "
                    "(e.g. whether noise reduction, pydub export, etc. are available)."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            },
            # ── Vision tools ──────────────────────────────────
            {
                "name": "vision_analyze",
                "description": (
                    "Analyze an image using Ollama vision models. Sends the image "
                    "to a multimodal LLM for detailed description, and stores the "
                    "result in Luna's visual memory database for later recall. "
                    "Runs asynchronously in a worker thread."
                ),
                "inputSchema": {
                    "type": "object",
                    "required": ["image_path"],
                    "properties": {
                        "image_path": {
                            "type": "string",
                            "description": "Absolute path to the image file to analyze"
                        },
                        "prompt": {
                            "type": "string",
                            "description": "Custom prompt for the vision model (default: 'Describe this image in detail.')",
                            "default": "Describe this image in detail."
                        },
                        "model": {
                            "type": "string",
                            "description": "Ollama vision model to use (default: llava:7b)",
                            "default": "llava:7b"
                        },
                        "tags": {
                            "type": "string",
                            "description": "Comma-separated tags for categorization"
                        }
                    }
                }
            },
            {
                "name": "vision_recall",
                "description": (
                    "Search Luna's visual memory for previously analyzed images. "
                    "Returns captions, OCR text, and summaries from past analyses. "
                    "Search by keyword, description, or image path."
                ),
                "inputSchema": {
                    "type": "object",
                    "required": ["query"],
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query (keywords or natural language)"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Max results to return (default: 5)",
                            "default": 5
                        },
                        "image_path": {
                            "type": "string",
                            "description": "Filter by exact image path (optional)"
                        }
                    }
                }
            },
            {
                "name": "vision_recent",
                "description": (
                    "List the most recently analyzed images from visual memory."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "integer",
                            "description": "Number of recent entries (default: 10)",
                            "default": 10
                        }
                    }
                }
            },
            {
                "name": "vision_stats",
                "description": "Get statistics about Luna's visual memory database.",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            }
        ]

    # ─── Tool Handlers ────────────────────────────────────────

    def _handle_play_animation(self, args: dict) -> str:
        name = args["animation_name"]
        cmd = {
            "type": "animation",
            "action": name,
            "params": {
                "fadeIn": args.get("fade_in", 0.4),
                "loop": args.get("loop", True),
                "timeScale": args.get("time_scale", 1.0)
            }
        }
        result = send_command(cmd)
        if "error" in result:
            return f"Error: {result['error']}"
        return f"Playing animation: {name}"

    def _handle_set_expression(self, args: dict) -> str:
        expression = args["expression"]
        cmd = {
            "type": "expression",
            "expression": expression,
            "intensity": args.get("intensity", 0.8),
            "duration": args.get("duration", 0.4)
        }
        result = send_command(cmd)
        if "error" in result:
            return f"Error: {result['error']}"
        return f"Expression set: {expression} (intensity: {args.get('intensity', 0.8)})"

    def _handle_move_camera(self, args: dict) -> str:
        preset = args.get("preset")
        if preset:
            presets = mapping.get("camera_presets", {})
            if preset in presets:
                p = presets[preset]
                cmd = {
                    "type": "camera",
                    "action": "zoom",
                    "position": p.get("position"),
                    "target": p.get("target"),
                    "duration": args.get("duration", 1.0)
                }
            else:
                return f"Unknown preset: {preset}. Available: {', '.join(presets.keys())}"
        else:
            cmd = {
                "type": "camera",
                "action": "zoom" if args.get("position") else "focus",
                "duration": args.get("duration", 1.0)
            }
            if args.get("position"):
                cmd["position"] = args["position"]
            if args.get("target"):
                cmd["target"] = args["target"]

        result = send_command(cmd)
        if "error" in result:
            return f"Error: {result['error']}"
        return f"Camera moved to: {preset or 'custom position'}"

    def _handle_trigger_effect(self, args: dict) -> str:
        effect = args["effect"]
        cmd = {
            "type": "effect",
            "effect": effect,
            "action": args.get("action", "trigger"),
            "params": {}
        }
        if args.get("color"):
            cmd["params"]["color"] = args["color"]
        
        result = send_command(cmd)
        if "error" in result:
            return f"Error: {result['error']}"
        return f"Effect triggered: {effect}"

    def _handle_run_composite(self, args: dict) -> str:
        name = args["name"]
        result = send_composite(name)
        if "error" in result:
            return f"Error: {result['error']}"
        return f"Running composite: {name} ({result.get('commands', '?')} commands)"

    def _handle_get_capabilities(self, args: dict) -> str:
        caps = get_capabilities()
        if "error" in caps:
            status = get_status()
            return json.dumps({"status": status, "error": caps["error"]}, indent=2)
        return json.dumps(caps, indent=2)

    def _handle_send_raw_command(self, args: dict) -> str:
        cmd = args["command"]
        result = send_command(cmd)
        if "error" in result:
            return f"Error: {result['error']}"
        return f"Command sent: {json.dumps(cmd)}"

    # ─── Memory Tool Handlers ─────────────────────────────────

    def _handle_store_memory(self, args: dict) -> str:
        if not self._memory:
            return "Error: Memory system not available"
        content = args["content"]
        mem_type = args.get("type", "semantic")
        tags = args.get("tags", "")
        importance = args.get("importance", 0.5)
        row_id = self._memory.store(
            mem_type=mem_type,
            content=content,
            importance=importance,
            tags=tags,
        )
        return f"Memory stored (id: {row_id}, type: {mem_type}): {content}"

    def _handle_recall_memories(self, args: dict) -> str:
        if not self._memory:
            return "Error: Memory system not available"
        query = args["query"]
        limit = args.get("limit", 5)
        type_filter = args.get("type")
        results = self._memory.recall(query, limit=limit, type_filter=type_filter)
        if not results:
            return f"No memories found for: {query}"
        lines = [f"Found {len(results)} memories:"]
        for m in results:
            line = f"  [{m.get('type', '?')}] {m['content']}"
            if m.get("tags"):
                line += f" (tags: {m['tags']})"
            lines.append(line)
        return "\n".join(lines)

    def _handle_get_memory_stats(self, args: dict) -> str:
        if not self._memory:
            return "Error: Memory system not available"
        stats = self._memory.get_stats()
        return json.dumps(stats, indent=2)

    # ─── RedVerse Narrator Handlers ───────────────────────────

    def _handle_redverse_narrate(self, args: dict) -> str:
        if not HAS_NARRATOR:
            return "Error: RedVerse Narrator module not available. Ensure redverse_narrator.py is in the same directory."

        text = args.get("text", "").strip()
        if not text:
            return "Error: No text provided for narration"

        cfg = narrator_load_config()

        # Override model if specified
        if args.get("model"):
            cfg["ollama_model"] = args["model"]

        # Override silence
        if args.get("silence_ms") is not None:
            cfg["silence_ms"] = args["silence_ms"]

        # Output path
        import time as _time
        output_path = args.get("output_path") or os.path.join(
            cfg.get("output_dir", str(Path.home() / "Music" / "RedVerse")),
            f"narration_{int(_time.time())}.mp3"
        )
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        char_names = [c["name"] for c in cfg["characters"]]
        char_map = {c["name"]: c for c in cfg["characters"]}
        narrator = char_map.get("Narrator", cfg["characters"][0])

        # ── 1. Detect speakers ──
        segments = None
        errors = []

        if HAS_OLLAMA:
            try:
                segments = detect_speakers_ollama(
                    text, char_names,
                    cfg.get("ollama_model", "qwen2.5:3b"),
                    cfg.get("ollama_url", "http://localhost:11434"),
                )
            except Exception as e:
                errors.append(f"Ollama: {e}")

        if segments is None:
            api = cfg.get("external_api", "claude")
            key = get_api_key(api)
            if key:
                try:
                    if api == "claude":
                        segments = detect_speakers_claude(text, char_names, key)
                    elif api == "openai":
                        segments = detect_speakers_openai(text, char_names, key)
                except Exception as e:
                    errors.append(f"{api}: {e}")

        if segments is None:
            segments = [{"speaker": "Narrator", "text": text}]
            log.warning("Speaker detection failed (%s), using Narrator voice", "; ".join(errors))

        # ── 2. Render each segment ──
        tmp_dir = tempfile.mkdtemp(prefix="redverse_mcp_")
        audio_files = []

        for i, seg in enumerate(segments):
            name = seg.get("speaker", "Narrator")
            char = char_map.get(name, narrator)
            try:
                path = render_segment(seg["text"], char, cfg, tmp_dir, i)
                audio_files.append(path)
            except Exception as e:
                log.error("Failed to render segment %d (%s): %s", i, name, e)
                errors.append(f"Render segment {i} ({name}): {e}")

        if not audio_files:
            return f"Error: No segments rendered successfully. Errors: {'; '.join(errors)}"

        # ── 3. Combine with pydub ──
        if HAS_PYDUB:
            try:
                from pydub import AudioSegment
                silence = AudioSegment.silent(duration=cfg.get("silence_ms", 400))
                combined = AudioSegment.empty()
                for f in audio_files:
                    seg_audio = AudioSegment.from_file(f)
                    if len(combined) > 0:
                        combined += silence
                    combined += seg_audio
                combined.export(output_path, format="mp3")
            except Exception as e:
                return f"Error combining audio: {e}"
        else:
            # Fallback: copy first segment only
            import shutil
            if audio_files:
                shutil.copy2(audio_files[0], output_path)
                if len(audio_files) > 1:
                    errors.append("pydub not available — only first segment exported")

        result = {
            "output_file": output_path,
            "segments": len(segments),
            "characters_detected": list(set(s.get("speaker", "Narrator") for s in segments)),
            "tts_engine": cfg.get("default_engine", "edge-tts"),
        }
        if errors:
            result["warnings"] = errors
        return json.dumps(result, indent=2)

    def _handle_redverse_list_voices(self, args: dict) -> str:
        if not HAS_NARRATOR:
            return "Error: RedVerse Narrator module not available"

        engine = args.get("engine", "all")
        voices = {}

        if engine in ("edge-tts", "all"):
            voices["edge-tts"] = {
                "available": HAS_EDGE_TTS,
                "voices": DEFAULT_EDGE_VOICES if HAS_EDGE_TTS else [],
                "note": "Microsoft Edge neural voices. High quality, requires internet."
            }

        if engine in ("pyttsx3", "all"):
            pyttsx3_voices = []
            if HAS_PYTTSX3:
                try:
                    import pyttsx3
                    eng = pyttsx3.init()
                    for v in eng.getProperty("voices"):
                        pyttsx3_voices.append({"id": v.id, "name": v.name})
                    eng.stop()
                except Exception:
                    pass
            voices["pyttsx3"] = {
                "available": HAS_PYTTSX3,
                "voices": pyttsx3_voices,
                "note": "Local offline TTS. Lower quality but no internet needed."
            }

        if engine in ("gptsovits", "all"):
            cfg = narrator_load_config()
            voices["gptsovits"] = {
                "available": True,
                "endpoint": cfg.get("gptsovits_url", "http://localhost:9880"),
                "voices": [],
                "note": "GPU-accelerated voice cloning. Requires GPT-SoVITS server running."
            }

        return json.dumps(voices, indent=2)

    def _handle_redverse_narrator_config(self, args: dict) -> str:
        if not HAS_NARRATOR:
            return "Error: RedVerse Narrator module not available"

        action = args.get("action", "get")
        cfg = narrator_load_config()

        if action == "get":
            return json.dumps(cfg, indent=2)

        elif action == "set":
            updates = args.get("updates", {})
            if not updates:
                return "Error: No updates provided"

            allowed_keys = {
                "default_engine", "ollama_model", "ollama_url",
                "gptsovits_url", "output_dir", "silence_ms",
                "external_api", "characters"
            }
            applied = []
            for key, val in updates.items():
                if key in allowed_keys:
                    cfg[key] = val
                    applied.append(key)

            if applied:
                narrator_save_config(cfg)
                return f"Config updated: {', '.join(applied)}"
            else:
                return f"No valid keys to update. Allowed: {', '.join(sorted(allowed_keys))}"

        return f"Unknown action: {action}. Use 'get' or 'set'."

    # ─── RedVerse Recorder Handlers ───────────────────────────

    def _handle_redverse_list_audio_devices(self, args: dict) -> str:
        if not HAS_SOUNDDEVICE:
            return "Error: sounddevice not installed. Install with: pip install sounddevice"

        input_only = args.get("input_only", True)
        devices = sd.query_devices()
        result = []

        for i, d in enumerate(devices):
            if input_only and d["max_input_channels"] == 0:
                continue
            result.append({
                "id": i,
                "name": d["name"],
                "input_channels": d["max_input_channels"],
                "output_channels": d["max_output_channels"],
                "default_samplerate": d["default_samplerate"],
                "is_default": i == sd.default.device[0] if input_only else False,
            })

        if not result:
            return "No audio input devices found"

        return json.dumps(result, indent=2)

    def _handle_redverse_recorder_info(self, args: dict) -> str:
        info = {
            "name": "RedVerse Voice Recorder",
            "description": "Voiceover recording studio for RedVerse Canon production",
            "features": [
                "Live waveform display",
                "Pause/resume recording",
                "Region selection (chop/trim/replace)",
                "Chapter/scene markers",
                "Noise reduction" + (" (available)" if HAS_SOUNDDEVICE else " (noisereduce not installed)"),
                "Music bed mixing",
                "Export: MP3 / WAV / FLAC",
                "Teleprompter panel",
            ],
            "supported_formats": ["wav", "mp3", "flac"],
            "sample_rate": 44100,
            "channels": 1,
            "dependencies": {
                "sounddevice": HAS_SOUNDDEVICE,
                "pydub": HAS_PYDUB if HAS_NARRATOR else False,
                "noisereduce": False,  # checked separately
            },
            "launch_command": "python redverse_recorder.py",
            "note": (
                "The recorder is a GUI application. Use redverse_list_audio_devices "
                "to verify microphone availability before launching."
            ),
        }

        # Check noisereduce availability
        try:
            import noisereduce
            info["dependencies"]["noisereduce"] = True
        except ImportError:
            pass

        return json.dumps(info, indent=2)

    # ─── Vision Tool Handlers ────────────────────────────────

    def _ollama_vision_sync(self, image_path: str, prompt: str, model: str) -> str:
        """Blocking Ollama vision call (runs inside ThreadPoolExecutor)."""
        with open(image_path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode()
        payload = {
            "model": model,
            "prompt": prompt,
            "images": [encoded],
            "stream": False,
        }
        r = requests.post(
            "http://localhost:11434/api/generate",
            json=payload,
            timeout=120,
        )
        r.raise_for_status()
        data = r.json()
        if isinstance(data, dict) and "response" in data:
            return data["response"].strip()
        return str(data)

    def _handle_vision_analyze(self, args: dict) -> str:
        image_path = args.get("image_path", "")
        if not image_path or not os.path.isfile(image_path):
            return f"Error: Image not found: {image_path}"

        prompt = args.get("prompt", "")
        model = args.get("model", "llava:7b")
        tags = args.get("tags", "")

        # Use cognitive VisionEngine if available
        if self._vision_engine:
            future = self._vision_pool.submit(
                self._vision_engine.analyze,
                image_path,
                query=prompt,
                vision_model=model,
            )
            try:
                ctx = future.result(timeout=200)
            except Exception as e:
                return f"Error: Cognitive vision analysis failed — {e}"

            result = {
                "id": ctx.memory_id,
                "image": os.path.basename(image_path),
                "model": model,
                "models_used": ctx.models_used,
                "processing_time": round(ctx.processing_time, 1),
                "perception": ctx.to_context_block(),
                "stored": ctx.memory_id is not None,
            }
            return json.dumps(result, indent=2)

        # Fallback: simple Ollama-only analysis
        if not self._visual_memory:
            return "Error: Visual memory system not available"

        future = self._vision_pool.submit(
            self._ollama_vision_sync, image_path,
            prompt or "Describe this image in detail.", model,
        )
        try:
            caption = future.result(timeout=130)
        except Exception as e:
            caption = f"[Vision Error] {e}"

        row_id = self._visual_memory.store(
            image_path=image_path,
            ollama_caption=caption,
            ollama_model=model,
            summary=caption[:512] if caption else "",
            tags=tags,
            strategy="OllamaVision",
        )

        result = {
            "id": row_id,
            "image": os.path.basename(image_path),
            "model": model,
            "caption": caption,
            "stored": True,
        }
        return json.dumps(result, indent=2)

    def _handle_vision_recall(self, args: dict) -> str:
        if not self._visual_memory:
            return "Error: Visual memory system not available"

        query = args.get("query", "")
        limit = args.get("limit", 5)
        image_path = args.get("image_path")

        results = self._visual_memory.recall(query, limit=limit, image_path=image_path)
        if not results:
            return f"No visual memories found for: {query}"

        lines = [f"Found {len(results)} visual memories:"]
        for m in results:
            line = f"  [{m.get('strategy', '?')}] {m.get('image_name', '?')}: {m.get('summary', '')[:200]}"
            if m.get("tags"):
                line += f" (tags: {m['tags']})"
            lines.append(line)
        return "\n".join(lines)

    def _handle_vision_recent(self, args: dict) -> str:
        if not self._visual_memory:
            return "Error: Visual memory system not available"

        limit = args.get("limit", 10)
        results = self._visual_memory.recent(limit=limit)
        if not results:
            return "No visual memories stored yet."

        lines = [f"Recent {len(results)} visual memories:"]
        for m in results:
            lines.append(
                f"  [{m.get('created_at', '?')[:19]}] {m.get('image_name', '?')} "
                f"({m.get('strategy', '?')}): {m.get('summary', '')[:120]}"
            )
        return "\n".join(lines)

    def _handle_vision_stats(self, args: dict) -> str:
        if not self._visual_memory:
            return "Error: Visual memory system not available"

        stats = self._visual_memory.get_stats()
        return json.dumps(stats, indent=2)

    # ─── MCP JSON-RPC Protocol ───────────────────────────────

    def handle_message(self, msg: dict) -> dict:
        """Handle a JSON-RPC message and return a response."""
        method = msg.get("method", "")
        msg_id = msg.get("id")
        params = msg.get("params", {})

        if method == "initialize":
            return self._respond(msg_id, {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": "embodiment",
                    "version": "1.0.0"
                }
            })

        elif method == "notifications/initialized":
            # No response needed for notifications
            return None

        elif method == "tools/list":
            return self._respond(msg_id, {"tools": self.tools})

        elif method == "tools/call":
            tool_name = params.get("name", "")
            tool_args = params.get("arguments", {})

            handler = self.tool_handlers.get(tool_name)
            if not handler:
                return self._error(msg_id, -32601, f"Unknown tool: {tool_name}")

            try:
                result_text = handler(tool_args)
                return self._respond(msg_id, {
                    "content": [{"type": "text", "text": result_text}]
                })
            except Exception as e:
                log.error(f"Tool error ({tool_name}): {e}")
                return self._respond(msg_id, {
                    "content": [{"type": "text", "text": f"Error: {str(e)}"}],
                    "isError": True
                })

        elif method == "ping":
            return self._respond(msg_id, {})

        else:
            # Unknown method — ignore notifications, error on requests
            if msg_id is not None:
                return self._error(msg_id, -32601, f"Method not found: {method}")
            return None

    def _respond(self, msg_id, result: dict) -> dict:
        return {"jsonrpc": "2.0", "id": msg_id, "result": result}

    def _error(self, msg_id, code: int, message: str) -> dict:
        return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}

    def run_stdio(self):
        """Run the MCP server over stdin/stdout (default mode)."""
        log.info("Embodiment MCP server starting (stdio mode)")
        log.info(f"Forwarding commands to: {EMBODIMENT_SERVER}")

        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue

            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                log.error(f"Invalid JSON: {line[:100]}")
                continue

            response = self.handle_message(msg)
            if response is not None:
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()

# ═══════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════

def main():
    global EMBODIMENT_SERVER

    import argparse
    parser = argparse.ArgumentParser(description="Embodiment MCP Server")
    parser.add_argument("--transport", choices=["stdio", "sse"], default="stdio",
                        help="Transport mode (default: stdio)")
    parser.add_argument("--server", type=str, default=None,
                        help=f"Embodiment server URL (default: {EMBODIMENT_SERVER})")
    args = parser.parse_args()

    if args.server:
        EMBODIMENT_SERVER = args.server

    server = EmbodimentMCPServer()

    if args.transport == "stdio":
        server.run_stdio()
    else:
        log.error("SSE transport not yet implemented. Use stdio for now.")
        sys.exit(1)

if __name__ == "__main__":
    main()
