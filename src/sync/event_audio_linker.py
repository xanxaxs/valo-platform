"""
Event-Audio Linker.

Creates and manages links between game events and audio segments
for quick lookup and playback.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from ..db.models import AudioSegment, EventAudioLink, EventType, Kill, Round


@dataclass
class AudioClip:
    """A clip of audio associated with an event."""
    
    file_path: Path
    start_seconds: float
    end_seconds: float
    event_type: str
    event_id: int
    context_description: str


class EventAudioLinker:
    """
    Links game events to audio segments for quick retrieval.
    
    Provides methods to:
    - Create links between events and audio
    - Query audio for specific events
    - Generate clips for events with context
    """
    
    def __init__(self, session: Session):
        """
        Initialize linker with database session.
        
        Args:
            session: SQLAlchemy session
        """
        self.session = session
        self.default_context_before = 3.0  # seconds
        self.default_context_after = 2.0  # seconds
    
    def link_event_to_audio(
        self,
        event_type: EventType,
        event_id: int,
        segment_id: int,
        event_offset: float,  # Offset from match start
        segment_start_offset: float,  # Segment start offset from match start
        context_before: Optional[float] = None,
        context_after: Optional[float] = None,
    ) -> EventAudioLink:
        """
        Create a link between an event and an audio segment.
        
        Args:
            event_type: Type of game event
            event_id: ID of the event record
            segment_id: ID of the audio segment
            event_offset: When the event occurred (from match start)
            segment_start_offset: When the segment started (from match start)
            context_before: Seconds of audio before the event
            context_after: Seconds of audio after the event
            
        Returns:
            Created EventAudioLink
        """
        ctx_before = context_before or self.default_context_before
        ctx_after = context_after or self.default_context_after
        
        # Calculate position within the audio file
        event_in_segment = event_offset - segment_start_offset
        audio_start = max(0, event_in_segment - ctx_before)
        audio_end = event_in_segment + ctx_after
        
        link = EventAudioLink(
            event_type=event_type,
            event_id=event_id,
            segment_id=segment_id,
            audio_start=audio_start,
            audio_end=audio_end,
            context_before=ctx_before,
            context_after=ctx_after,
        )
        
        self.session.add(link)
        self.session.commit()
        
        return link
    
    def link_kill_to_audio(
        self,
        kill: Kill,
        audio_segment: AudioSegment,
        context_before: Optional[float] = None,
        context_after: Optional[float] = None,
    ) -> Optional[EventAudioLink]:
        """
        Link a kill event to the appropriate audio segment.
        
        Args:
            kill: Kill record
            audio_segment: Audio segment containing the kill
            context_before: Seconds before the kill
            context_after: Seconds after the kill
            
        Returns:
            Created link or None if kill is outside segment
        """
        # Convert kill game_time (ms from round start) to match offset
        # This requires knowing the round start offset
        round_obj = self.session.query(Round).filter(
            Round.id == kill.round_id
        ).first()
        
        if not round_obj or round_obj.start_offset is None:
            return None
        
        # Kill offset from match start
        kill_offset = round_obj.start_offset + (kill.game_time / 1000)
        
        # Check if kill is within the audio segment
        if not (audio_segment.start_offset <= kill_offset <= audio_segment.end_offset):
            return None
        
        return self.link_event_to_audio(
            event_type=EventType.KILL,
            event_id=kill.id,
            segment_id=audio_segment.id,
            event_offset=kill_offset,
            segment_start_offset=audio_segment.start_offset,
            context_before=context_before,
            context_after=context_after,
        )
    
    def link_all_events_in_segment(
        self,
        audio_segment: AudioSegment,
        context_before: Optional[float] = None,
        context_after: Optional[float] = None,
    ) -> list[EventAudioLink]:
        """
        Create links for all events within an audio segment's time range.
        
        Args:
            audio_segment: The audio segment
            context_before: Context seconds before events
            context_after: Context seconds after events
            
        Returns:
            List of created links
        """
        links = []
        
        # Find all kills in the segment's time range
        # First, find rounds that overlap with the segment
        rounds = self.session.query(Round).filter(
            Round.match_id == audio_segment.match_id,
            Round.start_offset.isnot(None),
        ).all()
        
        for round_obj in rounds:
            # Get kills in this round
            kills = self.session.query(Kill).filter(
                Kill.round_id == round_obj.id
            ).all()
            
            for kill in kills:
                link = self.link_kill_to_audio(
                    kill=kill,
                    audio_segment=audio_segment,
                    context_before=context_before,
                    context_after=context_after,
                )
                if link:
                    links.append(link)
        
        return links
    
    def get_audio_for_event(
        self,
        event_type: EventType,
        event_id: int,
    ) -> Optional[AudioClip]:
        """
        Get the audio clip for a specific event.
        
        Args:
            event_type: Type of event
            event_id: ID of the event
            
        Returns:
            AudioClip or None if not linked
        """
        link = self.session.query(EventAudioLink).filter(
            EventAudioLink.event_type == event_type,
            EventAudioLink.event_id == event_id,
        ).first()
        
        if not link:
            return None
        
        segment = self.session.query(AudioSegment).filter(
            AudioSegment.id == link.segment_id
        ).first()
        
        if not segment:
            return None
        
        return AudioClip(
            file_path=Path(segment.file_path),
            start_seconds=link.audio_start,
            end_seconds=link.audio_end,
            event_type=event_type.value,
            event_id=event_id,
            context_description=f"{link.context_before}s before, {link.context_after}s after",
        )
    
    def get_audio_for_kill(self, kill_id: int) -> Optional[AudioClip]:
        """Get audio clip for a specific kill."""
        return self.get_audio_for_event(EventType.KILL, kill_id)
    
    def get_events_in_audio_range(
        self,
        segment_id: int,
        start_seconds: float,
        end_seconds: float,
    ) -> list[EventAudioLink]:
        """
        Get all events that occur within a specific range of an audio segment.
        
        Args:
            segment_id: Audio segment ID
            start_seconds: Start position in audio (seconds)
            end_seconds: End position in audio (seconds)
            
        Returns:
            List of event links within the range
        """
        return self.session.query(EventAudioLink).filter(
            EventAudioLink.segment_id == segment_id,
            EventAudioLink.audio_start <= end_seconds,
            EventAudioLink.audio_end >= start_seconds,
        ).all()
    
    def get_all_links_for_match(self, match_id: str) -> list[EventAudioLink]:
        """
        Get all event-audio links for a match.
        
        Args:
            match_id: Match ID
            
        Returns:
            List of all links for the match
        """
        segments = self.session.query(AudioSegment).filter(
            AudioSegment.match_id == match_id
        ).all()
        
        segment_ids = [s.id for s in segments]
        
        return self.session.query(EventAudioLink).filter(
            EventAudioLink.segment_id.in_(segment_ids)
        ).all()

