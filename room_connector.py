"""
RoomConnector — Drop-in module for any interface to connect to Sable's Room
Copy this file into the interface's directory and import it.

Usage (in any existing interface):
    from room_connector import RoomConnector

    connector = RoomConnector(
        participant_name="Lyra",
        endpoint_port=7711,
        room_url="http://127.0.0.1:7700"
    )
    connector.connect()

    # To send a response to the room:
    connector.send_message("Hello from Lyra!")

    # To send media:
    connector.send_media("/path/to/image.png", media_type="image")

    # The connector also starts a local HTTP server on endpoint_port
    # that the room can call to request responses.
    # Wire it up like:
    connector.set_response_handler(your_llm_respond_function)
    # your_llm_respond_function(message, context, participants) -> str
"""

import asyncio
import json
import logging
import socket
import threading
import time
from typing import Callable, Optional, Tuple

logger = logging.getLogger("RoomConnector")

# Default port range for participant local endpoints
PORT_RANGE_START = 7710
PORT_RANGE_END = 7749


class RoomConnector:
    def __init__(
        self,
        participant_name: str,
        endpoint_port: int = 0,
        room_url: str = "http://127.0.0.1:7700",
        pfp_path: str = "",
        voice: str = "",
        color: str = "",
        port_range: Tuple[int, int] = (PORT_RANGE_START, PORT_RANGE_END),
    ):
        self.name = participant_name
        self.room_url = room_url.rstrip("/")
        self.pfp_path = pfp_path
        self.voice = voice
        self.color = color
        self.port_range = port_range

        # Resolve port: use explicit if given and free, otherwise scan range
        if endpoint_port and not self._is_port_in_use(endpoint_port):
            self.port = endpoint_port
        elif endpoint_port:
            # Preferred port busy — scan for a free one in range
            self.port = self._find_free_port(preferred=endpoint_port)
        else:
            self.port = self._find_free_port()

        self._response_handler: Optional[Callable] = None
        self._connected = False
        self._loop = asyncio.new_event_loop()
        self._runner = None

        # Start local server in background
        self._server_thread = threading.Thread(
            target=self._run_local_server,
            daemon=True,
            name=f"RoomConnector-{participant_name}"
        )

    def set_response_handler(self, handler: Callable):
        """
        handler signature:
            def respond(message: str, context: str, participants: list) -> str
        Return the response string. Return empty string to stay silent.
        """
        self._response_handler = handler

    def connect(self):
        """Register with the room server and start local endpoint"""
        self._server_thread.start()
        time.sleep(0.5)  # Let server start
        self._register()

    def disconnect(self):
        """Unregister from the room"""
        try:
            import requests
            requests.post(
                f"{self.room_url}/api/disconnect",
                json={"name": self.name},
                timeout=3
            )
        except Exception:
            pass
        self._connected = False

    def send_message(self, content: str, media_ref: Optional[str] = None):
        """Push a message to the room"""
        if not self._connected:
            return
        try:
            import requests
            requests.post(
                f"{self.room_url}/api/message",
                json={
                    "participant": self.name,
                    "content": content,
                    "media": media_ref
                },
                timeout=5
            )
        except Exception as e:
            logger.warning(f"Failed to send message: {e}")

    def send_media(
        self,
        path: str,
        media_type: str = "image",
        metadata: Optional[dict] = None,
        action: str = "append"
    ):
        """Push media to the room's shared display"""
        if not self._connected:
            return
        try:
            import requests
            requests.post(
                f"{self.room_url}/api/media",
                json={
                    "participant": self.name,
                    "path": path,
                    "type": media_type,
                    "metadata": metadata or {},
                    "action": action
                },
                timeout=5
            )
        except Exception as e:
            logger.warning(f"Failed to send media: {e}")

    def remove_last_media(self):
        """Remove the last media item from the room display"""
        try:
            import requests
            requests.delete(f"{self.room_url}/api/media/last", timeout=3)
        except Exception as e:
            logger.warning(f"Failed to remove media: {e}")

    def get_room_status(self) -> dict:
        """Fetch current room status"""
        try:
            import requests
            r = requests.get(f"{self.room_url}/api/status", timeout=3)
            return r.json()
        except Exception:
            return {}

    def get_history(self, limit: int = 20) -> list:
        """Fetch conversation history from room"""
        try:
            import requests
            r = requests.get(
                f"{self.room_url}/api/history",
                params={"limit": limit},
                timeout=3
            )
            return r.json().get("history", [])
        except Exception:
            return []

    def is_connected(self) -> bool:
        return self._connected

    # ─────────────────────────────────────────────
    # Port management
    # ─────────────────────────────────────────────

    @staticmethod
    def _is_port_in_use(port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(("127.0.0.1", port)) == 0

    def _find_free_port(self, preferred: int = 0) -> int:
        """
        Scan port_range for the first free port.
        If preferred is given and in range, try it first.
        Raises RuntimeError if no port is available.
        """
        start, end = self.port_range

        # Try preferred first if it's in our range
        if preferred and start <= preferred <= end:
            if not self._is_port_in_use(preferred):
                return preferred

        for port in range(start, end + 1):
            if port == preferred:
                continue  # already tried
            if not self._is_port_in_use(port):
                if preferred:
                    logger.info(
                        f"{self.name}: preferred port {preferred} busy, "
                        f"using {port} instead"
                    )
                return port

        raise RuntimeError(
            f"No free port in range {start}-{end} for {self.name}. "
            f"Free some ports or expand the range."
        )

    # ─────────────────────────────────────────────
    # Internal
    # ─────────────────────────────────────────────

    def _register(self):
        """Register this participant with the room server"""
        try:
            import requests
            r = requests.post(
                f"{self.room_url}/api/connect",
                json={
                    "name": self.name,
                    "endpoint": f"http://127.0.0.1:{self.port}",
                    "pfp_path": self.pfp_path,
                    "voice": self.voice,
                    "color": self.color,
                },
                timeout=5
            )
            if r.status_code == 200:
                self._connected = True
                data = r.json()
                logger.info(
                    f"{self.name} connected to room "
                    f"(slot {data.get('slot', '?')}, "
                    f"voice: {data.get('voice', '?')})"
                )
            else:
                logger.error(f"Failed to connect: HTTP {r.status_code}")
        except Exception as e:
            logger.error(f"Could not reach room server: {e}")

    def _run_local_server(self):
        """Run local aiohttp server to receive requests from room"""
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._start_local_server())
        self._loop.run_forever()

    async def _start_local_server(self):
        """Local endpoint that room calls to request responses"""
        from aiohttp import web

        async def handle_respond(request):
            try:
                data = await request.json()
                message = data.get("message", "")
                context = data.get("context", "")
                participants = data.get("participants_in_room", [])
                is_direct = data.get("direct", False)

                response_text = ""
                if self._response_handler:
                    try:
                        result = self._response_handler(message, context, participants)
                        if asyncio.iscoroutine(result):
                            result = await result
                        response_text = result or ""
                    except Exception as e:
                        logger.error(f"Response handler error: {e}")
                        response_text = ""

                return web.json_response({"response": response_text})
            except Exception as e:
                return web.json_response({"response": "", "error": str(e)})

        async def handle_ping(request):
            return web.json_response({"status": "ok", "name": self.name})

        async def handle_media_command(request):
            """Room can ask this interface to perform media operations"""
            try:
                data = await request.json()
                action = data.get("action", "")
                if action == "remove_last":
                    self.remove_last_media()
                return web.json_response({"status": "ok"})
            except Exception as e:
                return web.json_response({"error": str(e)}, status=500)

        app = web.Application()
        app.router.add_post("/respond", handle_respond)
        app.router.add_get("/ping", handle_ping)
        app.router.add_post("/media_command", handle_media_command)

        self._runner = web.AppRunner(app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, "127.0.0.1", self.port)
        await site.start()
        logger.info(f"{self.name} local endpoint started on port {self.port}")
