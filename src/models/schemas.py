"""
Tactical Echo - Data Models (Pydantic Schemas)

Based on the target JSON schema for match data output.
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class Sentiment(str, Enum):
    """Sentiment classification for voice communications."""

    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    PANIC = "panic"


class WinCondition(str, Enum):
    """Round win conditions in Valorant."""

    ELIMINATION = "ELIMINATION"
    DEFUSE = "DEFUSE"
    DETONATE = "DETONATE"
    TIME = "TIME"


class RoundResult(str, Enum):
    """Round result."""

    WIN = "WIN"
    LOSS = "LOSS"


class EconomyTag(str, Enum):
    """Economy classification for rounds."""

    ECO = "ECO"
    FORCE = "FORCE"
    HALF_BUY = "HALF_BUY"
    FULL_BUY = "FULL_BUY"
    THRIFTY = "THRIFTY"
    BONUS = "BONUS"


# --- Vision Models ---


class VisionMetadata(BaseModel):
    """Vision analysis metadata from screenshot."""

    survivors_count: int = Field(ge=0, le=5, description="Surviving teammates")
    enemy_survivors: int = Field(ge=0, le=5, description="Surviving enemies")


class PlayerPosition(BaseModel):
    """Player position extracted from minimap."""

    player_id: str
    x: float = Field(description="X coordinate on minimap (normalized 0-1)")
    y: float = Field(description="Y coordinate on minimap (normalized 0-1)")
    is_alive: bool = True


class RoundEvent(BaseModel):
    """Detected round event from vision pipeline."""

    event_type: str  # VICTORY, DEFEAT, CLUTCH, ROUND_START, ROUND_END
    timestamp: datetime = Field(default_factory=datetime.now)
    screenshot_path: Optional[str] = None


class VisionAnalysis(BaseModel):
    """Complete vision analysis result from VLM."""

    result: RoundResult
    win_condition: WinCondition
    economy_tag: EconomyTag
    vision_metadata: VisionMetadata
    raw_response: Optional[str] = None


# --- Audio Models ---


class TranscriptSegment(BaseModel):
    """Single transcription segment with speaker and timing."""

    time_offset: float = Field(description="Offset in seconds from round start")
    speaker_id: str = Field(description="Identified speaker (player ID)")
    content: str = Field(description="Transcribed text")
    sentiment: Sentiment = Sentiment.NEUTRAL
    is_useful: bool = Field(default=True, description="Whether the callout was useful")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class SpeakerEmbedding(BaseModel):
    """Stored speaker voice embedding for identification."""

    user_id: str
    display_name: str
    embedding_path: str
    created_at: datetime = Field(default_factory=datetime.now)


# --- Intelligence Models ---


class AIFeedback(BaseModel):
    """AI-generated feedback for a round."""

    summary: str = Field(description="Brief feedback summary")
    score: int = Field(ge=0, le=100, description="Round performance score")
    improvements: list[str] = Field(default_factory=list)
    highlights: list[str] = Field(default_factory=list)


# --- Composite Models (Output Schema) ---


class Round(BaseModel):
    """Complete round data with vision, audio, and AI analysis."""

    round_number: int = Field(ge=1, le=25)
    result: RoundResult
    win_condition: WinCondition
    economy_tag: EconomyTag
    duration_seconds: int = Field(ge=0)
    vision_metadata: VisionMetadata
    transcript: list[TranscriptSegment] = Field(default_factory=list)
    ai_feedback: Optional[AIFeedback] = None
    key_events: list[dict] = Field(default_factory=list, description="Kill events with timing")


class MatchData(BaseModel):
    """Top-level match data output schema."""

    match_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=datetime.now)
    map_name: str
    team_id: str
    rounds: list[Round] = Field(default_factory=list)

    def to_json_file(self, path: str) -> None:
        """Export match data to JSON file."""
        from pathlib import Path

        Path(path).write_text(self.model_dump_json(indent=2), encoding="utf-8")

    @classmethod
    def from_json_file(cls, path: str) -> "MatchData":
        """Load match data from JSON file."""
        from pathlib import Path

        return cls.model_validate_json(Path(path).read_text(encoding="utf-8"))
