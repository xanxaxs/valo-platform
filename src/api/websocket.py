"""
Valorant WebSocket Client.

Connects to Valorant's local WebSocket for real-time events.
"""

import asyncio
import json
import logging
import ssl
from typing import Callable, Optional

import websockets
from websockets.client import WebSocketClientProtocol

from .lockfile import LockfileData

logger = logging.getLogger(__name__)


class ValorantWebSocket:
    """
    WebSocket client for Valorant real-time events.
    
    Subscribes to events like:
    - Game state changes
    - Match updates
    - Presence changes
    """
    
    def __init__(self, lockfile_data: LockfileData):
        """
        Initialize WebSocket client.
        
        Args:
            lockfile_data: Connection details from lockfile
        """
        self.lockfile_data = lockfile_data
        self._ws: Optional[WebSocketClientProtocol] = None
        self._connected = False
        self._receive_task: Optional[asyncio.Task] = None
        
        # Event handlers
        self._handlers: dict[str, list[Callable]] = {}
        self._global_handlers: list[Callable] = []
    
    @property
    def is_connected(self) -> bool:
        """Check if WebSocket is connected."""
        return self._connected and self._ws is not None
    
    async def connect(self) -> bool:
        """
        Connect to Valorant WebSocket.
        
        Returns:
            True if connection successful
        """
        try:
            # Build WebSocket URL
            ws_url = f"wss://127.0.0.1:{self.lockfile_data.port}"
            
            # Create SSL context that doesn't verify (local connection)
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            # Build auth header
            import base64
            credentials = f"riot:{self.lockfile_data.password}"
            auth = base64.b64encode(credentials.encode()).decode()
            
            # Connect
            self._ws = await websockets.connect(
                ws_url,
                ssl=ssl_context,
                extra_headers={
                    "Authorization": f"Basic {auth}",
                },
            )
            
            self._connected = True
            logger.info("WebSocket connected")
            
            # Start receive loop
            self._receive_task = asyncio.create_task(self._receive_loop())
            
            return True
            
        except Exception as e:
            logger.error(f"WebSocket connection failed: {e}")
            return False
    
    async def disconnect(self) -> None:
        """Disconnect WebSocket."""
        self._connected = False
        
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
        
        if self._ws:
            await self._ws.close()
            self._ws = None
        
        logger.info("WebSocket disconnected")
    
    async def subscribe(self, event_name: str) -> bool:
        """
        Subscribe to an event.
        
        Args:
            event_name: Event to subscribe to
            
        Returns:
            True if subscription sent
        """
        if not self._ws:
            return False
        
        try:
            message = json.dumps([5, event_name])
            await self._ws.send(message)
            logger.debug(f"Subscribed to: {event_name}")
            return True
        except Exception as e:
            logger.error(f"Subscribe failed: {e}")
            return False
    
    async def unsubscribe(self, event_name: str) -> bool:
        """
        Unsubscribe from an event.
        
        Args:
            event_name: Event to unsubscribe from
            
        Returns:
            True if unsubscription sent
        """
        if not self._ws:
            return False
        
        try:
            message = json.dumps([6, event_name])
            await self._ws.send(message)
            logger.debug(f"Unsubscribed from: {event_name}")
            return True
        except Exception as e:
            logger.error(f"Unsubscribe failed: {e}")
            return False
    
    def on(self, event_name: str, handler: Callable) -> None:
        """
        Register event handler.
        
        Args:
            event_name: Event to handle
            handler: Callback function
        """
        if event_name not in self._handlers:
            self._handlers[event_name] = []
        self._handlers[event_name].append(handler)
    
    def on_any(self, handler: Callable) -> None:
        """
        Register handler for all events.
        
        Args:
            handler: Callback function
        """
        self._global_handlers.append(handler)
    
    def off(self, event_name: str, handler: Optional[Callable] = None) -> None:
        """
        Remove event handler.
        
        Args:
            event_name: Event name
            handler: Specific handler to remove (all if None)
        """
        if event_name in self._handlers:
            if handler:
                self._handlers[event_name] = [
                    h for h in self._handlers[event_name] if h != handler
                ]
            else:
                del self._handlers[event_name]
    
    async def _receive_loop(self) -> None:
        """Main receive loop for WebSocket messages."""
        if not self._ws:
            return
        
        try:
            async for message in self._ws:
                await self._handle_message(message)
        except websockets.ConnectionClosed:
            logger.info("WebSocket connection closed")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"WebSocket receive error: {e}")
        finally:
            self._connected = False
    
    async def _handle_message(self, message: str) -> None:
        """
        Handle incoming WebSocket message.
        
        Args:
            message: Raw message string
        """
        try:
            data = json.loads(message)
            
            # Messages are typically in format: [type, event_name, payload]
            if isinstance(data, list) and len(data) >= 2:
                msg_type = data[0]
                
                if msg_type == 8:  # Event message
                    event_name = data[1]
                    payload = data[2] if len(data) > 2 else {}
                    
                    # Call specific handlers
                    if event_name in self._handlers:
                        for handler in self._handlers[event_name]:
                            try:
                                if asyncio.iscoroutinefunction(handler):
                                    await handler(payload)
                                else:
                                    handler(payload)
                            except Exception as e:
                                logger.error(f"Handler error for {event_name}: {e}")
                    
                    # Call global handlers
                    for handler in self._global_handlers:
                        try:
                            if asyncio.iscoroutinefunction(handler):
                                await handler(event_name, payload)
                            else:
                                handler(event_name, payload)
                        except Exception as e:
                            logger.error(f"Global handler error: {e}")
                            
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON message: {message[:100]}")
        except Exception as e:
            logger.error(f"Message handling error: {e}")
    
    # ============================================
    # Common Event Subscriptions
    # ============================================
    
    async def subscribe_to_presence(self) -> bool:
        """Subscribe to presence updates."""
        return await self.subscribe("OnJsonApiEvent_chat_v4_presences")
    
    async def subscribe_to_game_state(self) -> bool:
        """Subscribe to game state changes."""
        # Subscribe to multiple relevant events
        results = await asyncio.gather(
            self.subscribe("OnJsonApiEvent_riot-messaging-service_v1_message"),
            self.subscribe("OnJsonApiEvent"),
        )
        return all(results)
    
    async def subscribe_to_match(self, match_id: str) -> bool:
        """Subscribe to match updates."""
        return await self.subscribe(f"OnJsonApiEvent_core-game_v1_matches_{match_id}")

