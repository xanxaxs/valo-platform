"""
Timeline Synchronization for Match Events and Audio.

Extended from comms_tracker's timeline.py to support:
- Match-level timeline (not just round-level)
- Audio segment management
- Event-audio linking
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Optional


class EventType(str, Enum):
    """Types of events that can be tracked on the timeline."""
    
    MATCH_START = "match_start"
    MATCH_END = "match_end"
    ROUND_START = "round_start"
    ROUND_END = "round_end"
    KILL = "kill"
    DEATH = "death"
    PLANT = "plant"
    DEFUSE = "defuse"
    SPEECH = "speech"
    VISION = "vision"


@dataclass
class TimelineEvent:
    """A single event on the timeline."""
    
    event_type: EventType
    offset: float  # Seconds from match start
    timestamp: datetime
    data: dict = field(default_factory=dict)
    
    # For audio-linked events
    audio_segment_id: Optional[int] = None
    audio_start: Optional[float] = None
    audio_end: Optional[float] = None


@dataclass
class AudioSegmentInfo:
    """Information about a recorded audio segment."""
    
    segment_id: int
    file_path: Path
    start_offset: float  # Seconds from match start
    end_offset: float
    duration: float
    round_number: Optional[int] = None


class TimelineSync:
    """
    Synchronizes match events with audio recordings.
    
    Manages a unified timeline for all events in a match,
    with bidirectional linking between events and audio.
    """
    
    def __init__(self, match_start_time: Optional[datetime] = None):
        """
        Initialize timeline synchronizer.
        
        Args:
            match_start_time: Absolute time of match start
        """
        self.match_start_time = match_start_time or datetime.now()
        self._events: list[TimelineEvent] = []
        self._audio_segments: list[AudioSegmentInfo] = []
        self._current_round: int = 0
        self._is_recording: bool = False
        
    @property
    def match_id(self) -> Optional[str]:
        """Get current match ID from events."""
        for event in self._events:
            if event.event_type == EventType.MATCH_START:
                return event.data.get("match_id")
        return None
    
    # ============================================
    # Event Management
    # ============================================
    
    def add_event(
        self,
        event_type: EventType,
        data: Optional[dict] = None,
        timestamp: Optional[datetime] = None,
    ) -> TimelineEvent:
        """
        Add an event to the timeline.
        
        Args:
            event_type: Type of event
            data: Event-specific data
            timestamp: Event timestamp (defaults to now)
            
        Returns:
            Created TimelineEvent
        """
        ts = timestamp or datetime.now()
        offset = (ts - self.match_start_time).total_seconds()
        
        event = TimelineEvent(
            event_type=event_type,
            offset=max(0, offset),
            timestamp=ts,
            data=data or {},
        )
        
        self._events.append(event)
        return event
    
    def mark_match_start(self, match_id: str) -> TimelineEvent:
        """Mark the start of a match."""
        self.match_start_time = datetime.now()
        self._current_round = 0
        return self.add_event(
            EventType.MATCH_START,
            data={"match_id": match_id},
        )
    
    def mark_match_end(self, result: str, ally_score: int, enemy_score: int) -> TimelineEvent:
        """Mark the end of a match."""
        return self.add_event(
            EventType.MATCH_END,
            data={
                "result": result,
                "ally_score": ally_score,
                "enemy_score": enemy_score,
            },
        )
    
    def mark_round_start(self, round_number: int) -> TimelineEvent:
        """Mark the start of a round."""
        self._current_round = round_number
        return self.add_event(
            EventType.ROUND_START,
            data={"round_number": round_number},
        )
    
    def mark_round_end(
        self,
        round_number: int,
        result: str,
        win_condition: Optional[str] = None,
    ) -> TimelineEvent:
        """Mark the end of a round."""
        return self.add_event(
            EventType.ROUND_END,
            data={
                "round_number": round_number,
                "result": result,
                "win_condition": win_condition,
            },
        )
    
    def add_kill_event(
        self,
        killer_puuid: str,
        victim_puuid: str,
        location_x: int,
        location_y: int,
        weapon_id: Optional[str] = None,
        assistants: Optional[list[str]] = None,
    ) -> TimelineEvent:
        """Add a kill event."""
        return self.add_event(
            EventType.KILL,
            data={
                "round_number": self._current_round,
                "killer_puuid": killer_puuid,
                "victim_puuid": victim_puuid,
                "location_x": location_x,
                "location_y": location_y,
                "weapon_id": weapon_id,
                "assistants": assistants or [],
            },
        )
    
    def add_plant_event(self, planter_puuid: str, site: str) -> TimelineEvent:
        """Add a spike plant event."""
        return self.add_event(
            EventType.PLANT,
            data={
                "round_number": self._current_round,
                "planter_puuid": planter_puuid,
                "site": site,
            },
        )
    
    def add_defuse_event(self, defuser_puuid: str) -> TimelineEvent:
        """Add a spike defuse event."""
        return self.add_event(
            EventType.DEFUSE,
            data={
                "round_number": self._current_round,
                "defuser_puuid": defuser_puuid,
            },
        )
    
    def add_speech_event(
        self,
        speaker_id: str,
        content: str,
        sentiment: str = "neutral",
        is_useful: bool = True,
    ) -> TimelineEvent:
        """Add a speech/voice event."""
        return self.add_event(
            EventType.SPEECH,
            data={
                "round_number": self._current_round,
                "speaker_id": speaker_id,
                "content": content,
                "sentiment": sentiment,
                "is_useful": is_useful,
            },
        )
    
    # ============================================
    # Audio Segment Management
    # ============================================
    
    def add_audio_segment(
        self,
        segment_id: int,
        file_path: Path,
        start_offset: float,
        end_offset: float,
        round_number: Optional[int] = None,
    ) -> AudioSegmentInfo:
        """
        Register an audio segment.
        
        Args:
            segment_id: Database ID of the segment
            file_path: Path to the audio file
            start_offset: Start time relative to match start (seconds)
            end_offset: End time relative to match start (seconds)
            round_number: Optional round number this segment belongs to
            
        Returns:
            Created AudioSegmentInfo
        """
        segment = AudioSegmentInfo(
            segment_id=segment_id,
            file_path=file_path,
            start_offset=start_offset,
            end_offset=end_offset,
            duration=end_offset - start_offset,
            round_number=round_number,
        )
        self._audio_segments.append(segment)
        return segment
    
    def find_audio_for_event(
        self,
        event: TimelineEvent,
        context_before: float = 3.0,
        context_after: float = 2.0,
    ) -> Optional[tuple[AudioSegmentInfo, float, float]]:
        """
        Find the audio segment containing an event.
        
        Args:
            event: The event to find audio for
            context_before: Seconds before the event to include
            context_after: Seconds after the event to include
            
        Returns:
            Tuple of (segment, audio_start, audio_end) or None
        """
        event_time = event.offset
        window_start = event_time - context_before
        window_end = event_time + context_after
        
        for segment in self._audio_segments:
            # Check if the event falls within this segment
            if segment.start_offset <= event_time <= segment.end_offset:
                # Calculate position within the audio file
                audio_start = max(0, window_start - segment.start_offset)
                audio_end = min(segment.duration, window_end - segment.start_offset)
                return (segment, audio_start, audio_end)
        
        return None
    
    def find_events_in_audio(
        self,
        segment: AudioSegmentInfo,
        event_types: Optional[list[EventType]] = None,
    ) -> list[TimelineEvent]:
        """
        Find all events that occur within an audio segment.
        
        Args:
            segment: The audio segment
            event_types: Optional filter for event types
            
        Returns:
            List of events within the segment's time range
        """
        events = []
        for event in self._events:
            if segment.start_offset <= event.offset <= segment.end_offset:
                if event_types is None or event.event_type in event_types:
                    events.append(event)
        return events
    
    # ============================================
    # Query Methods
    # ============================================
    
    def get_events(
        self,
        event_types: Optional[list[EventType]] = None,
        round_number: Optional[int] = None,
        start_offset: Optional[float] = None,
        end_offset: Optional[float] = None,
    ) -> list[TimelineEvent]:
        """
        Get events with optional filters.
        
        Args:
            event_types: Filter by event types
            round_number: Filter by round
            start_offset: Filter by minimum offset
            end_offset: Filter by maximum offset
            
        Returns:
            Filtered list of events
        """
        events = self._events
        
        if event_types:
            events = [e for e in events if e.event_type in event_types]
        
        if round_number is not None:
            events = [
                e for e in events
                if e.data.get("round_number") == round_number
            ]
        
        if start_offset is not None:
            events = [e for e in events if e.offset >= start_offset]
        
        if end_offset is not None:
            events = [e for e in events if e.offset <= end_offset]
        
        return sorted(events, key=lambda e: e.offset)
    
    def get_round_events(self, round_number: int) -> list[TimelineEvent]:
        """Get all events for a specific round."""
        # Find round boundaries
        round_start = None
        round_end = None
        
        for event in self._events:
            if (event.event_type == EventType.ROUND_START and 
                event.data.get("round_number") == round_number):
                round_start = event.offset
            elif (event.event_type == EventType.ROUND_END and 
                  event.data.get("round_number") == round_number):
                round_end = event.offset
        
        if round_start is None:
            return []
        
        return self.get_events(
            start_offset=round_start,
            end_offset=round_end,
        )
    
    def get_speech_around_event(
        self,
        event: TimelineEvent,
        window_before: float = 3.0,
        window_after: float = 2.0,
    ) -> list[TimelineEvent]:
        """
        Get speech events around a specific event.
        
        Args:
            event: The reference event
            window_before: Seconds before to search
            window_after: Seconds after to search
            
        Returns:
            List of speech events within the window
        """
        return self.get_events(
            event_types=[EventType.SPEECH],
            start_offset=event.offset - window_before,
            end_offset=event.offset + window_after,
        )
    
    def get_kills_with_callouts(
        self,
        pre_window: float = 1.0,
        post_window: float = 2.0,
    ) -> list[dict]:
        """
        Correlate kill events with voice callouts.
        
        Args:
            pre_window: Seconds before kill to search for callouts
            post_window: Seconds after kill to search for callouts
            
        Returns:
            List of dictionaries with kill events and associated callouts
        """
        kills = self.get_events(event_types=[EventType.KILL])
        correlations = []
        
        for kill in kills:
            pre_callouts = self.get_events(
                event_types=[EventType.SPEECH],
                start_offset=kill.offset - pre_window,
                end_offset=kill.offset,
            )
            post_callouts = self.get_events(
                event_types=[EventType.SPEECH],
                start_offset=kill.offset,
                end_offset=kill.offset + post_window,
            )
            
            correlations.append({
                "kill": kill,
                "pre_callouts": pre_callouts,
                "post_callouts": post_callouts,
                "had_callout_before": len(pre_callouts) > 0,
            })
        
        return correlations
    
    # ============================================
    # Serialization
    # ============================================
    
    def to_dict(self) -> dict:
        """Export timeline to dictionary."""
        return {
            "match_start_time": self.match_start_time.isoformat(),
            "current_round": self._current_round,
            "events": [
                {
                    "event_type": e.event_type.value,
                    "offset": e.offset,
                    "timestamp": e.timestamp.isoformat(),
                    "data": e.data,
                }
                for e in self._events
            ],
            "audio_segments": [
                {
                    "segment_id": s.segment_id,
                    "file_path": str(s.file_path),
                    "start_offset": s.start_offset,
                    "end_offset": s.end_offset,
                    "duration": s.duration,
                    "round_number": s.round_number,
                }
                for s in self._audio_segments
            ],
        }
    
    def reset(self, new_start_time: Optional[datetime] = None) -> None:
        """Reset timeline for a new match."""
        self.match_start_time = new_start_time or datetime.now()
        self._events.clear()
        self._audio_segments.clear()
        self._current_round = 0
        self._is_recording = False

