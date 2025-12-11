"""
Valorant Local API Client.

Communicates with the local Valorant client API.
"""

import asyncio
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

import aiohttp

from .lockfile import LockfileData, LockfileReader

logger = logging.getLogger(__name__)


class GameState(str, Enum):
    """Valorant game states."""
    
    MENUS = "MENUS"
    PREGAME = "PREGAME"
    INGAME = "INGAME"
    UNKNOWN = "UNKNOWN"


@dataclass
class PlayerInfo:
    """Player information."""
    
    puuid: str
    game_name: str
    tag_line: str
    
    @property
    def full_name(self) -> str:
        return f"{self.game_name}#{self.tag_line}"


@dataclass
class MatchPlayer:
    """Player in a match."""
    
    puuid: str
    team_id: str
    agent_id: str
    player_name: Optional[str] = None
    tag_line: Optional[str] = None


@dataclass
class MatchInfo:
    """Match information."""
    
    match_id: str
    map_id: str
    game_mode: str
    players: list[MatchPlayer]
    
    def get_player_team(self, puuid: str) -> Optional[str]:
        """Get team ID for a player."""
        for player in self.players:
            if player.puuid == puuid:
                return player.team_id
        return None


class ValorantClient:
    """
    Client for Valorant local API.
    
    Provides methods to interact with the running Valorant client.
    """
    
    def __init__(self):
        """Initialize client."""
        self.lockfile_reader = LockfileReader()
        self._lockfile_data: Optional[LockfileData] = None
        self._session: Optional[aiohttp.ClientSession] = None
        self._puuid: Optional[str] = None
    
    @property
    def is_connected(self) -> bool:
        """Check if client is connected."""
        return self._lockfile_data is not None and self._session is not None
    
    @property
    def puuid(self) -> Optional[str]:
        """Get current player's PUUID."""
        return self._puuid
    
    async def connect(self) -> bool:
        """
        Connect to Valorant local API.
        
        Returns:
            True if connection successful
        """
        self._lockfile_data = self.lockfile_reader.read()
        if not self._lockfile_data:
            logger.error("Failed to read lockfile - is Valorant running?")
            return False
        
        # Create session with auth
        connector = aiohttp.TCPConnector(ssl=False)
        self._session = aiohttp.ClientSession(
            connector=connector,
            headers={
                "Authorization": self._lockfile_data.auth_header,
                "Content-Type": "application/json",
            },
        )
        
        # Get player info
        try:
            user_info = await self.get_user_info()
            if user_info:
                self._puuid = user_info.puuid
                logger.info(f"Connected as {user_info.full_name}")
                return True
        except Exception as e:
            logger.error(f"Failed to get user info: {e}")
        
        return False
    
    async def disconnect(self) -> None:
        """Disconnect and cleanup."""
        if self._session:
            await self._session.close()
            self._session = None
        self._lockfile_data = None
        self._puuid = None
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        base: str = "local",
        **kwargs,
    ) -> Optional[dict]:
        """
        Make API request.
        
        Args:
            method: HTTP method
            endpoint: API endpoint
            base: "local" or "glz" or "pd"
            **kwargs: Additional request arguments
            
        Returns:
            Response JSON or None
        """
        if not self._session or not self._lockfile_data:
            return None
        
        if base == "local":
            url = f"{self._lockfile_data.base_url}{endpoint}"
        else:
            # For remote APIs, would need different handling
            url = endpoint
        
        try:
            async with self._session.request(method, url, **kwargs) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.warning(f"API request failed: {response.status} {endpoint}")
                    return None
        except Exception as e:
            logger.error(f"API request error: {e}")
            return None
    
    # ============================================
    # User/Account APIs
    # ============================================
    
    async def get_user_info(self) -> Optional[PlayerInfo]:
        """Get current user info."""
        data = await self._request("GET", "/rso-auth/v1/authorization/userinfo")
        if not data:
            return None
        
        try:
            # Parse userinfo JWT or response
            # The actual structure may vary
            if "userInfo" in data:
                info = data["userInfo"]
                return PlayerInfo(
                    puuid=info.get("sub", ""),
                    game_name=info.get("acct", {}).get("game_name", ""),
                    tag_line=info.get("acct", {}).get("tag_line", ""),
                )
        except Exception as e:
            logger.error(f"Failed to parse user info: {e}")
        
        return None
    
    async def get_session(self) -> Optional[dict]:
        """Get current session info."""
        return await self._request("GET", "/chat/v1/session")
    
    # ============================================
    # Game State APIs
    # ============================================
    
    async def get_game_state(self) -> GameState:
        """Get current game state."""
        # Try to get current game match ID
        pregame = await self._request("GET", "/pregame/v1/player")
        if pregame and pregame.get("MatchID"):
            return GameState.PREGAME
        
        coregame = await self._request("GET", "/core-game/v1/player")
        if coregame and coregame.get("MatchID"):
            return GameState.INGAME
        
        return GameState.MENUS
    
    async def get_presence(self) -> Optional[dict]:
        """Get presence info (includes game state)."""
        return await self._request("GET", "/chat/v6/presences")
    
    # ============================================
    # Match APIs
    # ============================================
    
    async def get_pregame_match_id(self) -> Optional[str]:
        """Get pregame match ID."""
        data = await self._request("GET", "/pregame/v1/player")
        return data.get("MatchID") if data else None
    
    async def get_coregame_match_id(self) -> Optional[str]:
        """Get current game match ID."""
        data = await self._request("GET", "/core-game/v1/player")
        return data.get("MatchID") if data else None
    
    async def get_current_match_id(self) -> Optional[str]:
        """Get current match ID (pregame or coregame)."""
        match_id = await self.get_coregame_match_id()
        if match_id:
            return match_id
        return await self.get_pregame_match_id()
    
    async def get_pregame_match(self, match_id: str) -> Optional[dict]:
        """Get pregame match details."""
        return await self._request("GET", f"/pregame/v1/matches/{match_id}")
    
    async def get_coregame_match(self, match_id: str) -> Optional[dict]:
        """Get current game match details."""
        return await self._request("GET", f"/core-game/v1/matches/{match_id}")
    
    async def get_current_match_info(self) -> Optional[MatchInfo]:
        """Get current match information."""
        match_id = await self.get_coregame_match_id()
        if match_id:
            data = await self.get_coregame_match(match_id)
            if data:
                return self._parse_match_info(match_id, data)
        
        match_id = await self.get_pregame_match_id()
        if match_id:
            data = await self.get_pregame_match(match_id)
            if data:
                return self._parse_match_info(match_id, data)
        
        return None
    
    def _parse_match_info(self, match_id: str, data: dict) -> MatchInfo:
        """Parse match info from API response."""
        players = []
        
        for player_data in data.get("Players", []):
            players.append(MatchPlayer(
                puuid=player_data.get("Subject", ""),
                team_id=player_data.get("TeamID", ""),
                agent_id=player_data.get("CharacterID", ""),
                player_name=player_data.get("PlayerIdentity", {}).get("PlayerCardID"),
            ))
        
        return MatchInfo(
            match_id=match_id,
            map_id=data.get("MapID", ""),
            game_mode=data.get("ModeID", data.get("Mode", "")),
            players=players,
        )
    
    # ============================================
    # Post-Match APIs
    # ============================================
    
    async def get_match_history(self, puuid: Optional[str] = None, count: int = 10) -> Optional[dict]:
        """
        Get match history.
        
        Note: This requires PD (Player Data) API access which uses different auth.
        For now, returns None as it needs additional implementation.
        """
        # This would need to call the PD API with different authentication
        # https://pd.{region}.a.pvp.net/match-history/v1/history/{puuid}
        logger.warning("Match history API not yet implemented")
        return None
    
    async def get_match_details(self, match_id: str) -> Optional[dict]:
        """
        Get detailed match results.
        
        Note: This requires PD API access.
        """
        logger.warning("Match details API not yet implemented")
        return None


class ValorantClientManager:
    """
    Manages Valorant client connection with auto-reconnect.
    """
    
    def __init__(self):
        """Initialize manager."""
        self.client = ValorantClient()
        self._reconnect_task: Optional[asyncio.Task] = None
        self._on_connect_callback = None
        self._on_disconnect_callback = None
    
    def on_connect(self, callback):
        """Set callback for when client connects."""
        self._on_connect_callback = callback
    
    def on_disconnect(self, callback):
        """Set callback for when client disconnects."""
        self._on_disconnect_callback = callback
    
    async def start(self) -> bool:
        """Start client with auto-reconnect."""
        connected = await self.client.connect()
        if connected and self._on_connect_callback:
            await self._on_connect_callback()
        return connected
    
    async def stop(self) -> None:
        """Stop client and cleanup."""
        if self._reconnect_task:
            self._reconnect_task.cancel()
        await self.client.disconnect()
    
    async def wait_for_connection(self, timeout: float = 120.0) -> bool:
        """
        Wait for Valorant to start and connect.
        
        Args:
            timeout: Maximum time to wait
            
        Returns:
            True if connected
        """
        import time
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            if await self.client.connect():
                if self._on_connect_callback:
                    await self._on_connect_callback()
                return True
            await asyncio.sleep(2.0)
        
        return False

