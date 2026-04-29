#!/usr/bin/env python3
"""
Mech Game Controller - WebSocket client for game control
Sends commands to the game and receives state updates

Author: Crimson Valentine
Date: January 9, 2026
"""

import asyncio
import json
import websockets
from typing import Optional, Dict, Any, Callable
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MechGameController:
    """Control the mech game via WebSocket"""
    
    def __init__(self, game_ws_url: str = "ws://localhost:8888"):
        self.game_ws_url = game_ws_url
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.current_state: Dict[str, Any] = {}
        self.state_callback: Optional[Callable] = None
        self.connected = False
        
    async def connect(self, websocket_url: Optional[str] = None):
        """Connect to the game WebSocket server"""
        # Allow URL override
        url = websocket_url if websocket_url else self.game_ws_url
        try:
            self.websocket = await websockets.connect(url)
            self.connected = True
            
            # Register as AI client
            await self.websocket.send(json.dumps({'type': 'register_ai'}))
            
            # Wait for registration confirmation
            response = await self.websocket.recv()
            data = json.loads(response)
            
            if data.get('type') == 'registered':
                logger.info(f"Registered as: {data.get('role')}")
                return True
            
            return False
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            self.connected = False
            return False
    
    async def disconnect(self):
        """Disconnect from server"""
        if self.websocket:
            await self.websocket.close()
            self.connected = False
            logger.info("Disconnected from game")
    
    async def send_command(self, action: str, **kwargs) -> Dict[str, Any]:
        """Send command to game and wait for acknowledgment"""
        if not self.connected or not self.websocket:
            return {'success': False, 'message': 'Not connected'}
        
        try:
            command = {
                'type': 'command',
                'action': action,
                **kwargs
            }
            
            await self.websocket.send(json.dumps(command))
            logger.info(f"Sent command: {action}")
            
            # Wait for acknowledgment (with timeout)
            try:
                response = await asyncio.wait_for(self.websocket.recv(), timeout=2.0)
                data = json.loads(response)
                
                if data.get('type') == 'ack' and data.get('action') == action:
                    return {
                        'success': data.get('success', False),
                        'message': data.get('message', '')
                    }
            except asyncio.TimeoutError:
                return {'success': False, 'message': 'Command timeout'}
            
            return {'success': False, 'message': 'No acknowledgment'}
            
        except Exception as e:
            logger.error(f"Failed to send command {action}: {e}")
            return {'success': False, 'message': str(e)}
    
    async def listen_for_state_updates(self):
        """Listen for game state updates in background"""
        if not self.websocket:
            return
        
        try:
            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    
                    if data.get('type') == 'game_state':
                        self.current_state = data
                        logger.debug(f"Game state updated: HP={data.get('player_hp')}, Heat={data.get('heat_level')}")
                        
                        # Call callback if registered
                        if self.state_callback:
                            self.state_callback(data)
                            
                except json.JSONDecodeError:
                    logger.error("Failed to parse game state")
        except websockets.exceptions.ConnectionClosed:
            logger.info("Connection closed")
            self.connected = False
    
    def set_state_callback(self, callback: Callable):
        """Register callback for game state updates"""
        self.state_callback = callback
    
    # ==================================================================
    # COMMAND SHORTCUTS
    # ==================================================================
    
    async def shield_activate(self) -> Dict[str, Any]:
        """Activate shield"""
        return await self.send_command('shield_activate')
    
    async def vent_heat(self) -> Dict[str, Any]:
        """Vent heat"""
        return await self.send_command('vent_heat')
    
    async def boost(self, direction: Optional[Dict] = None) -> Dict[str, Any]:
        """Boost forward"""
        if direction:
            return await self.send_command('boost', direction=direction)
        return await self.send_command('boost')
    
    async def handbrake(self) -> Dict[str, Any]:
        """Apply handbrake"""
        return await self.send_command('handbrake')
    
    async def emergency_dump(self) -> Dict[str, Any]:
        """Emergency heat dump"""
        return await self.send_command('emergency_dump')
    
    async def toggle_reactor(self) -> Dict[str, Any]:
        """Toggle reactor"""
        return await self.send_command('toggle_reactor')
    
    def get_current_state(self) -> Dict[str, Any]:
        """Get the most recent game state"""
        return self.current_state


# ==================================================================
# TESTING
# ==================================================================

async def test_controller():
    """Test the game controller"""
    print("=" * 60)
    print("Mech Game Controller Test")
    print("=" * 60)
    
    controller = MechGameController()
    
    # Connect
    print("\nConnecting to game...")
    if not await controller.connect():
        print("✗ Failed to connect")
        return
    
    print("✓ Connected to game")
    
    # Start listening for state updates in background
    listen_task = asyncio.create_task(controller.listen_for_state_updates())
    
    # Test commands
    print("\n--- Testing Commands ---")
    
    await asyncio.sleep(1)
    
    result = await controller.shield_activate()
    print(f"Shield: {result}")
    
    await asyncio.sleep(1)
    
    result = await controller.vent_heat()
    print(f"Vent: {result}")
    
    await asyncio.sleep(1)
    
    result = await controller.boost()
    print(f"Boost: {result}")
    
    await asyncio.sleep(2)
    
    # Show current state
    state = controller.get_current_state()
    if state:
        print(f"\n--- Current Game State ---")
        print(f"HP: {state.get('player_hp')}/{state.get('player_hp_max')}")
        print(f"Heat: {state.get('heat_level')}%")
        print(f"Fuel: {state.get('fuel')}/{state.get('fuel_max')}")
        print(f"Ammo: {state.get('ammo')}/{state.get('ammo_max')}")
        print(f"Enemies: {state.get('enemies_alive')}")
        print(f"Score: {state.get('score')}")
    
    # Disconnect
    print("\nDisconnecting...")
    listen_task.cancel()
    await controller.disconnect()
    print("✓ Disconnected")


if __name__ == "__main__":
    asyncio.run(test_controller())
