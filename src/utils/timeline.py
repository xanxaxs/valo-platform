"""
Timeline Synchronization Utilities

Merges vision events with audio transcripts by timestamp.
"""

from datetime import datetime, timedelta
from typing import Optional

from src.models.schemas import Round, TranscriptSegment, VisionAnalysis


class TimelineSync:
    """
    Synchronizes vision and audio events into a unified timeline.

    Handles time offset calculations and event correlation.
    """

    def __init__(self, round_start_time: Optional[datetime] = None):
        """
        Initialize timeline synchronizer.

        Args:
            round_start_time: Absolute time of round start
        """
        self.round_start_time = round_start_time or datetime.now()
        self._events: list[dict] = []

    def add_vision_event(
        self,
        event_type: str,
        timestamp: datetime,
        data: Optional[dict] = None,
    ) -> None:
        """Add a vision-detected event to timeline."""
        offset = (timestamp - self.round_start_time).total_seconds()
        self._events.append({
            "type": "vision",
            "event": event_type,
            "offset": max(0, offset),
            "timestamp": timestamp,
            "data": data or {},
        })

    def add_transcript_segment(self, segment: TranscriptSegment) -> None:
        """Add a transcript segment to timeline."""
        self._events.append({
            "type": "audio",
            "event": "speech",
            "offset": segment.time_offset,
            "timestamp": self.round_start_time + timedelta(seconds=segment.time_offset),
            "data": {
                "speaker": segment.speaker_id,
                "content": segment.content,
                "sentiment": segment.sentiment.value,
            },
        })

    def get_sorted_events(self) -> list[dict]:
        """Get all events sorted by time offset."""
        return sorted(self._events, key=lambda e: e["offset"])

    def find_speech_at_event(
        self,
        event_offset: float,
        window_seconds: float = 3.0,
    ) -> list[dict]:
        """
        Find speech events around a specific timestamp.

        Args:
            event_offset: Time offset of the event
            window_seconds: Time window to search (before and after)

        Returns:
            List of speech events within the window
        """
        return [
            e for e in self._events
            if e["type"] == "audio"
            and abs(e["offset"] - event_offset) <= window_seconds
        ]

    def find_vision_at_speech(
        self,
        speech_offset: float,
        window_seconds: float = 2.0,
    ) -> list[dict]:
        """Find vision events around a speech timestamp."""
        return [
            e for e in self._events
            if e["type"] == "vision"
            and abs(e["offset"] - speech_offset) <= window_seconds
        ]

    def correlate_kills_with_callouts(
        self,
        kill_events: list[dict],
        transcripts: list[TranscriptSegment],
        pre_window: float = 1.0,
        post_window: float = 2.0,
    ) -> list[dict]:
        """
        Correlate kill events with voice callouts.

        Find what was being said before/after each kill.

        Args:
            kill_events: List of kill events with timing
            transcripts: List of transcript segments
            pre_window: Seconds before kill to search
            post_window: Seconds after kill to search

        Returns:
            List of correlated events
        """
        correlations = []

        for kill in kill_events:
            kill_time = kill.get("offset", 0)

            # Find relevant callouts
            pre_callouts = [
                t for t in transcripts
                if kill_time - pre_window <= t.time_offset <= kill_time
            ]
            post_callouts = [
                t for t in transcripts
                if kill_time < t.time_offset <= kill_time + post_window
            ]

            correlations.append({
                "kill": kill,
                "pre_callouts": pre_callouts,
                "post_callouts": post_callouts,
                "had_callout_before": len(pre_callouts) > 0,
            })

        return correlations

    def build_round(
        self,
        round_number: int,
        vision: VisionAnalysis,
        transcripts: list[TranscriptSegment],
    ) -> Round:
        """
        Build a complete Round object from timeline data.

        Args:
            round_number: Round number (1-25)
            vision: Vision analysis result
            transcripts: List of transcript segments

        Returns:
            Complete Round object
        """
        # Calculate duration from events
        events = self.get_sorted_events()
        duration = int(events[-1]["offset"]) if events else 0

        return Round(
            round_number=round_number,
            result=vision.result,
            win_condition=vision.win_condition,
            economy_tag=vision.economy_tag,
            duration_seconds=duration,
            vision_metadata=vision.vision_metadata,
            transcript=transcripts,
        )

    def reset(self, new_start_time: Optional[datetime] = None) -> None:
        """Reset timeline for new round."""
        self.round_start_time = new_start_time or datetime.now()
        self._events.clear()
