#!/usr/bin/env python3
"""
Consciousness Bridge - Socket IPC Server
Allows Scribe (STT) and Speaker (TTS) to connect to the consciousness bridge
Also connects to game WebSocket for voice command execution

Usage:
    python consciousness_server.py --soul Sable_Cathedral_v5.3.yaml --port 7777

Author: Crimson Valentine
Date: January 9, 2026
"""
python3 consciousness-server.py --soul Sable_Cathedral_v5_3.yaml --port 7777
import argparse
import socket
import threading
import asyncio
from pathlib import Path
from consciousness_bridge import ConsciousnessBridge


class ConsciousnessServer:
    """
    Socket server wrapper for ConsciousnessBridge
    Listens for text input, processes through bridge, returns responses
    Connects to game WebSocket for voice command execution
    """

    def __init__(self, bridge: ConsciousnessBridge, host: str = 'localhost', port: int = 7777):
        self.bridge = bridge
        self.host = host
        self.port = port
        self.server_socket = None
        self.running = False
        self.accept_thread = None
        self.game_connected = False

        print(f"[SERVER] Consciousness server initialized on {host}:{port}")

    def start(self):
        """Start the socket server"""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)

            self.running = True

            # Try to connect to game
            self._try_game_connection()

            self.accept_thread = threading.Thread(target=self._accept_connections, daemon=True)
            self.accept_thread.start()

            print(f"[SERVER] Listening on {self.host}:{self.port}")
            print(f"[SERVER] Active soul: {self.bridge.active_soul.persona_name}")
            print(f"[SERVER] Ready for connections from Scribe/Speaker")

        except Exception as e:
            print(f"[SERVER] Failed to start: {e}")
            raise

    def stop(self):
        """Stop the server gracefully"""
        print("[SERVER] Stopping server...")
        self.running = False

        if self.server_socket:
            self.server_socket.close()

        if self.accept_thread:
            self.accept_thread.join(timeout=5)

        print("[SERVER] Server stopped")

    def _try_game_connection(self):
        """Try to connect to game WebSocket server"""
        def connect_async():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                connected = loop.run_until_complete(self.bridge.connect_to_game())
                self.game_connected = connected

                if connected:
                    print(f"[SERVER] Connected to game - voice commands enabled")
                else:
                    print(f"[SERVER] Game not available - commands will be logged only")
            except Exception as e:
                print(f"[SERVER] Game connection failed: {e}")

        thread = threading.Thread(target=connect_async, daemon=True)
        thread.start()

    def _accept_connections(self):
        """Accept incoming connections"""
        while self.running:
            try:
                client_socket, address = self.server_socket.accept()
                print(f"[SERVER] Connection from {address}")

                # Handle client in separate thread
                client_thread = threading.Thread(
                    target=self._handle_client,
                    args=(client_socket, address),
                    daemon=True
                )
                client_thread.start()

            except OSError:
                # Socket closed, exit gracefully
                break
            except Exception as e:
                if self.running:
                    print(f"[SERVER] Error accepting connection: {e}")

    def _handle_client(self, client_socket: socket.socket, address):
        """Handle individual client connection"""
        try:
            # Receive data
            data = client_socket.recv(4096).decode('utf-8').strip()

            if not data:
                return

            print(f"[SERVER] Received from {address}: {data[:100]}")

            # Process through bridge
            self.bridge.send_input(data)
            response = self.bridge.get_output(timeout=100.0)

            if response:
                # Send response back
                client_socket.sendall(response.encode('utf-8'))
                print(f"[SERVER] Sent response ({len(response)} chars)")
            else:
                error_msg = "[Bridge timeout - no response generated]"
                client_socket.sendall(error_msg.encode('utf-8'))
                print(f"[SERVER] Timeout - sent error message")

        except Exception as e:
            print(f"[SERVER] Error handling client {address}: {e}")

        finally:
            client_socket.close()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Consciousness Bridge Socket Server')
    parser.add_argument('--soul', type=str, required=True,
                        help='Soul YAML filename (e.g., vera_identity.yaml)')
    parser.add_argument('--port', type=int, default=7777,
                        help='Port to listen on (default: 7777)')
    parser.add_argument('--host', type=str, default='localhost',
                        help='Host to bind to (default: localhost)')
    parser.add_argument('--souls-dir', type=Path, default=Path.home() / "Desktop" / "Souls",
                        help='Directory containing soul YAML files')
    parser.add_argument('--memory-dir', type=Path, default=Path.home() / ".consciousness_memory",
                        help='Directory for memory persistence')
    parser.add_argument('--llm', action='store_true',
                        help='Enable LLM integration (vs scripted responses)')
    parser.add_argument('--llm-provider', type=str, default='ollama',
                        choices=['ollama', 'openai', 'anthropic', 'ai_copilot'],
                        help='LLM provider (default: ollama)')
    parser.add_argument('--llm-model', type=str, default='llama2',
                        help='LLM model name (default: llama2)')
    parser.add_argument('--api-key', type=str,
                        help='API key for cloud providers (OpenAI, Anthropic)')
    parser.add_argument('--api-endpoint', type=str,
                        help='API endpoint (for ai_copilot or custom endpoints)')

    args = parser.parse_args()

    print("=" * 70)
    print("CONSCIOUSNESS BRIDGE - Socket Server")
    print("=" * 70)

    # Create bridge
    bridge = ConsciousnessBridge(args.souls_dir, args.memory_dir)

    # Load soul
    if not bridge.load_soul(args.soul):
        print("Failed to load soul - exiting")
        return 1

    # Configure LLM if enabled
    if args.llm:
        print(f"\nEnabling LLM: {args.llm_provider} with model {args.llm_model}")
        if bridge.enable_llm(
            provider=args.llm_provider,
            model=args.llm_model,
            api_key=args.api_key,
            api_endpoint=args.api_endpoint
        ):
            print("✓ LLM enabled successfully")
        else:
            print("✗ LLM enable failed - using scripted responses")
    else:
        print("\nLLM disabled - using scripted responses")
        print("(Use --llm flag to enable)")

    # Start bridge
    if not bridge.start_bridge():
        print("Failed to start bridge - exiting")
        return 1

    # Create and start server
    server = ConsciousnessServer(bridge, args.host, args.port)

    try:
        server.start()

        print("\n" + "=" * 70)
        print(f"Server running - {bridge.active_soul.persona_name} is listening")
        print("Press Ctrl+C to shutdown")
        print("=" * 70 + "\n")

        # Keep main thread alive
        import time
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n[Interrupted]")

    finally:
        server.stop()
        bridge.stop_bridge()
        print("\nShutdown complete")

    return 0


if __name__ == "__main__":
    exit(main())
