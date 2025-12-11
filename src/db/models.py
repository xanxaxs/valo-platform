"""SQLAlchemy models for Valorant Tracker.

Migrated from tracker's TypeScript schema (Drizzle ORM) with additions
for audio synchronization from comms_tracker.
"""

from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from .database import Base


# ============================================
# Enums
# ============================================


class MatchResult(str, PyEnum):
    WIN = "Win"
    LOSE = "Lose"
    DRAW = "Draw"
    SPECTATED = "Spectated"


class MatchCategory(str, PyEnum):
    SCRIM = "scrim"
    RANKED = "ranked"
    TOURNAMENT = "tournament"
    CUSTOM = "custom"
    PRACTICE = "practice"


class WinCondition(str, PyEnum):
    ELIMINATION = "ELIMINATION"
    DEFUSE = "DEFUSE"
    DETONATE = "DETONATE"
    TIME = "TIME"


class EconomyTag(str, PyEnum):
    ECO = "ECO"
    FORCE = "FORCE"
    HALF_BUY = "HALF_BUY"
    FULL_BUY = "FULL_BUY"
    THRIFTY = "THRIFTY"
    BONUS = "BONUS"


class TimeSector(str, PyEnum):
    FIRST = "first"  # 1:40-1:20
    PREPARE = "prepare"  # 1:20-1:00
    SECOND = "second"  # 1:00-0:40
    LATE = "late"  # 0:40-0:00
    POSTPLANT = "postplant"


class EventType(str, PyEnum):
    ROUND_START = "round_start"
    KILL = "kill"
    PLANT = "plant"
    DEFUSE = "defuse"
    ROUND_END = "round_end"


class Sentiment(str, PyEnum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    PANIC = "panic"


# ============================================
# Core Match Models (from tracker)
# ============================================


class Match(Base):
    """Main match record."""

    __tablename__ = "matches"

    match_id = Column(String(36), primary_key=True)
    map_id = Column(String(36), nullable=False)
    map_name = Column(String(50), nullable=False)
    queue_id = Column(String(20), default="custom")
    game_start_millis = Column(Integer, nullable=False)
    game_length_millis = Column(Integer, nullable=False)
    result = Column(Enum(MatchResult), nullable=False)
    ally_score = Column(Integer, nullable=False)
    enemy_score = Column(Integer, nullable=False)
    completion_state = Column(String(50), nullable=False)
    is_coach_view = Column(Boolean, default=False)
    coached_team_id = Column(String(10), nullable=True)
    
    # Extended metadata
    custom_name = Column(String(100), nullable=True)
    category = Column(Enum(MatchCategory), default=MatchCategory.CUSTOM)
    team_id = Column(String(36), ForeignKey("teams.id"), nullable=True)
    opponent_name = Column(String(100), nullable=True)
    opponent_tag = Column(String(10), nullable=True)
    notes = Column(Text, nullable=True)
    tags = Column(JSON, nullable=True)  # JSON array
    is_hidden = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    rounds = relationship("Round", back_populates="match", cascade="all, delete-orphan")
    player_stats = relationship("PlayerMatchStats", back_populates="match", cascade="all, delete-orphan")
    audio_segments = relationship("AudioSegment", back_populates="match", cascade="all, delete-orphan")
    team = relationship("Team", back_populates="matches")


class Round(Base):
    """Round data within a match."""

    __tablename__ = "rounds"

    id = Column(Integer, primary_key=True, autoincrement=True)
    match_id = Column(String(36), ForeignKey("matches.match_id"), nullable=False)
    round_number = Column(Integer, nullable=False)
    result = Column(String(10), nullable=False)  # WIN/LOSS
    win_condition = Column(Enum(WinCondition), nullable=True)
    economy_tag = Column(Enum(EconomyTag), nullable=True)
    
    # Timing (offsets from match start in seconds)
    start_offset = Column(Float, nullable=True)
    end_offset = Column(Float, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    
    # Vision metadata
    survivors_count = Column(Integer, nullable=True)
    enemy_survivors = Column(Integer, nullable=True)

    # Relationships
    match = relationship("Match", back_populates="rounds")
    kills = relationship("Kill", back_populates="round", cascade="all, delete-orphan")
    ai_feedback = relationship("AIFeedback", back_populates="round", uselist=False, cascade="all, delete-orphan")


class Kill(Base):
    """Kill event with coordinates."""

    __tablename__ = "kills"

    id = Column(Integer, primary_key=True, autoincrement=True)
    match_id = Column(String(36), ForeignKey("matches.match_id"), nullable=False)
    round_id = Column(Integer, ForeignKey("rounds.id"), nullable=False)
    round_number = Column(Integer, nullable=False)
    game_time = Column(Integer, nullable=False)  # Milliseconds from round start
    killer_puuid = Column(String(36), nullable=False)
    victim_puuid = Column(String(36), nullable=False)
    victim_location_x = Column(Integer, nullable=False)
    victim_location_y = Column(Integer, nullable=False)
    assistants = Column(Text, nullable=True)  # Comma-separated PUUIDs
    weapon_id = Column(String(36), nullable=True)
    time_sector = Column(Enum(TimeSector), nullable=True)

    # Relationships
    round = relationship("Round", back_populates="kills")


# ============================================
# Player Models
# ============================================


class Player(Base):
    """Player information cache."""

    __tablename__ = "players"

    puuid = Column(String(36), primary_key=True)
    player_name = Column(String(50), nullable=False)
    tag_line = Column(String(10), nullable=False)
    last_seen = Column(DateTime, default=datetime.utcnow)


class PlayerMatchStats(Base):
    """Player statistics for a specific match."""

    __tablename__ = "player_match_stats"

    id = Column(String(100), primary_key=True)  # match_id_puuid
    match_id = Column(String(36), ForeignKey("matches.match_id"), nullable=False)
    puuid = Column(String(36), nullable=False)
    player_name = Column(String(50), nullable=False)
    tag_line = Column(String(10), nullable=False)
    agent_id = Column(String(36), nullable=False)
    agent_name = Column(String(30), nullable=False)
    team_id = Column(String(10), nullable=False)
    is_ally = Column(Boolean, nullable=False)
    
    # Basic stats
    kills = Column(Integer, default=0)
    deaths = Column(Integer, default=0)
    assists = Column(Integer, default=0)
    score = Column(Integer, default=0)
    
    # Damage stats
    damage_dealt = Column(Integer, default=0)
    damage_received = Column(Integer, default=0)
    
    # Shot stats
    headshots = Column(Integer, default=0)
    bodyshots = Column(Integer, default=0)
    legshots = Column(Integer, default=0)
    
    # Other
    first_bloods = Column(Integer, default=0)
    plants = Column(Integer, default=0)
    defuses = Column(Integer, default=0)

    # Relationships
    match = relationship("Match", back_populates="player_stats")


class PlayerMapStats(Base):
    """Aggregated player statistics by map."""

    __tablename__ = "player_map_stats"

    id = Column(String(100), primary_key=True)  # puuid_mapId
    puuid = Column(String(36), nullable=False)
    map_id = Column(String(36), nullable=False)
    map_name = Column(String(50), nullable=False)
    games_played = Column(Integer, default=0)
    wins = Column(Integer, default=0)
    kills = Column(Integer, default=0)
    deaths = Column(Integer, default=0)
    assists = Column(Integer, default=0)
    damage_dealt = Column(Integer, default=0)
    headshots = Column(Integer, default=0)
    bodyshots = Column(Integer, default=0)
    legshots = Column(Integer, default=0)
    updated_at = Column(Integer, nullable=False)


class PlayerAgentStats(Base):
    """Aggregated player statistics by agent."""

    __tablename__ = "player_agent_stats"

    id = Column(String(100), primary_key=True)  # puuid_agentId
    puuid = Column(String(36), nullable=False)
    agent_id = Column(String(36), nullable=False)
    agent_name = Column(String(30), nullable=False)
    games_played = Column(Integer, default=0)
    wins = Column(Integer, default=0)
    kills = Column(Integer, default=0)
    deaths = Column(Integer, default=0)
    assists = Column(Integer, default=0)
    damage_dealt = Column(Integer, default=0)
    updated_at = Column(Integer, nullable=False)


class PlayerTimeStats(Base):
    """Player statistics by time sector within rounds."""

    __tablename__ = "player_time_stats"

    id = Column(String(36), primary_key=True)  # puuid
    puuid = Column(String(36), nullable=False)
    
    # First (1:40-1:20)
    first_kills = Column(Integer, default=0)
    first_deaths = Column(Integer, default=0)
    
    # Prepare (1:20-1:00)
    prepare_kills = Column(Integer, default=0)
    prepare_deaths = Column(Integer, default=0)
    
    # Second (1:00-0:40)
    second_kills = Column(Integer, default=0)
    second_deaths = Column(Integer, default=0)
    
    # Late (0:40-0:00)
    late_kills = Column(Integer, default=0)
    late_deaths = Column(Integer, default=0)
    
    # Postplant
    postplant_kills = Column(Integer, default=0)
    postplant_deaths = Column(Integer, default=0)
    
    updated_at = Column(Integer, nullable=False)


# ============================================
# Team Management
# ============================================


class Team(Base):
    """Team information."""

    __tablename__ = "teams"

    id = Column(String(36), primary_key=True)
    name = Column(String(100), nullable=False)
    tag = Column(String(10), nullable=True)
    created_at = Column(Integer, nullable=False)
    updated_at = Column(Integer, nullable=False)

    # Relationships
    members = relationship("TeamMember", back_populates="team", cascade="all, delete-orphan")
    matches = relationship("Match", back_populates="team")


class TeamMember(Base):
    """Team member."""

    __tablename__ = "team_members"

    id = Column(String(36), primary_key=True)
    team_id = Column(String(36), ForeignKey("teams.id"), nullable=False)
    puuid = Column(String(36), nullable=False)
    player_name = Column(String(50), nullable=False)
    tag_line = Column(String(10), nullable=False)
    role = Column(String(30), nullable=True)  # IGL, Duelist, etc.
    joined_at = Column(Integer, nullable=False)

    # Relationships
    team = relationship("Team", back_populates="members")


# ============================================
# Audio Synchronization (NEW)
# ============================================


class AudioSegment(Base):
    """Audio recording segment linked to match/round."""

    __tablename__ = "audio_segments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    match_id = Column(String(36), ForeignKey("matches.match_id"), nullable=False)
    round_number = Column(Integer, nullable=True)  # None for full match recording
    file_path = Column(String(255), nullable=False)
    
    # Timing relative to match start (seconds)
    start_offset = Column(Float, nullable=False)
    end_offset = Column(Float, nullable=False)
    duration = Column(Float, nullable=False)
    
    # Recording metadata
    sample_rate = Column(Integer, default=16000)
    channels = Column(Integer, default=1)
    
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    match = relationship("Match", back_populates="audio_segments")
    transcripts = relationship("Transcript", back_populates="segment", cascade="all, delete-orphan")
    event_links = relationship("EventAudioLink", back_populates="segment", cascade="all, delete-orphan")


class EventAudioLink(Base):
    """Links game events to audio segments for quick lookup."""

    __tablename__ = "event_audio_links"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(Enum(EventType), nullable=False)
    event_id = Column(Integer, nullable=False)  # ID of the event (kill, round, etc.)
    segment_id = Column(Integer, ForeignKey("audio_segments.id"), nullable=False)
    
    # Position within the audio segment (seconds)
    audio_start = Column(Float, nullable=False)
    audio_end = Column(Float, nullable=False)
    
    # Context window (how much audio before/after the event)
    context_before = Column(Float, default=3.0)
    context_after = Column(Float, default=2.0)

    # Relationships
    segment = relationship("AudioSegment", back_populates="event_links")


class Transcript(Base):
    """Transcribed speech segment."""

    __tablename__ = "transcripts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    segment_id = Column(Integer, ForeignKey("audio_segments.id"), nullable=False)
    
    # Timing within the audio segment (seconds)
    time_offset = Column(Float, nullable=False)
    duration = Column(Float, nullable=True)
    
    # Content
    speaker_id = Column(String(50), nullable=True)  # Player ID or "unknown"
    content = Column(Text, nullable=False)
    
    # Analysis
    sentiment = Column(Enum(Sentiment), default=Sentiment.NEUTRAL)
    is_useful = Column(Boolean, default=True)
    confidence = Column(Float, default=1.0)

    # Relationships
    segment = relationship("AudioSegment", back_populates="transcripts")


# ============================================
# AI Coaching
# ============================================


class AIFeedback(Base):
    """AI-generated feedback for a round."""

    __tablename__ = "ai_feedback"

    id = Column(Integer, primary_key=True, autoincrement=True)
    round_id = Column(Integer, ForeignKey("rounds.id"), nullable=False)
    
    summary = Column(Text, nullable=False)
    score = Column(Integer, nullable=False)  # 0-100
    improvements = Column(JSON, nullable=True)  # List of improvement suggestions
    highlights = Column(JSON, nullable=True)  # List of positive highlights
    
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    round = relationship("Round", back_populates="ai_feedback")


# ============================================
# Replay Data
# ============================================


class MatchEventSnapshot(Base):
    """Snapshot of all player positions at a specific event."""

    __tablename__ = "match_event_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    match_id = Column(String(36), ForeignKey("matches.match_id"), nullable=False)
    round_number = Column(Integer, nullable=False)
    event_type = Column(Enum(EventType), nullable=False)
    game_time = Column(Integer, nullable=False)  # From match start
    round_time = Column(Integer, nullable=False)  # From round start
    event_data = Column(JSON, nullable=True)  # Killer, victim, weapon, etc.
    player_positions = Column(JSON, nullable=False)  # Array of all player positions


class RoundEconomy(Base):
    """Economy data for each player in a round."""

    __tablename__ = "round_economies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    match_id = Column(String(36), ForeignKey("matches.match_id"), nullable=False)
    round_number = Column(Integer, nullable=False)
    puuid = Column(String(36), nullable=False)
    loadout_value = Column(Integer, nullable=True)
    remaining = Column(Integer, nullable=True)
    spent = Column(Integer, nullable=True)
    weapon = Column(String(50), nullable=True)
    armor = Column(String(30), nullable=True)

