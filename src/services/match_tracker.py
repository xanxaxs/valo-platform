"""
Match Tracker Service.

Orchestrates match tracking with synchronized audio recording.
"""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from sqlalchemy.orm import Session

from ..api.client import GameState, MatchInfo, ValorantClient
from ..api.websocket import ValorantWebSocket
from ..db.models import Match, MatchCategory, MatchResult, PlayerMatchStats, Round
from ..sync.sync_recorder import SyncRecorder
from ..sync.timeline import EventType, TimelineSync

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
        
        # Components
        self.recorder = SyncRecorder(
            output_dir=recordings_dir,
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
        
        # Callbacks
        self._on_match_start: Optional[Callable] = None
        self._on_match_end: Optional[Callable] = None
        self._on_round_start: Optional[Callable] = None
        self._on_round_end: Optional[Callable] = None
    
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
        
        # Stop any active recording
        if self.recorder.is_recording:
            self.recorder.stop_recording()
        
        logger.info("Match tracker stopped")
    
    async def _poll_game_state(self) -> None:
        """Poll game state and detect changes."""
        while self._is_tracking:
            try:
                current_state = await self.client.get_game_state()
                
                if current_state != self._last_game_state:
                    await self._handle_state_change(self._last_game_state, current_state)
                    self._last_game_state = current_state
                
                await asyncio.sleep(2.0)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Poll error: {e}")
                await asyncio.sleep(5.0)
    
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
        if not match_id:
            logger.error("Could not get match ID")
            return
        
        self._current_match_id = match_id
        self._current_match_info = await self.client.get_current_match_info()
        
        logger.info(f"Match started: {match_id}")
        
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
        
        match_id = self._current_match_id
        logger.info(f"Match ended: {match_id}")
        
        # Wait a bit for final data
        await asyncio.sleep(3.0)
        
        # Stop recording
        audio_path = self.recorder.stop_recording()
        if audio_path:
            logger.info(f"Audio saved: {audio_path}")
        
        # Mark timeline
        self.timeline.mark_match_end(
            result="UNKNOWN",  # Will be updated from API
            ally_score=0,
            enemy_score=0,
        )
        
        # Save match to database
        await self._save_match(match_id)
        
        # Callback
        if self._on_match_end:
            try:
                if asyncio.iscoroutinefunction(self._on_match_end):
                    await self._on_match_end(match_id)
                else:
                    self._on_match_end(match_id)
            except Exception as e:
                logger.error(f"Match end callback error: {e}")
        
        # Reset state
        self._current_match_id = None
        self._current_match_info = None
    
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
    # Database Operations
    # ============================================
    
    async def _save_match(self, match_id: str) -> Optional[Match]:
        """
        Save match data to database.
        
        Args:
            match_id: Match ID to save
            
        Returns:
            Saved Match object or None
        """
        if not self._current_match_info:
            logger.warning("No match info to save")
            return None
        
        try:
            # Create match record
            match = Match(
                match_id=match_id,
                map_id=self._current_match_info.map_id,
                map_name=self._get_map_name(self._current_match_info.map_id),
                queue_id="custom",
                game_start_millis=int(datetime.now().timestamp() * 1000),
                game_length_millis=0,  # Will be calculated
                result=MatchResult.WIN,  # Placeholder
                ally_score=0,
                enemy_score=0,
                completion_state="Completed",
                category=MatchCategory.CUSTOM,
            )
            
            self.session.add(match)
            
            # Save player stats
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
            
            self.session.commit()
            logger.info(f"Match saved: {match_id}")
            
            return match
            
        except Exception as e:
            logger.error(f"Failed to save match: {e}")
            self.session.rollback()
            return None
    
    def _get_map_name(self, map_id: str) -> str:
        """Get map name from ID."""
        # Simple mapping - could be expanded
        maps = {
            "Ascent": "Ascent",
            "Bind": "Bind",
            "Haven": "Haven",
            "Split": "Split",
            "Icebox": "Icebox",
            "Breeze": "Breeze",
            "Fracture": "Fracture",
            "Pearl": "Pearl",
            "Lotus": "Lotus",
            "Sunset": "Sunset",
            "Abyss": "Abyss",
        }
        for name in maps:
            if name.lower() in map_id.lower():
                return name
        return "Unknown"
    
    def _get_agent_name(self, agent_id: str) -> str:
        """Get agent name from ID."""
        # Simple mapping - could be expanded with full UUID mapping
        return "Unknown"
    
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

