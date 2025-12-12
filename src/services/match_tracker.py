"""
Match Tracker Service.

Orchestrates match tracking with synchronized audio recording.
"""

import asyncio
import json
import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from sqlalchemy.orm import Session

from ..api.client import GameState, MatchInfo, ValorantClient
from ..api.websocket import ValorantWebSocket
from ..db.models import Match, MatchCategory, MatchResult, PlayerMatchStats, Round
from ..sync.sync_recorder import RecordingConfig, SyncRecorder
from ..sync.timeline import EventType, TimelineSync

# 絶対インポート（パッケージルートから）
from config.settings import settings

logger = logging.getLogger(__name__)


class MatchTrackerService:
    """
    Service for tracking matches with synchronized audio.
    
    Monitors game state, records audio during matches,
    and saves all data to the database.
    """
    
    def __init__(
        self,
        client: ValorantClient,
        session: Session,
        recordings_dir: Path,
    ):
        """
        Initialize match tracker.
        
        Args:
            client: Valorant API client
            session: Database session
            recordings_dir: Directory for audio recordings
        """
        self.client = client
        self.session = session
        self.recordings_dir = recordings_dir
        
        # Components - Audio recording with settings
        audio_config = RecordingConfig(
            sample_rate=settings.audio.sample_rate,
            channels=settings.audio.channels,
            device=settings.audio.device_name,
        )
        self.recorder = SyncRecorder(
            output_dir=recordings_dir,
            config=audio_config,
            session=session,
        )
        self.timeline = TimelineSync()
        self.websocket: Optional[ValorantWebSocket] = None
        
        # State
        self._is_tracking = False
        self._current_match_id: Optional[str] = None
        self._current_match_info: Optional[MatchInfo] = None
        self._last_game_state = GameState.UNKNOWN
        self._poll_task: Optional[asyncio.Task] = None
        
        # Coach mode: cache player PUUIDs for later match details retrieval
        self._cached_player_puuids: list[str] = []
        self._is_coach_mode = False
        
        # Cache match data during game (scores reset after match ends)
        self._cached_map_name: str = "Unknown"
        self._cached_ally_score: int = 0
        self._cached_enemy_score: int = 0
        self._real_match_id: Optional[str] = None
        self._cached_players_data: list = []
        
        # Callbacks
        self._on_match_start: Optional[Callable] = None
        self._on_match_end: Optional[Callable] = None
        self._on_round_start: Optional[Callable] = None
        self._on_round_end: Optional[Callable] = None
        
        # Background tasks for async data fetching
        self._background_tasks: list[asyncio.Task] = []
    
    @property
    def is_tracking(self) -> bool:
        """Check if currently tracking a match."""
        return self._is_tracking
    
    @property
    def current_match_id(self) -> Optional[str]:
        """Get current match ID."""
        return self._current_match_id
    
    # ============================================
    # Callbacks
    # ============================================
    
    def on_match_start(self, callback: Callable):
        """Set callback for match start."""
        self._on_match_start = callback
    
    def on_match_end(self, callback: Callable):
        """Set callback for match end."""
        self._on_match_end = callback
    
    def on_round_start(self, callback: Callable):
        """Set callback for round start."""
        self._on_round_start = callback
    
    def on_round_end(self, callback: Callable):
        """Set callback for round end."""
        self._on_round_end = callback
    
    # ============================================
    # Main Control
    # ============================================
    
    async def start(self) -> bool:
        """
        Start match tracking service.
        
        Returns:
            True if started successfully
        """
        if self._is_tracking:
            logger.warning("Already tracking")
            return False
        
        if not self.client.is_connected:
            logger.error("Client not connected")
            return False
        
        self._is_tracking = True
        
        # Start game state polling
        self._poll_task = asyncio.create_task(self._poll_game_state())
        
        logger.info("Match tracker started")
        return True
    
    async def stop(self) -> None:
        """Stop match tracking service."""
        self._is_tracking = False
        
        # Stop polling
        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
        
        # Cancel background tasks (but let them finish gracefully)
        for task in self._background_tasks:
            if not task.done():
                logger.info("Waiting for background task to complete...")
                try:
                    await asyncio.wait_for(task, timeout=5.0)
                except asyncio.TimeoutError:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
        self._background_tasks.clear()
        
        # Stop any active recording
        if self.recorder.is_recording:
            self.recorder.stop_recording()
        
        logger.info("Match tracker stopped")
    
    async def _poll_game_state(self) -> None:
        """Poll game state and detect changes."""
        while self._is_tracking:
            try:
                current_state = await self.client.get_game_state()
                
                # Update cached score while in game
                if current_state == GameState.INGAME and self._current_match_id:
                    await self._update_cached_score()
                
                if current_state != self._last_game_state:
                    await self._handle_state_change(self._last_game_state, current_state)
                    self._last_game_state = current_state
                
                await asyncio.sleep(2.0)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Poll error: {e}")
                await asyncio.sleep(5.0)
    
    async def _update_cached_score(self) -> None:
        """Update cached score from presence data during match."""
        presence_data = await self.client.get_presence_data()
        if presence_data:
            party_data = presence_data.get("partyPresenceData", {})
            new_ally = party_data.get("partyOwnerMatchScoreAllyTeam", 0)
            new_enemy = party_data.get("partyOwnerMatchScoreEnemyTeam", 0)
            
            # Only update if scores changed
            if new_ally != self._cached_ally_score or new_enemy != self._cached_enemy_score:
                self._cached_ally_score = new_ally
                self._cached_enemy_score = new_enemy
                logger.debug(f"Score updated: {new_ally}-{new_enemy}")
    
    async def _handle_state_change(self, old_state: GameState, new_state: GameState) -> None:
        """
        Handle game state transition.
        
        Args:
            old_state: Previous game state
            new_state: New game state
        """
        logger.info(f"Game state: {old_state.value} -> {new_state.value}")
        
        # MENUS/PREGAME -> INGAME: Match started
        if new_state == GameState.INGAME and old_state != GameState.INGAME:
            await self._on_match_started()
        
        # INGAME -> MENUS: Match ended
        elif old_state == GameState.INGAME and new_state == GameState.MENUS:
            await self._on_match_ended()
    
    # ============================================
    # Match Events
    # ============================================
    
    async def _on_match_started(self) -> None:
        """Handle match start."""
        # Get match info
        match_id = await self.client.get_current_match_id()
        
        # For coach mode: generate match ID from party ID + timestamp if not available
        if not match_id:
            import time
            presence_data = await self.client.get_presence_data()
            if presence_data:
                party_id = presence_data.get("partyId", "unknown")
                match_map = presence_data.get("matchPresenceData", {}).get("matchMap", "unknown")
                # Create a unique ID for this match
                match_id = f"coach_{party_id[:8]}_{int(time.time())}"
                logger.info(f"Coach mode: Generated match ID {match_id} (map: {match_map})")
            else:
                match_id = f"unknown_{int(time.time())}"
                logger.warning(f"Could not get match info, using generated ID: {match_id}")
        
        self._current_match_id = match_id
        self._current_match_info = await self.client.get_current_match_info()
        
        # Cache player PUUIDs for coach mode (to retrieve match details later)
        await self._cache_player_puuids()
        
        # Cache map name at match start
        presence_data = await self.client.get_presence_data()
        if presence_data:
            match_map = presence_data.get("matchPresenceData", {}).get("matchMap", "")
            self._cached_map_name = self._get_map_name(match_map)
        
        logger.info(f"Match started: {match_id} (map: {self._cached_map_name})")
        
        # Initialize timeline
        self.timeline.reset()
        self.timeline.mark_match_start(match_id)
        
        # Start recording
        if self.recorder.start_recording(match_id):
            logger.info("Audio recording started")
        else:
            logger.warning("Failed to start audio recording")
        
        # Callback
        if self._on_match_start:
            try:
                if asyncio.iscoroutinefunction(self._on_match_start):
                    await self._on_match_start(match_id, self._current_match_info)
                else:
                    self._on_match_start(match_id, self._current_match_info)
            except Exception as e:
                logger.error(f"Match start callback error: {e}")
    
    async def _on_match_ended(self) -> None:
        """Handle match end."""
        if not self._current_match_id:
            return
        
        temp_match_id = self._current_match_id
        logger.info(f"Match ended: {temp_match_id}")
        
        # Stop recording immediately
        audio_path = self.recorder.stop_recording()
        if audio_path:
            logger.info(f"Audio saved: {audio_path}")
        
        # Use cached scores (presence data may reset after match)
        ally_score = self._cached_ally_score
        enemy_score = self._cached_enemy_score
        
        # Try to get latest scores from presence (may still be available)
        presence_data = await self.client.get_presence_data()
        if presence_data:
            party_data = presence_data.get("partyPresenceData", {})
            new_ally = party_data.get("partyOwnerMatchScoreAllyTeam", 0)
            new_enemy = party_data.get("partyOwnerMatchScoreEnemyTeam", 0)
            if new_ally > 0 or new_enemy > 0:
                ally_score = new_ally
                enemy_score = new_enemy
        
        result = "WIN" if ally_score > enemy_score else "LOSS" if ally_score < enemy_score else "DRAW"
        
        # Mark timeline
        self.timeline.mark_match_end(
            result=result,
            ally_score=ally_score,
            enemy_score=enemy_score,
        )
        
        # Save basic match info IMMEDIATELY (no waiting)
        saved_match = await self._save_match_basic(temp_match_id, ally_score, enemy_score)
        
        if saved_match:
            logger.info(f"Basic match saved: {temp_match_id} | Score: {ally_score}-{enemy_score} | Result: {result}")
            
            # Start background task for detailed data fetching
            # Copy necessary data for the background task
            bg_data = {
                "temp_match_id": temp_match_id,
                "cached_player_puuids": self._cached_player_puuids.copy(),
                "cached_players_data": self._cached_players_data.copy(),
                "real_match_id": self._real_match_id,
                "is_coach_mode": self._is_coach_mode,
                "cached_map_name": self._cached_map_name,  # For verifying the correct match
            }
            
            task = asyncio.create_task(
                self._fetch_and_update_match_details(bg_data)
            )
            self._background_tasks.append(task)
            
            # Clean up completed tasks
            self._background_tasks = [t for t in self._background_tasks if not t.done()]
            
            logger.info("Started background task for detailed match data")
        else:
            logger.error(f"Failed to save basic match info: {temp_match_id}")
        
        # Callback
        if self._on_match_end:
            try:
                if asyncio.iscoroutinefunction(self._on_match_end):
                    await self._on_match_end(temp_match_id)
                else:
                    self._on_match_end(temp_match_id)
            except Exception as e:
                logger.error(f"Match end callback error: {e}")
        
        # Reset state immediately (don't wait for background task)
        self._current_match_id = None
        self._current_match_info = None
        self._cached_player_puuids = []
        self._is_coach_mode = False
        self._cached_map_name = "Unknown"
        self._cached_ally_score = 0
        self._cached_enemy_score = 0
        self._real_match_id = None
        self._cached_players_data = []
    
    # ============================================
    # Round Events
    # ============================================
    
    def handle_round_start(self, round_number: int) -> None:
        """
        Handle round start event.
        
        Args:
            round_number: Round number starting
        """
        logger.info(f"Round {round_number} started")
        
        self.timeline.mark_round_start(round_number)
        self.recorder.mark_round_start(round_number)
        
        if self._on_round_start:
            try:
                self._on_round_start(round_number)
            except Exception as e:
                logger.error(f"Round start callback error: {e}")
    
    def handle_round_end(
        self,
        round_number: int,
        result: str,
        win_condition: Optional[str] = None,
    ) -> None:
        """
        Handle round end event.
        
        Args:
            round_number: Round number ended
            result: WIN or LOSS
            win_condition: How the round was won
        """
        logger.info(f"Round {round_number} ended: {result}")
        
        self.timeline.mark_round_end(round_number, result, win_condition)
        self.recorder.mark_round_end(round_number)
        
        if self._on_round_end:
            try:
                self._on_round_end(round_number, result)
            except Exception as e:
                logger.error(f"Round end callback error: {e}")
    
    # ============================================
    # Kill Events
    # ============================================
    
    def handle_kill(
        self,
        killer_puuid: str,
        victim_puuid: str,
        location_x: int,
        location_y: int,
        weapon_id: Optional[str] = None,
        assistants: Optional[list[str]] = None,
    ) -> None:
        """
        Handle kill event.
        
        Args:
            killer_puuid: Killer's PUUID
            victim_puuid: Victim's PUUID
            location_x: Kill X coordinate
            location_y: Kill Y coordinate
            weapon_id: Weapon used
            assistants: List of assistant PUUIDs
        """
        self.timeline.add_kill_event(
            killer_puuid=killer_puuid,
            victim_puuid=victim_puuid,
            location_x=location_x,
            location_y=location_y,
            weapon_id=weapon_id,
            assistants=assistants,
        )
    
    # ============================================
    # Coach Mode Helpers
    # ============================================
    
    async def _cache_player_puuids(self) -> None:
        """Cache player PUUIDs for later match details retrieval (coach mode)."""
        presence_data = await self.client.get_presence_data()
        if not presence_data:
            return
        
        # Check if we're in coach mode
        party_data = presence_data.get("partyPresenceData", {})
        custom_game_team = party_data.get("customGameTeam", "")
        self._is_coach_mode = "Coach" in custom_game_team
        
        if self._is_coach_mode:
            logger.info(f"Coach mode detected: {custom_game_team}")
        
        # Try to get player PUUIDs from current match info
        if self._current_match_info and self._current_match_info.players:
            self._cached_player_puuids = [
                p.puuid for p in self._current_match_info.players
                if p.puuid != self.client.puuid
            ]
            logger.info(f"Cached {len(self._cached_player_puuids)} player PUUIDs from match info")
            return
        
        # For coach mode: try to get real match ID and fetch match data
        real_match_id = await self._get_real_match_id()
        if real_match_id:
            logger.info(f"Found real match ID: {real_match_id}")
            self._real_match_id = real_match_id
            match_data = await self.client.get_current_match_data(real_match_id)
            if match_data and match_data.get("Players"):
                players = match_data["Players"]
                self._cached_player_puuids = [
                    p.get("Subject") for p in players
                    if p.get("Subject") and p.get("Subject") != self.client.puuid
                ]
                # Cache full player data for stats
                self._cached_players_data = players
                logger.info(f"Cached {len(self._cached_player_puuids)} player PUUIDs from match API")
    
    async def _get_real_match_id(self) -> Optional[str]:
        """Try to get the real match ID (for coach mode)."""
        # Method 1: Try core-game player endpoint
        coregame = await self.client._request("GET", f"/core-game/v1/player/{self.client.puuid}")
        if coregame and isinstance(coregame, dict) and coregame.get("MatchID"):
            return coregame.get("MatchID")
        
        # Method 2: Check help endpoint for events with match IDs
        help_data = await self.client._request("GET", "/help")
        if help_data and isinstance(help_data, dict):
            events = help_data.get("events", {})
            for event_name in events:
                if "core-game" in event_name and "matches" in event_name:
                    # Extract match ID from event name
                    parts = event_name.split("_")
                    if len(parts) >= 5:
                        potential_id = parts[-1]
                        if len(potential_id) > 20:  # Match IDs are UUIDs
                            return potential_id
        
        return None
    
    async def _get_match_details_with_retry(
        self,
        match_id: str,
        max_retries: int = 8,
        delay_seconds: float = 15.0,
    ) -> tuple[Optional[dict], Optional[str]]:
        """
        Get match details with retry logic.
        
        For generated match IDs, tries to get real match ID from history.
        Handles slow API responses after match end.
        
        Args:
            match_id: Match ID (may be generated)
            max_retries: Maximum retry attempts
            delay_seconds: Delay between retries
            
        Returns:
            Tuple of (match_details, real_match_id) - real_match_id is set if different from input
        """
        is_generated_id = match_id.startswith("coach_") or match_id.startswith("unknown_")
        real_match_id = self._real_match_id  # Use cached real ID if available
        
        # For generated IDs, try to get real match ID from history
        if is_generated_id:
            logger.info("Generated match ID detected, trying to get real match ID...")
            
            # Try multiple times with increasing delay (API may take time to update)
            for history_attempt in range(3):
                if history_attempt > 0:
                    wait_time = 10.0 * (history_attempt + 1)
                    logger.info(f"Waiting {wait_time}s for match history to update...")
                    await asyncio.sleep(wait_time)
                
                found_id = await self._get_real_match_id_from_history()
                if found_id:
                    real_match_id = found_id
                    match_id = found_id
                    logger.info(f"Found real match ID: {real_match_id}")
                    break
            
            if not real_match_id:
                logger.warning("Could not find real match ID from history, will retry later")
        
        # Try direct API with retries
        for attempt in range(1, max_retries + 1):
            # If we still don't have real match ID, try again
            if is_generated_id and not real_match_id:
                found_id = await self._get_real_match_id_from_history()
                if found_id:
                    real_match_id = found_id
                    match_id = found_id
                    logger.info(f"Found real match ID on retry: {real_match_id}")
            
            if not match_id or match_id.startswith("coach_") or match_id.startswith("unknown_"):
                logger.debug(f"Skipping API call, no valid match ID yet (attempt {attempt})")
                if attempt < max_retries:
                    await asyncio.sleep(delay_seconds)
                continue
            
            try:
                logger.info(f"Fetching match details (attempt {attempt}/{max_retries})...")
                details = await self.client.get_match_details(match_id)
                if details:
                    logger.info("Successfully retrieved match details")
                    return details, real_match_id
            except Exception as e:
                logger.warning(f"Match details not available: {e}")
            
            if attempt < max_retries:
                await asyncio.sleep(delay_seconds)
        
        logger.warning("Failed to fetch match details after all retries")
        return None, real_match_id
    
    async def _get_real_match_id_from_history(self) -> Optional[str]:
        """
        Get the most recent match ID from player's match history.
        
        For coach mode, uses cached player PUUIDs since coach's own history
        won't contain the match.
        
        Returns:
            Match ID or None
        """
        # Method 1: Try own match history (works for normal mode)
        try:
            history = await self.client.get_match_history(self.client.puuid, count=3)
            if history and history.get("History"):
                latest = history["History"][0]
                match_id = latest.get("MatchID")
                if match_id:
                    logger.info(f"Found latest match in own history: {match_id}")
                    return match_id
        except Exception as e:
            logger.debug(f"Failed to get own match history: {e}")
        
        # Method 2: Try other players' histories (coach mode)
        if self._cached_player_puuids:
            logger.info(f"Trying {len(self._cached_player_puuids)} cached player PUUIDs...")
            for puuid in self._cached_player_puuids[:5]:  # Try up to 5 players
                try:
                    history = await self.client.get_match_history(puuid, count=3)
                    if history and history.get("History"):
                        latest = history["History"][0]
                        match_id = latest.get("MatchID")
                        if match_id:
                            logger.info(f"Found match ID from player {puuid[:8]}: {match_id}")
                            return match_id
                except Exception as e:
                    logger.debug(f"Failed to get history for {puuid[:8]}: {e}")
                await asyncio.sleep(0.5)  # Rate limiting
        
        return None
    
    # ============================================
    # Database Operations
    # ============================================
    
    async def _save_match_basic(self, match_id: str, ally_score: int, enemy_score: int) -> Optional[Match]:
        """
        Save basic match info immediately (no waiting for API).
        
        Args:
            match_id: Match ID to save
            ally_score: Cached ally score
            enemy_score: Cached enemy score
            
        Returns:
            Saved Match object or None
        """
        map_name = self._cached_map_name
        map_id = ""
        
        if self._current_match_info:
            map_id = self._current_match_info.map_id
        
        result = MatchResult.WIN if ally_score > enemy_score else MatchResult.LOSE if ally_score < enemy_score else MatchResult.DRAW
        
        try:
            match = Match(
                match_id=match_id,
                map_id=map_id,
                map_name=map_name,
                queue_id="custom",
                game_start_millis=int(datetime.now().timestamp() * 1000),
                game_length_millis=0,
                result=result,
                ally_score=ally_score,
                enemy_score=enemy_score,
                completion_state="Pending",  # Will be updated when details are fetched
                is_coach_view=self._is_coach_mode,
                category=MatchCategory.CUSTOM,
            )
            
            self.session.add(match)
            self.session.commit()
            
            logger.info(f"Basic match saved: {match_id} | {map_name} | {ally_score}-{enemy_score}")
            return match
            
        except Exception as e:
            logger.error(f"Failed to save basic match: {e}")
            self.session.rollback()
            return None
    
    async def _fetch_and_update_match_details(self, bg_data: dict) -> None:
        """
        Background task to fetch match details and update database.
        
        For custom/coach matches, searches other players' histories for
        matches with empty queue ID (custom games).
        
        Args:
            bg_data: Dictionary with cached data needed for fetching
        """
        temp_match_id = bg_data["temp_match_id"]
        cached_puuids = bg_data["cached_player_puuids"]
        real_match_id_cache = bg_data["real_match_id"]
        is_coach_mode = bg_data.get("is_coach_mode", False)
        cached_map_name = bg_data.get("cached_map_name", "Unknown")
        
        logger.info(f"Background task: Fetching details for {temp_match_id} (coach: {is_coach_mode}, map: {cached_map_name})")
        
        # Wait for API to update with match data
        await asyncio.sleep(15.0)
        
        try:
            match_details = None
            real_match_id = real_match_id_cache
            
            # For coach mode or generated IDs, search for custom match
            is_generated_id = temp_match_id.startswith("coach_") or temp_match_id.startswith("unknown_")
            
            if is_generated_id or is_coach_mode:
                logger.info("Background: Searching for custom match in player histories...")
                match_details, real_match_id = await self._find_custom_match(
                    cached_puuids, cached_map_name
                )
            else:
                # Normal mode - try direct fetch
                match_details, real_match_id = await self._get_match_details_for_background(
                    temp_match_id, cached_puuids, real_match_id_cache
                )
            
            if match_details:
                # Update database with details
                await self._update_match_with_details(temp_match_id, match_details, real_match_id)
                logger.info(f"Background task: Successfully updated {temp_match_id} with details")
            else:
                # Mark as completed even without details
                self._mark_match_completed(temp_match_id)
                logger.warning(f"Background task: Could not fetch details for {temp_match_id}")
                
        except Exception as e:
            logger.error(f"Background task error for {temp_match_id}: {e}")
            self._mark_match_completed(temp_match_id)
    
    async def _find_custom_match(
        self,
        cached_puuids: list[str],
        expected_map: str,
    ) -> tuple[Optional[dict], Optional[str]]:
        """
        Find custom match by searching player histories.
        
        Custom matches have empty queue ID. Matches by map name to verify.
        
        Args:
            cached_puuids: List of player PUUIDs to search
            expected_map: Expected map name for verification
            
        Returns:
            Tuple of (match_details, match_id)
        """
        # Get additional players from presences
        all_puuids = list(cached_puuids)
        
        try:
            presences = await self.client._request("GET", "/chat/v4/presences")
            if presences and presences.get("presences"):
                for p in presences["presences"]:
                    puuid = p.get("puuid")
                    if puuid and puuid != self.client.puuid and puuid not in all_puuids:
                        all_puuids.append(puuid)
        except Exception as e:
            logger.debug(f"Failed to get presences: {e}")
        
        logger.info(f"Background: Searching {len(all_puuids)} players for custom match on {expected_map}")
        
        # Track matches we've already checked
        checked_matches = set()
        
        # Search with retries (match may take time to appear in history)
        for attempt in range(5):
            if attempt > 0:
                logger.info(f"Background: Retry {attempt + 1}/5, waiting 20s...")
                await asyncio.sleep(20.0)
            
            for puuid in all_puuids[:20]:  # Check up to 20 players
                try:
                    history = await self.client.get_match_history(puuid, count=5)
                    if not history or not history.get("History"):
                        continue
                    
                    for match in history["History"]:
                        match_id = match.get("MatchID", "")
                        queue_id = match.get("QueueID", "")
                        
                        # Skip if already checked
                        if match_id in checked_matches:
                            continue
                        checked_matches.add(match_id)
                        
                        # Custom matches have empty queue ID
                        if queue_id == "" or queue_id is None:
                            # Verify by getting details and checking map
                            details = await self.client.get_match_details(match_id)
                            if not details:
                                continue
                            
                            match_info = details.get("matchInfo", {})
                            map_id = match_info.get("mapId", "")
                            
                            # Check if map matches
                            if self._map_matches(map_id, expected_map):
                                logger.info(f"Background: Found custom match {match_id} on {expected_map}")
                                return details, match_id
                            else:
                                logger.debug(f"Background: Custom match {match_id[:8]} is on different map: {map_id}")
                    
                except Exception as e:
                    logger.debug(f"Background: Error checking player {puuid[:8]}: {e}")
                
                await asyncio.sleep(0.3)  # Rate limiting
        
        logger.warning(f"Background: Could not find custom match on {expected_map}")
        return None, None
    
    def _map_matches(self, map_id: str, expected_map: str) -> bool:
        """Check if map ID matches expected map name."""
        map_id_lower = map_id.lower()
        expected_lower = expected_map.lower()
        
        # Direct match
        if expected_lower in map_id_lower:
            return True
        
        # Map name to ID mapping
        map_aliases = {
            "ascent": ["ascent"],
            "bind": ["duality", "bind"],
            "haven": ["triad", "haven"],
            "split": ["bonsai", "split"],
            "icebox": ["port", "icebox"],
            "breeze": ["foxtrot", "breeze"],
            "fracture": ["canyon", "fracture"],
            "pearl": ["pitt", "pearl"],
            "lotus": ["jam", "lotus"],
            "sunset": ["juliett", "sunset"],
            "abyss": ["infinity", "abyss"],
            "corrode": ["kilo", "corrode"],  # New map (internal name: Kilo)
        }
        
        for name, aliases in map_aliases.items():
            if expected_lower == name or expected_lower in aliases:
                for alias in aliases:
                    if alias in map_id_lower:
                        return True
        
        return False
    
    async def _get_match_details_for_background(
        self,
        match_id: str,
        cached_puuids: list[str],
        cached_real_id: Optional[str],
    ) -> tuple[Optional[dict], Optional[str]]:
        """
        Get match details for background task with retry logic.
        """
        is_generated_id = match_id.startswith("coach_") or match_id.startswith("unknown_")
        real_match_id = cached_real_id
        
        # Try to get real match ID from history
        if is_generated_id and not real_match_id:
            for attempt in range(5):
                if attempt > 0:
                    await asyncio.sleep(15.0)
                
                # Try own history first
                try:
                    history = await self.client.get_match_history(self.client.puuid, count=3)
                    if history and history.get("History"):
                        latest = history["History"][0]
                        found_id = latest.get("MatchID")
                        if found_id:
                            real_match_id = found_id
                            logger.info(f"Background: Found match ID from own history: {found_id}")
                            break
                except Exception as e:
                    logger.debug(f"Background: Own history failed: {e}")
                
                # Try cached player histories
                for puuid in cached_puuids[:5]:
                    try:
                        history = await self.client.get_match_history(puuid, count=3)
                        if history and history.get("History"):
                            latest = history["History"][0]
                            found_id = latest.get("MatchID")
                            if found_id:
                                real_match_id = found_id
                                logger.info(f"Background: Found match ID from player {puuid[:8]}: {found_id}")
                                break
                    except Exception as e:
                        logger.debug(f"Background: Player history failed: {e}")
                    await asyncio.sleep(0.5)
                
                if real_match_id:
                    break
        
        # Fetch match details
        fetch_id = real_match_id if real_match_id else match_id
        if fetch_id.startswith("coach_") or fetch_id.startswith("unknown_"):
            return None, real_match_id
        
        for attempt in range(5):
            try:
                details = await self.client.get_match_details(fetch_id)
                if details:
                    return details, real_match_id
            except Exception as e:
                logger.debug(f"Background: Match details attempt {attempt+1} failed: {e}")
            
            await asyncio.sleep(10.0)
        
        return None, real_match_id
    
    async def _update_match_with_details(
        self,
        temp_match_id: str,
        match_details: dict,
        real_match_id: Optional[str],
    ) -> None:
        """
        Update match record with detailed data from API.
        """
        try:
            # Get the match record
            match = self.session.query(Match).filter_by(match_id=temp_match_id).first()
            if not match:
                logger.warning(f"Match {temp_match_id} not found for update")
                return
            
            # Update scores if available
            teams = match_details.get("teams", [])
            if len(teams) >= 2:
                match.ally_score = teams[0].get("roundsWon", match.ally_score)
                match.enemy_score = teams[1].get("roundsWon", match.enemy_score)
                match.result = (
                    MatchResult.WIN if match.ally_score > match.enemy_score
                    else MatchResult.LOSE if match.ally_score < match.enemy_score
                    else MatchResult.DRAW
                )
            
            match.completion_state = "Completed"
            
            # Save player stats with detailed analysis
            if match_details.get("players"):
                my_puuid = self.client.puuid
                my_team = None
                for player in match_details["players"]:
                    if player.get("subject") == my_puuid:
                        my_team = player.get("teamId")
                        break
                
                # Calculate detailed stats from round data
                detailed_stats = self._calculate_detailed_stats(match_details)
                
                for player in match_details["players"]:
                    puuid = player.get("subject", "")
                    team_id = player.get("teamId", "")
                    is_ally = team_id == my_team if my_team else False
                    
                    game_name = player.get("gameName", "Unknown")
                    tag_line = player.get("tagLine", "")
                    agent_id = player.get("characterId", "")
                    
                    stats_data = player.get("stats", {})
                    kills = stats_data.get("kills", 0)
                    deaths = stats_data.get("deaths", 0)
                    assists = stats_data.get("assists", 0)
                    score = stats_data.get("score", 0)
                    rounds_played = stats_data.get("roundsPlayed", 0)
                    
                    # Get detailed stats for this player
                    player_detailed = detailed_stats.get(puuid, {})
                    
                    # Calculate damage from roundDamage
                    round_damage = player.get("roundDamage", [])
                    total_damage = sum(rd.get("damage", 0) for rd in round_damage)
                    
                    stats = PlayerMatchStats(
                        id=f"{temp_match_id}_{puuid}",
                        match_id=temp_match_id,
                        puuid=puuid,
                        player_name=game_name,
                        tag_line=tag_line,
                        agent_id=agent_id,
                        agent_name=self._get_agent_name(agent_id),
                        team_id=team_id,
                        is_ally=is_ally,
                        kills=kills,
                        deaths=deaths,
                        assists=assists,
                        score=score,
                        rounds_played=rounds_played,
                        damage_dealt=total_damage,
                        # FK/FD/TrueFK
                        first_kills=player_detailed.get("first_kills", 0),
                        first_deaths=player_detailed.get("first_deaths", 0),
                        true_first_kills=player_detailed.get("true_first_kills", 0),
                        # Headshot stats
                        headshots=player_detailed.get("headshots", 0),
                        bodyshots=player_detailed.get("bodyshots", 0),
                        legshots=player_detailed.get("legshots", 0),
                        # Time-based K/D (JSON)
                        time_based_kd=json.dumps(player_detailed.get("time_based_kd", {})),
                    )
                    self.session.merge(stats)  # Use merge to update if exists
                
                logger.info(f"Updated {len(match_details['players'])} player stats with detailed analysis")
            
            # Save round results
            if match_details.get("roundResults"):
                my_puuid = self.client.puuid
                my_team = None
                for player in match_details.get("players", []):
                    if player.get("subject") == my_puuid:
                        my_team = player.get("teamId")
                        break
                
                for round_data in match_details["roundResults"]:
                    round_num = round_data.get("roundNum", 0)
                    winning_team = round_data.get("winningTeam", "")
                    round_result_str = round_data.get("roundResult", "")
                    
                    result = "WIN" if winning_team == my_team else "LOSS" if my_team else "UNKNOWN"
                    win_condition = self._map_win_condition(round_result_str)
                    
                    round_record = Round(
                        match_id=temp_match_id,
                        round_number=round_num,
                        result=result,
                        win_condition=win_condition,
                    )
                    self.session.add(round_record)
                
                logger.info(f"Saved {len(match_details['roundResults'])} rounds")
            
            # Save replay snapshots
            from .replay_service import ReplayService
            replay_service = ReplayService(self.session)
            snapshots_saved = replay_service.save_match_snapshots(temp_match_id, match_details)
            if snapshots_saved > 0:
                logger.info(f"Saved {snapshots_saved} replay snapshots")
            
            self.session.commit()
            logger.info(f"Match updated with details: {temp_match_id}")
            
        except Exception as e:
            logger.error(f"Failed to update match with details: {e}")
            self.session.rollback()
    
    def _mark_match_completed(self, match_id: str) -> None:
        """Mark match as completed even without details."""
        try:
            match = self.session.query(Match).filter_by(match_id=match_id).first()
            if match:
                match.completion_state = "Completed"
                self.session.commit()
        except Exception as e:
            logger.error(f"Failed to mark match completed: {e}")
            self.session.rollback()
    
    async def _save_match(self, match_id: str, match_details: Optional[dict] = None) -> Optional[Match]:
        """
        Save match data to database.
        
        Args:
            match_id: Match ID to save
            match_details: Optional match details from API
            
        Returns:
            Saved Match object or None
        """
        # Use cached map name (presence data resets after match)
        map_name = self._cached_map_name
        map_id = ""
        
        if self._current_match_info:
            map_id = self._current_match_info.map_id
        
        # Use cached scores (presence data resets after match)
        ally_score = self._cached_ally_score
        enemy_score = self._cached_enemy_score
        
        # Override with match_details if available
        if match_details:
            teams = match_details.get("teams", [])
            if len(teams) >= 2:
                ally_score = teams[0].get("roundsWon", ally_score)
                enemy_score = teams[1].get("roundsWon", enemy_score)
        
        result = MatchResult.WIN if ally_score > enemy_score else MatchResult.LOSE if ally_score < enemy_score else MatchResult.DRAW
        
        try:
            # Create match record
            match = Match(
                match_id=match_id,
                map_id=map_id,
                map_name=map_name,
                queue_id="custom",
                game_start_millis=int(datetime.now().timestamp() * 1000),
                game_length_millis=0,
                result=result,
                ally_score=ally_score,
                enemy_score=enemy_score,
                completion_state="Completed",
                is_coach_view=self._is_coach_mode,
                category=MatchCategory.CUSTOM,
            )
            
            self.session.add(match)
            
            # Save player stats
            players_saved = 0
            
            # Method 1: From match_details (best - has full stats including K/D/A and detailed analysis)
            if match_details and match_details.get("players"):
                logger.info("Saving player stats from match details API with detailed analysis")
                my_puuid = self.client.puuid
                
                # Find my team (for ally/enemy classification)
                my_team = None
                for player in match_details["players"]:
                    if player.get("subject") == my_puuid:
                        my_team = player.get("teamId")
                        break
                
                # Calculate detailed stats
                detailed_stats = self._calculate_detailed_stats(match_details)
                
                for player in match_details["players"]:
                    puuid = player.get("subject", "")
                    team_id = player.get("teamId", "")
                    is_ally = team_id == my_team if my_team else False
                    
                    # Get player identity
                    game_name = player.get("gameName", "Unknown")
                    tag_line = player.get("tagLine", "")
                    
                    # Get agent info
                    agent_id = player.get("characterId", "")
                    
                    # Get stats
                    stats_data = player.get("stats", {})
                    kills = stats_data.get("kills", 0)
                    deaths = stats_data.get("deaths", 0)
                    assists = stats_data.get("assists", 0)
                    score = stats_data.get("score", 0)
                    rounds_played = stats_data.get("roundsPlayed", 0)
                    
                    # Get detailed stats for this player
                    player_detailed = detailed_stats.get(puuid, {})
                    
                    # Calculate damage from roundDamage
                    round_damage = player.get("roundDamage", [])
                    total_damage = sum(rd.get("damage", 0) for rd in round_damage)
                    
                    stats = PlayerMatchStats(
                        id=f"{match_id}_{puuid}",
                        match_id=match_id,
                        puuid=puuid,
                        player_name=game_name,
                        tag_line=tag_line,
                        agent_id=agent_id,
                        agent_name=self._get_agent_name(agent_id),
                        team_id=team_id,
                        is_ally=is_ally,
                        kills=kills,
                        deaths=deaths,
                        assists=assists,
                        score=score,
                        rounds_played=rounds_played,
                        damage_dealt=total_damage,
                        # FK/FD/TrueFK
                        first_kills=player_detailed.get("first_kills", 0),
                        first_deaths=player_detailed.get("first_deaths", 0),
                        true_first_kills=player_detailed.get("true_first_kills", 0),
                        # Headshot stats
                        headshots=player_detailed.get("headshots", 0),
                        bodyshots=player_detailed.get("bodyshots", 0),
                        legshots=player_detailed.get("legshots", 0),
                        # Time-based K/D
                        time_based_kd=json.dumps(player_detailed.get("time_based_kd", {})),
                    )
                    self.session.add(stats)
                    players_saved += 1
            
            # Method 2: From match info (normal mode, during game)
            elif self._current_match_info and self._current_match_info.players:
                logger.info("Saving player stats from match info (no K/D/A)")
                my_puuid = self.client.puuid
                my_team = self._current_match_info.get_player_team(my_puuid) if my_puuid else None
                
                for player in self._current_match_info.players:
                    is_ally = player.team_id == my_team if my_team else False
                    
                    stats = PlayerMatchStats(
                        id=f"{match_id}_{player.puuid}",
                        match_id=match_id,
                        puuid=player.puuid,
                        player_name=player.player_name or "Unknown",
                        tag_line=player.tag_line or "",
                        agent_id=player.agent_id,
                        agent_name=self._get_agent_name(player.agent_id),
                        team_id=player.team_id,
                        is_ally=is_ally,
                    )
                    self.session.add(stats)
                    players_saved += 1
            
            # Method 3: From cached API data (coach mode, during game)
            elif self._cached_players_data:
                logger.info("Saving player stats from cached data (no K/D/A)")
                for player_data in self._cached_players_data:
                    puuid = player_data.get("Subject", "")
                    team_id = player_data.get("TeamID", "")
                    agent_id = player_data.get("CharacterID", "")
                    
                    stats = PlayerMatchStats(
                        id=f"{match_id}_{puuid}",
                        match_id=match_id,
                        puuid=puuid,
                        player_name="Unknown",  # Will be resolved later
                        tag_line="",
                        agent_id=agent_id,
                        agent_name=self._get_agent_name(agent_id),
                        team_id=team_id,
                        is_ally=False,  # Coach view - not on either team
                    )
                    self.session.add(stats)
                    players_saved += 1
            
            if players_saved > 0:
                logger.info(f"Saved {players_saved} player stats")
            
            # Save round results from match_details
            rounds_saved = 0
            if match_details and match_details.get("roundResults"):
                logger.info("Saving round results from match details API")
                my_puuid = self.client.puuid
                
                # Find my team
                my_team = None
                for player in match_details.get("players", []):
                    if player.get("subject") == my_puuid:
                        my_team = player.get("teamId")
                        break
                
                for round_data in match_details["roundResults"]:
                    round_num = round_data.get("roundNum", 0)
                    winning_team = round_data.get("winningTeam", "")
                    round_result_str = round_data.get("roundResult", "")
                    
                    # Determine if we won this round
                    result = "WIN" if winning_team == my_team else "LOSS" if my_team else "UNKNOWN"
                    
                    # Map API win condition to enum
                    win_condition = self._map_win_condition(round_result_str)
                    
                    round_record = Round(
                        match_id=match_id,
                        round_number=round_num,
                        result=result,
                        win_condition=win_condition,
                    )
                    self.session.add(round_record)
                    rounds_saved += 1
                
                if rounds_saved > 0:
                    logger.info(f"Saved {rounds_saved} rounds")
            
            self.session.commit()
            logger.info(f"Match saved to DB: {match_id} | {map_name} | {ally_score}-{enemy_score}")
            
            return match
            
        except Exception as e:
            logger.error(f"Failed to save match: {e}")
            self.session.rollback()
            return None
    
    def _get_map_name(self, map_id: str) -> str:
        """Get map name from ID."""
        # Map internal names to display names
        map_id_lower = map_id.lower()
        
        maps = {
            "ascent": "Ascent",
            "duality": "Bind",
            "bind": "Bind",
            "triad": "Haven",
            "haven": "Haven",
            "bonsai": "Split",
            "split": "Split",
            "port": "Icebox",
            "icebox": "Icebox",
            "foxtrot": "Breeze",
            "breeze": "Breeze",
            "canyon": "Fracture",
            "fracture": "Fracture",
            "pitt": "Pearl",
            "pearl": "Pearl",
            "jam": "Lotus",
            "lotus": "Lotus",
            "juliett": "Sunset",
            "sunset": "Sunset",
            "infinity": "Abyss",
            "abyss": "Abyss",
            "kilo": "Corrode",
            "corrode": "Corrode",
        }
        
        for key, name in maps.items():
            if key in map_id_lower:
                return name
        return "Unknown"
    
    def _get_agent_name(self, agent_id: str) -> str:
        """Get agent name from ID."""
        # Simple mapping - could be expanded with full UUID mapping
        return "Unknown"
    
    def _map_win_condition(self, api_result: str) -> Optional[str]:
        """Map API round result to WinCondition enum value."""
        from ..db.models import WinCondition
        
        mapping = {
            "Eliminated": WinCondition.ELIMINATION,
            "Bomb detonated": WinCondition.DETONATE,
            "Bomb defused": WinCondition.DEFUSE,
            "Round timer expired": WinCondition.TIME,
            # Alternative formats
            "eliminated": WinCondition.ELIMINATION,
            "detonated": WinCondition.DETONATE,
            "defused": WinCondition.DEFUSE,
            "time": WinCondition.TIME,
        }
        return mapping.get(api_result)
    
    def _calculate_detailed_stats(self, match_details: dict) -> dict:
        """
        Calculate detailed stats from match details.
        
        Includes:
        - FK (First Kills)
        - FD (First Deaths)
        - True FK (FK + round win)
        - Headshots/Bodyshots/Legshots
        - Time-based K/D
        
        Args:
            match_details: Raw match details from API
            
        Returns:
            Dict of puuid -> detailed stats
        """
        players = match_details.get("players", [])
        rounds = match_details.get("roundResults", [])
        
        # Build player team map
        player_teams = {p.get("subject"): p.get("teamId") for p in players}
        
        # Initialize stats for each player
        stats = defaultdict(lambda: {
            "first_kills": 0,
            "first_deaths": 0,
            "true_first_kills": 0,
            "headshots": 0,
            "bodyshots": 0,
            "legshots": 0,
            "time_based_kd": {
                "1st": {"k": 0, "d": 0},     # 0-20s
                "1.5th": {"k": 0, "d": 0},   # 20-40s
                "2nd": {"k": 0, "d": 0},     # 40-60s
                "Late": {"k": 0, "d": 0},    # 60s+
                "PP": {"k": 0, "d": 0},      # Post-plant
            },
        })
        
        for r in rounds:
            winning_team = r.get("winningTeam", "")
            plant_time = r.get("plantRoundTime")  # None if no plant
            
            # Find first kill in this round
            first_kill_time = float('inf')
            first_killer = None
            first_victim = None
            
            # Process all player stats in round
            for ps in r.get("playerStats", []):
                puuid = ps.get("subject", "")
                
                # Collect headshot stats from damage data
                for dmg in ps.get("damage", []):
                    stats[puuid]["headshots"] += dmg.get("headshots", 0)
                    stats[puuid]["bodyshots"] += dmg.get("bodyshots", 0)
                    stats[puuid]["legshots"] += dmg.get("legshots", 0)
                
                # Process kills for FK and time-based stats
                for kill in ps.get("kills", []):
                    round_time = kill.get("roundTime", 0)
                    killer = kill.get("killer", "")
                    victim = kill.get("victim", "")
                    
                    # Track first kill
                    if round_time < first_kill_time:
                        first_kill_time = round_time
                        first_killer = killer
                        first_victim = victim
                    
                    # Time-based K/D
                    zone = self._get_time_zone(round_time, plant_time)
                    if killer in stats:
                        stats[killer]["time_based_kd"][zone]["k"] += 1
                    if victim in stats:
                        stats[victim]["time_based_kd"][zone]["d"] += 1
            
            # Record FK and FD
            if first_killer and first_victim:
                stats[first_killer]["first_kills"] += 1
                stats[first_victim]["first_deaths"] += 1
                
                # Check if True FK (killer's team won)
                killer_team = player_teams.get(first_killer, "")
                if killer_team == winning_team:
                    stats[first_killer]["true_first_kills"] += 1
        
        return dict(stats)
    
    def _get_time_zone(self, round_time_ms: int, plant_time_ms: Optional[int]) -> str:
        """
        Get time zone for a kill based on round time.
        
        Time zones (from round start):
        - 1st:   0-20s  (1:40-1:20 remaining)
        - 1.5th: 20-40s (1:20-1:00 remaining)
        - 2nd:   40-60s (1:00-0:40 remaining)
        - Late:  60s+   (0:40-0:00 remaining)
        - PP:    After plant
        """
        # Check post-plant first
        if plant_time_ms and round_time_ms > plant_time_ms:
            return "PP"
        
        t = round_time_ms / 1000  # Convert to seconds
        
        if t <= 20:
            return "1st"
        elif t <= 40:
            return "1.5th"
        elif t <= 60:
            return "2nd"
        else:
            return "Late"
    
    # ============================================
    # Export
    # ============================================
    
    def export_timeline_json(self, output_path: Path) -> None:
        """
        Export current timeline to JSON.
        
        Args:
            output_path: Path for output file
        """
        import json
        
        data = self.timeline.to_dict()
        output_path.write_text(json.dumps(data, indent=2, default=str))
        logger.info(f"Timeline exported: {output_path}")

