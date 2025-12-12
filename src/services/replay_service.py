"""
2D Replay Service.

Records and retrieves match event snapshots for 2D replay visualization.
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from ..db.models import AudioSegment, Match, MatchEventSnapshot, EventType

logger = logging.getLogger(__name__)


# ============================================
# Map Coordinate Conversion
# ============================================

# Map bounds for coordinate conversion (game units to normalized 0-1)
# These are approximate and may need calibration per map
MAP_BOUNDS = {
    "Ascent": {"x_min": -6000, "x_max": 8000, "y_min": -6000, "y_max": 8000},
    "Bind": {"x_min": -5000, "x_max": 7500, "y_min": -5000, "y_max": 7000},
    "Haven": {"x_min": -6500, "x_max": 7500, "y_min": -5000, "y_max": 9000},
    "Split": {"x_min": -6000, "x_max": 7000, "y_min": -5500, "y_max": 7500},
    "Icebox": {"x_min": -5000, "x_max": 7000, "y_min": -5000, "y_max": 7000},
    "Breeze": {"x_min": -7000, "x_max": 9000, "y_min": -6000, "y_max": 9000},
    "Fracture": {"x_min": -7000, "x_max": 7000, "y_min": -7000, "y_max": 7000},
    "Pearl": {"x_min": -6000, "x_max": 8000, "y_min": -5000, "y_max": 8000},
    "Lotus": {"x_min": -7000, "x_max": 8000, "y_min": -6000, "y_max": 8000},
    "Sunset": {"x_min": -6000, "x_max": 8000, "y_min": -5000, "y_max": 8000},
    "Abyss": {"x_min": -6000, "x_max": 8000, "y_min": -5000, "y_max": 8000},
    "Corrode": {"x_min": -6000, "x_max": 8000, "y_min": -5000, "y_max": 8000},
}

DEFAULT_BOUNDS = {"x_min": -6000, "x_max": 8000, "y_min": -6000, "y_max": 8000}


def normalize_position(x: float, y: float, map_name: str) -> tuple[float, float]:
    """
    Convert game coordinates to normalized 0-1 range for display.
    
    Args:
        x: Game X coordinate
        y: Game Y coordinate
        map_name: Map name for bounds lookup
        
    Returns:
        Tuple of (normalized_x, normalized_y) in 0-1 range
    """
    bounds = MAP_BOUNDS.get(map_name, DEFAULT_BOUNDS)
    
    norm_x = (x - bounds["x_min"]) / (bounds["x_max"] - bounds["x_min"])
    norm_y = (y - bounds["y_min"]) / (bounds["y_max"] - bounds["y_min"])
    
    # Clamp to 0-1
    norm_x = max(0, min(1, norm_x))
    norm_y = max(0, min(1, norm_y))
    
    return norm_x, norm_y


# ============================================
# Data Classes
# ============================================

@dataclass
class PlayerPosition:
    """Player position at a point in time."""
    puuid: str
    player_name: str
    team_id: str
    agent_id: str
    x: float
    y: float
    is_alive: bool
    
    def to_dict(self) -> dict:
        return {
            "puuid": self.puuid,
            "player_name": self.player_name,
            "team_id": self.team_id,
            "agent_id": self.agent_id,
            "x": self.x,
            "y": self.y,
            "is_alive": self.is_alive,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "PlayerPosition":
        return cls(**data)


@dataclass
class ReplayEvent:
    """A single event in the replay timeline."""
    id: int
    round_number: int
    event_type: str
    game_time: int  # ms from match start
    round_time: int  # ms from round start
    event_data: Optional[dict]
    player_positions: list[PlayerPosition]
    
    @property
    def round_time_seconds(self) -> float:
        return self.round_time / 1000
    
    @property
    def round_time_display(self) -> str:
        """Format as MM:SS"""
        total_seconds = int(self.round_time / 1000)
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes}:{seconds:02d}"


# ============================================
# Replay Service
# ============================================

class ReplayService:
    """
    Service for 2D replay functionality.
    
    Handles:
    - Saving event snapshots from match details
    - Retrieving replay data for visualization
    - Syncing with audio segments
    """
    
    def __init__(self, session: Session):
        """
        Initialize replay service.
        
        Args:
            session: Database session
        """
        self.session = session
    
    # ============================================
    # Save Snapshots
    # ============================================
    
    def save_match_snapshots(self, match_id: str, match_details: dict) -> int:
        """
        Extract and save event snapshots from match details.
        
        Args:
            match_id: Match ID
            match_details: Raw match details from API
            
        Returns:
            Number of snapshots saved
        """
        try:
            # Delete existing snapshots for this match
            self.session.query(MatchEventSnapshot).filter(
                MatchEventSnapshot.match_id == match_id
            ).delete()
            
            snapshots_saved = 0
            rounds = match_details.get("roundResults", [])
            players = match_details.get("players", [])
            
            # Build player info map
            player_info = {
                p.get("subject"): {
                    "player_name": p.get("gameName", "Unknown"),
                    "team_id": p.get("teamId", ""),
                    "agent_id": p.get("characterId", ""),
                }
                for p in players
            }
            
            game_time_offset = 0  # Cumulative game time
            
            for round_data in rounds:
                round_num = round_data.get("roundNum", 0)
                round_duration = round_data.get("roundResultCode", 0)
                
                # Track alive status
                alive_status = {puuid: True for puuid in player_info}
                
                # Round start event
                round_start = MatchEventSnapshot(
                    match_id=match_id,
                    round_number=round_num,
                    event_type=EventType.ROUND_START,
                    game_time=game_time_offset,
                    round_time=0,
                    event_data=None,
                    player_positions=self._build_positions_json(player_info, alive_status),
                )
                self.session.add(round_start)
                snapshots_saved += 1
                
                # Collect all kills with timing
                all_kills = []
                for stat in round_data.get("playerStats", []):
                    killer_puuid = stat.get("subject", "")
                    for kill in stat.get("kills", []):
                        all_kills.append({
                            "killer": killer_puuid,
                            "victim": kill.get("victim", ""),
                            "round_time": kill.get("roundTime", 0),
                            "finishing_damage": kill.get("finishingDamage", {}),
                            "player_locations": kill.get("playerLocations", []),
                        })
                
                # Sort by time
                all_kills.sort(key=lambda k: k["round_time"])
                
                # Process each kill
                for kill in all_kills:
                    victim = kill["victim"]
                    if victim in alive_status:
                        alive_status[victim] = False
                    
                    # Build positions from kill data
                    positions = self._build_positions_from_kill(
                        kill["player_locations"],
                        player_info,
                        alive_status,
                    )
                    
                    kill_event = MatchEventSnapshot(
                        match_id=match_id,
                        round_number=round_num,
                        event_type=EventType.KILL,
                        game_time=game_time_offset + kill["round_time"],
                        round_time=kill["round_time"],
                        event_data=json.dumps({
                            "killer": kill["killer"],
                            "victim": kill["victim"],
                            "weapon": kill["finishing_damage"].get("damageType", "Unknown"),
                            "headshot": kill["finishing_damage"].get("isSecondaryFireMode", False),
                        }),
                        player_positions=json.dumps(positions),
                    )
                    self.session.add(kill_event)
                    snapshots_saved += 1
                
                # Plant event
                plant_time = round_data.get("plantRoundTime")
                if plant_time:
                    plant_site = round_data.get("plantSite", "")
                    plant_event = MatchEventSnapshot(
                        match_id=match_id,
                        round_number=round_num,
                        event_type=EventType.PLANT,
                        game_time=game_time_offset + plant_time,
                        round_time=plant_time,
                        event_data=json.dumps({"site": plant_site}),
                        player_positions=self._build_positions_json(player_info, alive_status),
                    )
                    self.session.add(plant_event)
                    snapshots_saved += 1
                
                # Defuse event
                defuse_time = round_data.get("defuseRoundTime")
                if defuse_time:
                    defuse_event = MatchEventSnapshot(
                        match_id=match_id,
                        round_number=round_num,
                        event_type=EventType.DEFUSE,
                        game_time=game_time_offset + defuse_time,
                        round_time=defuse_time,
                        event_data=None,
                        player_positions=self._build_positions_json(player_info, alive_status),
                    )
                    self.session.add(defuse_event)
                    snapshots_saved += 1
                
                # Round end event
                round_end = MatchEventSnapshot(
                    match_id=match_id,
                    round_number=round_num,
                    event_type=EventType.ROUND_END,
                    game_time=game_time_offset + 100000,  # Approximate
                    round_time=100000,
                    event_data=json.dumps({
                        "winning_team": round_data.get("winningTeam", ""),
                        "round_result": round_data.get("roundResult", ""),
                    }),
                    player_positions=self._build_positions_json(player_info, alive_status),
                )
                self.session.add(round_end)
                snapshots_saved += 1
                
                # Add round duration to game time
                game_time_offset += 120000  # ~2 min per round average
            
            self.session.commit()
            logger.info(f"Saved {snapshots_saved} event snapshots for match {match_id}")
            return snapshots_saved
            
        except Exception as e:
            logger.error(f"Failed to save snapshots: {e}")
            self.session.rollback()
            return 0
    
    def _build_positions_json(self, player_info: dict, alive_status: dict) -> str:
        """Build positions JSON with alive status."""
        positions = []
        for puuid, info in player_info.items():
            positions.append({
                "puuid": puuid,
                "player_name": info["player_name"],
                "team_id": info["team_id"],
                "agent_id": info["agent_id"],
                "x": 0,
                "y": 0,
                "is_alive": alive_status.get(puuid, True),
            })
        return json.dumps(positions)
    
    def _build_positions_from_kill(
        self,
        player_locations: list,
        player_info: dict,
        alive_status: dict,
    ) -> list:
        """Build positions list from kill event locations."""
        positions = []
        
        # Map locations by puuid
        location_map = {
            loc.get("subject"): loc.get("location", {})
            for loc in player_locations
        }
        
        for puuid, info in player_info.items():
            loc = location_map.get(puuid, {})
            positions.append({
                "puuid": puuid,
                "player_name": info["player_name"],
                "team_id": info["team_id"],
                "agent_id": info["agent_id"],
                "x": loc.get("x", 0),
                "y": loc.get("y", 0),
                "is_alive": alive_status.get(puuid, True),
            })
        
        return positions
    
    # ============================================
    # Retrieve Replay Data
    # ============================================
    
    def get_match_events(self, match_id: str) -> list[ReplayEvent]:
        """
        Get all events for a match.
        
        Args:
            match_id: Match ID
            
        Returns:
            List of ReplayEvent objects
        """
        snapshots = self.session.query(MatchEventSnapshot).filter(
            MatchEventSnapshot.match_id == match_id
        ).order_by(
            MatchEventSnapshot.round_number,
            MatchEventSnapshot.round_time,
        ).all()
        
        events = []
        for snap in snapshots:
            positions = []
            try:
                pos_data = json.loads(snap.player_positions) if snap.player_positions else []
                positions = [PlayerPosition.from_dict(p) for p in pos_data]
            except:
                pass
            
            event_data = None
            try:
                event_data = json.loads(snap.event_data) if snap.event_data else None
            except:
                pass
            
            events.append(ReplayEvent(
                id=snap.id,
                round_number=snap.round_number,
                event_type=snap.event_type.value if snap.event_type else "unknown",
                game_time=snap.game_time,
                round_time=snap.round_time,
                event_data=event_data,
                player_positions=positions,
            ))
        
        return events
    
    def get_round_events(self, match_id: str, round_number: int) -> list[ReplayEvent]:
        """
        Get events for a specific round.
        
        Args:
            match_id: Match ID
            round_number: Round number
            
        Returns:
            List of ReplayEvent objects for the round
        """
        all_events = self.get_match_events(match_id)
        return [e for e in all_events if e.round_number == round_number]
    
    def get_kill_events(self, match_id: str) -> list[ReplayEvent]:
        """
        Get only kill events for a match.
        
        Args:
            match_id: Match ID
            
        Returns:
            List of kill ReplayEvent objects
        """
        all_events = self.get_match_events(match_id)
        return [e for e in all_events if e.event_type == "kill"]
    
    # ============================================
    # Audio Sync
    # ============================================
    
    def get_audio_for_event(self, match_id: str, round_time_ms: int) -> Optional[tuple[str, float]]:
        """
        Get audio file and timestamp for a specific event.
        
        Args:
            match_id: Match ID
            round_time_ms: Time in round (milliseconds)
            
        Returns:
            Tuple of (audio_file_path, start_time_seconds) or None
        """
        # Get full match audio
        segment = self.session.query(AudioSegment).filter(
            AudioSegment.match_id == match_id,
            AudioSegment.round_number.is_(None),  # Full match recording
        ).first()
        
        if segment and Path(segment.file_path).exists():
            # Calculate offset in audio file
            # This is approximate - actual sync would need match start timestamp
            audio_offset = round_time_ms / 1000
            return segment.file_path, audio_offset
        
        return None
    
    def get_round_audio(self, match_id: str, round_number: int) -> Optional[str]:
        """
        Get audio file for a specific round.
        
        Args:
            match_id: Match ID
            round_number: Round number
            
        Returns:
            Audio file path or None
        """
        segment = self.session.query(AudioSegment).filter(
            AudioSegment.match_id == match_id,
            AudioSegment.round_number == round_number,
        ).first()
        
        if segment and Path(segment.file_path).exists():
            return segment.file_path
        
        return None
    
    # ============================================
    # Timeline Generation
    # ============================================
    
    def generate_timeline(self, match_id: str) -> list[dict]:
        """
        Generate a timeline of significant events.
        
        Args:
            match_id: Match ID
            
        Returns:
            List of timeline entries
        """
        events = self.get_match_events(match_id)
        timeline = []
        
        for event in events:
            if event.event_type == "kill":
                data = event.event_data or {}
                timeline.append({
                    "round": event.round_number,
                    "time": event.round_time_display,
                    "type": "kill",
                    "description": f"{data.get('killer', '?')[:8]} → {data.get('victim', '?')[:8]}",
                    "weapon": data.get("weapon", "Unknown"),
                    "event_id": event.id,
                })
            elif event.event_type == "plant":
                data = event.event_data or {}
                timeline.append({
                    "round": event.round_number,
                    "time": event.round_time_display,
                    "type": "plant",
                    "description": f"Spike planted at {data.get('site', '?')}",
                    "event_id": event.id,
                })
            elif event.event_type == "defuse":
                timeline.append({
                    "round": event.round_number,
                    "time": event.round_time_display,
                    "type": "defuse",
                    "description": "Spike defused",
                    "event_id": event.id,
                })
        
        return timeline

