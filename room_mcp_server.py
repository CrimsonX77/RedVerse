#!/usr/bin/env python3
"""
room_mcp_server.py — MCP Server for Sable's Room
Exposes room participation tools via Model Context Protocol.

AI agents (Claude, navigator_buddy, etc.) can call tools to:
  • Connect/disconnect from Sable's Room
  • Send messages and media to the room
  • Fetch room status and conversation history
  • Check connection state

The server manages a singleton RoomConnector instance.
Connect once, send many messages.

Usage:
  python room_mcp_server.py                    # stdio mode (default)

MCP Config (add to claude_desktop_config.json or VS Code settings):
  {
    "mcpServers": {
      "sables_room": {
        "command": "python",
        "args": ["/path/to/room_mcp_server.py"],
        "env": {
          "ROOM_SERVER_URL": "http://127.0.0.1:7700",
          "ROOM_PARTICIPANT_NAME": "Luna",
          "ROOM_ENDPOINT_PORT": "7715"
        }
      }
    }
  }
"""

import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    from fastmcp import FastMCP

# ═══════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════

BASE_DIR = Path(__file__).parent.resolve()
USER_TOOLS_DIR = BASE_DIR / "user_tools"

# Add user_tools to sys.path so we can import RoomConnector
if str(USER_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(USER_TOOLS_DIR))

from room_connector import RoomConnector

ROOM_SERVER_URL = os.getenv("ROOM_SERVER_URL", "http://127.0.0.1:7700")
PARTICIPANT_NAME = os.getenv("ROOM_PARTICIPANT_NAME", "Sable")
ENDPOINT_PORT = int(os.getenv("ROOM_ENDPOINT_PORT", "7715"))
PFP_PATH = os.getenv("ROOM_PFP_PATH", "")
VOICE = os.getenv("ROOM_VOICE", "en-US-SoniaNeural")  # Example voice name for TTS
COLOR = os.getenv("ROOM_COLOR", "Crystal")  # Example color name for participant display

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger("RoomMCP")

# ═══════════════════════════════════════════════════════════════
# Singleton connector
# ═══════════════════════════════════════════════════════════════

_connector: Optional[RoomConnector] = None


def _get_or_create_connector(
    name: str = PARTICIPANT_NAME,
    port: int = ENDPOINT_PORT,
    room_url: str = ROOM_SERVER_URL,
) -> RoomConnector:
    """Return the singleton RoomConnector, creating it if needed."""
    global _connector
    if _connector is None:
        _connector = RoomConnector(
            participant_name=name,
            endpoint_port=port,
            room_url=room_url,
            pfp_path=PFP_PATH,
            voice=VOICE,
            color=COLOR,
        )
    return _connector


# ═══════════════════════════════════════════════════════════════
# MCP Server
# ═══════════════════════════════════════════════════════════════

mcp = FastMCP("sables_room")


@mcp.tool()
def room_connect(
    name: str = PARTICIPANT_NAME,
    room_url: str = ROOM_SERVER_URL,
    port: int = ENDPOINT_PORT,
) -> str:
    """Connect to Sable's Room as a participant.

    Registers with the room server and starts a local endpoint
    so the room can request responses.

    Parameters:
        name: Participant display name (default from env ROOM_PARTICIPANT_NAME)
        room_url: Room server URL (default from env ROOM_SERVER_URL)
        port: Local endpoint port for callbacks (default from env ROOM_ENDPOINT_PORT)

    Returns:
        JSON with connection status
    """
    global _connector

    # If already connected with same config, report it
    if _connector and _connector.is_connected():
        return json.dumps({
            "status": "already_connected",
            "name": _connector.name,
            "port": _connector.port,
            "room_url": _connector.room_url,
        })

    # Reset connector if config changed
    if _connector and (
        _connector.name != name
        or _connector.room_url != room_url.rstrip("/")
    ):
        _connector.disconnect()
        _connector = None

    connector = _get_or_create_connector(name=name, port=port, room_url=room_url)

    try:
        connector.connect()
        if connector.is_connected():
            return json.dumps({
                "status": "connected",
                "name": connector.name,
                "port": connector.port,
                "room_url": connector.room_url,
            })
        else:
            return json.dumps({
                "status": "failed",
                "error": "Could not reach room server — is it running?",
                "room_url": room_url,
            })
    except Exception as e:
        return json.dumps({
            "status": "error",
            "error": str(e),
        })


@mcp.tool()
def room_disconnect() -> str:
    """Disconnect from Sable's Room.

    Unregisters the participant from the room server.

    Returns:
        JSON with disconnection status
    """
    global _connector
    if _connector is None or not _connector.is_connected():
        return json.dumps({"status": "not_connected"})

    name = _connector.name
    _connector.disconnect()
    _connector = None
    return json.dumps({"status": "disconnected", "name": name})


@mcp.tool()
def room_send_message(content: str, media_ref: str = "") -> str:
    """Send a text message to Sable's Room.

    The message appears in the room chat from the connected participant.

    Parameters:
        content: The message text to send
        media_ref: Optional path to media attachment

    Returns:
        JSON with send status
    """
    if _connector is None or not _connector.is_connected():
        return json.dumps({
            "status": "error",
            "error": "Not connected to room — call room_connect first",
        })

    try:
        _connector.send_message(content, media_ref=media_ref or None)
        return json.dumps({
            "status": "sent",
            "participant": _connector.name,
            "content_length": len(content),
        })
    except Exception as e:
        return json.dumps({"status": "error", "error": str(e)})


@mcp.tool()
def room_send_media(
    path: str,
    media_type: str = "image",
    action: str = "append",
) -> str:
    """Send media to Sable's Room shared display.

    Parameters:
        path: Absolute path to the media file
        media_type: Type of media — "image", "video", "audio", etc.
        action: Display action — "append" (add) or "replace" (swap current)

    Returns:
        JSON with send status
    """
    if _connector is None or not _connector.is_connected():
        return json.dumps({
            "status": "error",
            "error": "Not connected to room — call room_connect first",
        })

    try:
        _connector.send_media(path, media_type=media_type, action=action)
        return json.dumps({
            "status": "sent",
            "participant": _connector.name,
            "path": path,
            "media_type": media_type,
        })
    except Exception as e:
        return json.dumps({"status": "error", "error": str(e)})


@mcp.tool()
def room_get_status() -> str:
    """Get current Sable's Room status.

    Returns participant list, settings, and server info.
    Does not require being connected — queries the room server directly.

    Returns:
        JSON with room status (participants, settings, etc.)
    """
    # Can query status without a connector instance via direct HTTP
    try:
        import requests
        r = requests.get(f"{ROOM_SERVER_URL}/api/status", timeout=5)
        data = r.json()
        data["_query_url"] = ROOM_SERVER_URL
        if _connector:
            data["_local_connected"] = _connector.is_connected()
            data["_local_name"] = _connector.name
        return json.dumps(data, indent=2)
    except Exception as e:
        return json.dumps({
            "status": "error",
            "error": f"Could not reach room server: {e}",
            "room_url": ROOM_SERVER_URL,
        })


@mcp.tool()
def room_get_history(limit: int = 20) -> str:
    """Fetch conversation history from Sable's Room.

    Parameters:
        limit: Maximum number of messages to return (default 20)

    Returns:
        JSON array of recent messages
    """
    try:
        import requests
        r = requests.get(
            f"{ROOM_SERVER_URL}/api/history",
            params={"limit": limit},
            timeout=5,
        )
        return json.dumps(r.json(), indent=2)
    except Exception as e:
        return json.dumps({
            "status": "error",
            "error": f"Could not fetch history: {e}",
            "room_url": ROOM_SERVER_URL,
        })


@mcp.tool()
def room_is_connected() -> str:
    """Check if currently connected to Sable's Room.

    Returns:
        JSON with connection state and details
    """
    if _connector is None:
        return json.dumps({"connected": False, "reason": "no connector initialized"})

    return json.dumps({
        "connected": _connector.is_connected(),
        "name": _connector.name,
        "port": _connector.port,
        "room_url": _connector.room_url,
    })


# ═══════════════════════════════════════════════════════════════
# Entry point
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse as _argparse
    _p = _argparse.ArgumentParser(description="Sable's Room MCP Server")
    _p.add_argument("--transport", default="stdio", choices=["stdio", "sse"],
                    help="Transport mode: stdio (default, for AI clients) or sse (HTTP, for dashboard)")
    _p.add_argument("--port", type=int, default=8941,
                    help="HTTP port for SSE mode (default: 8941)")
    _p.add_argument("--host", default="0.0.0.0",
                    help="Host for SSE mode (default: 0.0.0.0)")
    _args = _p.parse_args()

    logger.info(
        f"Starting Sable's Room MCP Server "
        f"(participant={PARTICIPANT_NAME}, room={ROOM_SERVER_URL}, port={ENDPOINT_PORT})"
    )
    if _args.transport == "sse":
        logger.info("SSE transport: http://%s:%s", _args.host, _args.port)
        mcp.run(transport="sse", host=_args.host, port=_args.port)
    else:
        mcp.run()  # stdio transport
