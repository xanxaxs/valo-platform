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
    Client for Valorant local and remote APIs.
    
    Provides methods to interact with both the local Valorant client
    and the remote PD (Player Data) API.
    """
    
    def __init__(self):
        """Initialize client."""
        self.lockfile_reader = LockfileReader()
        self._lockfile_data: Optional[LockfileData] = None
        self._session: Optional[aiohttp.ClientSession] = None
        self._puuid: Optional[str] = None
        
        # Remote API (PD) credentials
        self._access_token: Optional[str] = None
        self._entitlements_token: Optional[str] = None
        self._shard: Optional[str] = None  # ap, na, eu, kr, etc.
        self._pd_session: Optional[aiohttp.ClientSession] = None
    
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
        Connect to Valorant local and remote APIs.
        
        Returns:
            True if connection successful
        """
        # Close existing sessions if any
        if self._session:
            await self._session.close()
            self._session = None
        if self._pd_session:
            await self._pd_session.close()
            self._pd_session = None
        
        self._lockfile_data = self.lockfile_reader.read()
        if not self._lockfile_data:
            logger.debug("Lockfile not found - Valorant not running")
            return False
        
        # Create local API session
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
                
                # Initialize remote PD API
                await self._init_remote_api()
                
                return True
        except Exception as e:
            logger.error(f"Failed to get user info: {e}")
        
        # Close session on failure
        if self._session:
            await self._session.close()
            self._session = None
        
        return False
    
    async def _init_remote_api(self) -> bool:
        """Initialize remote PD API with tokens from local API."""
        try:
            # Get entitlements (contains access token info)
            entitlements = await self._request("GET", "/entitlements/v1/token")
            if not entitlements:
                logger.warning("Failed to get entitlements")
                return False
            
            self._access_token = entitlements.get("accessToken")
            self._entitlements_token = entitlements.get("token")
            
            # Get region/shard from session
            session = await self._request("GET", "/product-session/v1/external-sessions")
            if session:
                # Find the Valorant session
                for key, value in session.items():
                    if isinstance(value, dict) and value.get("productId") == "valorant":
                        launch_args = value.get("launchConfiguration", {}).get("arguments", [])
                        for arg in launch_args:
                            if arg.startswith("-ares-deployment="):
                                self._shard = arg.split("=")[1]
                                break
                        break
            
            # Fallback to getting shard from pas token
            if not self._shard:
                pas_token = await self._request("GET", "/pas/v1/product/valorant")
                if pas_token and isinstance(pas_token, str):
                    # PAS token contains shard info, but let's default to ap for Japan
                    self._shard = "ap"
            
            if not self._shard:
                self._shard = "ap"  # Default for Japan
            
            if self._access_token and self._entitlements_token:
                # Create PD API session
                self._pd_session = aiohttp.ClientSession(
                    headers={
                        "Authorization": f"Bearer {self._access_token}",
                        "X-Riot-Entitlements-JWT": self._entitlements_token,
                        "X-Riot-ClientPlatform": "ew0KCSJwbGF0Zm9ybVR5cGUiOiAiUEMiLA0KCSJwbGF0Zm9ybU9TIjogIldpbmRvd3MiLA0KCSJwbGF0Zm9ybU9TVmVyc2lvbiI6ICIxMC4wLjE5MDQyLjEuMjU2LjY0Yml0IiwNCgkicGxhdGZvcm1DaGlwc2V0IjogIlVua25vd24iDQp9",
                        "X-Riot-ClientVersion": "release-09.10-shipping-12-2691923",
                        "Content-Type": "application/json",
                    },
                )
                logger.info(f"Remote PD API initialized (shard: {self._shard})")
                return True
            
            logger.warning("Failed to get access tokens for remote API")
            return False
            
        except Exception as e:
            logger.error(f"Failed to init remote API: {e}")
            return False
    
    async def disconnect(self) -> None:
        """Disconnect and cleanup."""
        if self._session and not self._session.closed:
            await self._session.close()
        if self._pd_session and not self._pd_session.closed:
            await self._pd_session.close()
        self._session = None
        self._pd_session = None
        self._lockfile_data = None
        self._puuid = None
        self._access_token = None
        self._entitlements_token = None
        self._shard = None
    
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
                    # 404 is expected when not in game
                    if response.status != 404:
                        logger.warning(f"API request failed: {response.status} {endpoint}")
                    return None
        except Exception as e:
            logger.error(f"API request error: {e}")
            return None
    
    async def _pd_request(
        self,
        method: str,
        endpoint: str,
        **kwargs,
    ) -> Optional[dict]:
        """
        Make request to remote PD API.
        
        Args:
            method: HTTP method
            endpoint: API endpoint (e.g., /match-history/v1/history/{puuid})
            **kwargs: Additional request arguments
            
        Returns:
            Response JSON or None
        """
        if not self._pd_session or not self._shard:
            logger.debug("PD session not initialized, trying to reinitialize...")
            if not await self._init_remote_api():
                logger.warning("Failed to initialize PD API")
                return None
        
        url = f"https://pd.{self._shard}.a.pvp.net{endpoint}"
        
        try:
            async with self._pd_session.request(method, url, **kwargs) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 400:
                    # Token expired, try to refresh
                    logger.info("PD API token expired, refreshing...")
                    if await self._init_remote_api():
                        # Retry request
                        async with self._pd_session.request(method, url, **kwargs) as retry_response:
                            if retry_response.status == 200:
                                return await retry_response.json()
                    logger.warning(f"PD API request failed after refresh: {response.status}")
                    return None
                else:
                    logger.warning(f"PD API request failed: {response.status} {endpoint}")
                    return None
        except Exception as e:
            logger.error(f"PD API request error: {e}")
            return None
    
    # ============================================
    # User/Account APIs
    # ============================================
    
    async def get_user_info(self) -> Optional[PlayerInfo]:
        """Get current user info."""
        # Try the entitlements endpoint first (more reliable)
        data = await self._request("GET", "/entitlements/v1/token")
        if data and isinstance(data, dict):
            try:
                # Get PUUID from entitlements
                puuid = data.get("subject", "")
                if puuid:
                    # Get player name from chat session
                    session_data = await self._request("GET", "/chat/v1/session")
                    game_name = ""
                    tag_line = ""
                    if session_data and isinstance(session_data, dict):
                        game_name = session_data.get("game_name", "")
                        tag_line = session_data.get("game_tag", "")
                    
                    return PlayerInfo(
                        puuid=puuid,
                        game_name=game_name or "Player",
                        tag_line=tag_line or "0000",
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
        """Get current game state (supports coach mode)."""
        # Method 1: Try direct game API (works for normal play)
        coregame = await self._request("GET", "/core-game/v1/player/" + (self._puuid or ""))
        if coregame and isinstance(coregame, dict) and coregame.get("MatchID"):
            logger.debug(f"INGAME detected via core-game API, MatchID: {coregame.get('MatchID')}")
            return GameState.INGAME
        
        pregame = await self._request("GET", "/pregame/v1/player/" + (self._puuid or ""))
        if pregame and isinstance(pregame, dict) and pregame.get("MatchID"):
            logger.debug(f"PREGAME detected, MatchID: {pregame.get('MatchID')}")
            return GameState.PREGAME
        
        # Method 2: Try presence API (works for coach/spectator mode)
        state = await self._get_state_from_presence()
        if state != GameState.MENUS:
            return state
        
        return GameState.MENUS
    
    async def _get_state_from_presence(self) -> GameState:
        """Get game state from presence data."""
        state, _ = await self._get_state_from_presence_debug()
        return state
    
    async def _get_state_from_presence_debug(self) -> tuple[GameState, Optional[dict]]:
        """Get game state from presence data with debug info."""
        presences = await self._request("GET", "/chat/v4/presences")
        
        if presences and isinstance(presences, dict):
            for presence in presences.get("presences", []):
                if presence.get("puuid") == self._puuid:
                    private_b64 = presence.get("private")
                    if private_b64:
                        try:
                            import base64
                            import json
                            private_json = base64.b64decode(private_b64).decode("utf-8")
                            private_data = json.loads(private_json)
                            
                            # Check multiple locations for session state
                            # 1. matchPresenceData.sessionLoopState (for coach/spectator)
                            match_presence = private_data.get("matchPresenceData", {})
                            session_state = match_presence.get("sessionLoopState", "")
                            
                            # 2. Fallback to top-level sessionLoopState
                            if not session_state:
                                session_state = private_data.get("sessionLoopState", "")
                            
                            # 3. Check partyOwnerSessionLoopState (coach sees party owner's state)
                            if not session_state:
                                party_presence = private_data.get("partyPresenceData", {})
                                session_state = party_presence.get("partyOwnerSessionLoopState", "")
                            
                            if session_state == "INGAME":
                                return GameState.INGAME, private_data
                            elif session_state == "PREGAME":
                                return GameState.PREGAME, private_data
                            
                            return GameState.MENUS, private_data
                        except Exception as e:
                            return GameState.MENUS, {"error": str(e), "raw": private_b64[:50]}
                    break
        
        return GameState.MENUS, None
    
    async def get_presence(self) -> Optional[dict]:
        """Get presence info (includes game state)."""
        return await self._request("GET", "/chat/v6/presences")
    
    async def get_presence_data(self) -> Optional[dict]:
        """Get parsed presence data for current player."""
        presences = await self._request("GET", "/chat/v4/presences")
        
        if presences and isinstance(presences, dict):
            for presence in presences.get("presences", []):
                if presence.get("puuid") == self._puuid:
                    private_b64 = presence.get("private")
                    if private_b64:
                        try:
                            import base64
                            import json
                            private_json = base64.b64decode(private_b64).decode("utf-8")
                            return json.loads(private_json)
                        except Exception:
                            pass
                    break
        return None
    
    # ============================================
    # Match APIs
    # ============================================
    
    async def get_pregame_match_id(self) -> Optional[str]:
        """Get pregame match ID."""
        # Try direct API first (works for coach)
        data = await self._request("GET", "/pregame/v1/player/" + (self._puuid or ""))
        if data and isinstance(data, dict) and data.get("MatchID"):
            return data.get("MatchID")
        
        # Fallback to presence
        return await self._get_match_id_from_presence()
    
    async def get_coregame_match_id(self) -> Optional[str]:
        """Get current game match ID."""
        # Try direct API first (works for coach)
        data = await self._request("GET", "/core-game/v1/player/" + (self._puuid or ""))
        if data and isinstance(data, dict) and data.get("MatchID"):
            return data.get("MatchID")
        
        # Fallback to presence
        return await self._get_match_id_from_presence()
    
    async def _get_match_id_from_presence(self) -> Optional[str]:
        """Get match ID from presence data."""
        presences = await self._request("GET", "/chat/v4/presences")
        
        if presences and isinstance(presences, dict):
            for presence in presences.get("presences", []):
                if presence.get("puuid") == self._puuid:
                    private_b64 = presence.get("private")
                    if private_b64:
                        try:
                            import base64
                            import json
                            private_json = base64.b64decode(private_b64).decode("utf-8")
                            private_data = json.loads(private_json)
                            
                            match_id = private_data.get("matchId")
                            if match_id:
                                return match_id
                        except Exception:
                            pass
                    break
        
        return None
    
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
    
    async def get_current_match_data(self, match_id: str) -> Optional[dict]:
        """
        Get full match data including all players.
        Works for both regular players and spectators/coaches.
        
        Args:
            match_id: Match ID
            
        Returns:
            Full match data dict or None
        """
        # Try core-game API first
        data = await self._request("GET", f"/core-game/v1/matches/{match_id}")
        if data:
            return data
        
        # Try pregame API
        data = await self._request("GET", f"/pregame/v1/matches/{match_id}")
        return data
    
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
    # Post-Match APIs (Remote PD API)
    # ============================================
    
    async def get_match_history(self, puuid: Optional[str] = None, count: int = 10) -> Optional[dict]:
        """
        Get match history for a player via remote PD API.
        
        Args:
            puuid: Player PUUID (defaults to current player)
            count: Number of matches to retrieve
            
        Returns:
            Match history dict or None
        """
        target_puuid = puuid or self._puuid
        if not target_puuid:
            logger.warning("No PUUID available for match history")
            return None
        
        logger.debug(f"Fetching match history for {target_puuid[:8]}...")
        data = await self._pd_request(
            "GET", 
            f"/match-history/v1/history/{target_puuid}?endIndex={count}"
        )
        
        if data:
            history_count = len(data.get("History", []))
            logger.info(f"Got {history_count} matches in history for {target_puuid[:8]}")
        else:
            logger.debug(f"No match history data returned for {target_puuid[:8]}")
        
        return data
    
    async def get_match_details(self, match_id: str) -> Optional[dict]:
        """
        Get detailed match results via remote PD API.
        
        Args:
            match_id: Match ID to get details for
            
        Returns:
            Match details dict or None
        """
        logger.debug(f"Fetching match details for {match_id[:8]}...")
        data = await self._pd_request("GET", f"/match-details/v1/matches/{match_id}")
        
        if data:
            logger.info(f"Got match details for {match_id[:8]}")
        else:
            logger.debug(f"No match details returned for {match_id[:8]}")
        
        return data


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

