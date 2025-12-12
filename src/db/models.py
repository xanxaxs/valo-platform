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
    score = Column(Integer, default=0)  # Combat score total
    rounds_played = Column(Integer, default=0)
    
    # Damage stats
    damage_dealt = Column(Integer, default=0)
    damage_received = Column(Integer, default=0)
    
    # Shot stats
    headshots = Column(Integer, default=0)
    bodyshots = Column(Integer, default=0)
    legshots = Column(Integer, default=0)
    
    # First blood stats
    first_kills = Column(Integer, default=0)  # FK - First Kills
    first_deaths = Column(Integer, default=0)  # FD - First Deaths
    true_first_kills = Column(Integer, default=0)  # True FK - FK取得かつラウンド勝利
    
    # KAST components (per round tracking)
    kast_rounds = Column(Integer, default=0)  # Rounds with Kill/Assist/Survive/Trade
    
    # Multi-kills
    multi_kills_2 = Column(Integer, default=0)  # 2K rounds
    multi_kills_3 = Column(Integer, default=0)  # 3K rounds
    multi_kills_4 = Column(Integer, default=0)  # 4K rounds
    multi_kills_5 = Column(Integer, default=0)  # Ace rounds
    
    # Clutch stats
    clutch_wins = Column(Integer, default=0)
    clutch_attempts = Column(Integer, default=0)
    
    # Economy stats
    avg_loadout_value = Column(Integer, default=0)
    avg_credits_spent = Column(Integer, default=0)
    
    # Legacy fields (for backward compatibility)
    first_bloods = Column(Integer, default=0)  # Alias for first_kills
    plants = Column(Integer, default=0)
    defuses = Column(Integer, default=0)
    
    # Time-based KD (JSON format)
    # Timing zones based on round time remaining:
    #   - "1st": 1:40-1:20 (100s-80s remaining)
    #   - "1.5th": 1:20-1:00 (80s-60s remaining)  
    #   - "2nd": 1:00-0:40 (60s-40s remaining)
    #   - "late": 0:40-0:00 (40s-0s remaining)
    #   - "pp": Post Plant
    # Format: {"1st": {"k": 0, "d": 0}, "1.5th": {...}, "2nd": {...}, "late": {...}, "pp": {...}}
    time_based_kd = Column(Text, default="{}")  # JSON string
    
    # Round-by-round performance (JSON array)
    round_performance = Column(Text, default="[]")  # JSON string

    # Relationships
    match = relationship("Match", back_populates="player_stats")
    
    # Computed properties
    @property
    def acs(self) -> float:
        """Average Combat Score per round."""
        if self.rounds_played == 0:
            return 0.0
        return round(self.score / self.rounds_played, 1)
    
    @property
    def kda(self) -> str:
        """KDA string."""
        return f"{self.kills}/{self.deaths}/{self.assists}"
    
    @property
    def kd_ratio(self) -> float:
        """Kill/Death ratio."""
        if self.deaths == 0:
            return float(self.kills)
        return round(self.kills / self.deaths, 2)
    
    @property
    def fk_fd_diff(self) -> int:
        """First Kill differential (FK - FD)."""
        return self.first_kills - self.first_deaths
    
    @property
    def true_fk_rate(self) -> float:
        """True FK rate - percentage of FKs that resulted in round wins."""
        if self.first_kills == 0:
            return 0.0
        return round((self.true_first_kills / self.first_kills) * 100, 1)
    
    @property
    def kast_percentage(self) -> float:
        """KAST percentage."""
        if self.rounds_played == 0:
            return 0.0
        return round((self.kast_rounds / self.rounds_played) * 100, 1)
    
    @property
    def headshot_percentage(self) -> float:
        """Headshot percentage."""
        total_shots = self.headshots + self.bodyshots + self.legshots
        if total_shots == 0:
            return 0.0
        return round((self.headshots / total_shots) * 100, 1)


class RoundPlayerStats(Base):
    """Per-round player statistics for detailed analysis."""
    
    __tablename__ = "round_player_stats"
    
    id = Column(String(150), primary_key=True)  # match_id_round_puuid
    match_id = Column(String(36), ForeignKey("matches.match_id"), nullable=False)
    round_number = Column(Integer, nullable=False)
    puuid = Column(String(36), nullable=False)
    
    # Round outcome for this player
    kills = Column(Integer, default=0)
    deaths = Column(Integer, default=0)
    assists = Column(Integer, default=0)
    damage_dealt = Column(Integer, default=0)
    
    # First engagement
    is_first_kill = Column(Boolean, default=False)
    is_first_death = Column(Boolean, default=False)
    
    # KAST components
    got_kill = Column(Boolean, default=False)
    got_assist = Column(Boolean, default=False)
    survived = Column(Boolean, default=False)
    got_traded = Column(Boolean, default=False)  # Died but was traded
    
    # Economy
    loadout_value = Column(Integer, default=0)
    credits_remaining = Column(Integer, default=0)
    
    # Time-based timing zones (based on round time remaining)
    # "1st" = 1:40-1:20, "1.5th" = 1:20-1:00, "2nd" = 1:00-0:40, "late" = 0:40-0:00, "pp" = post plant
    kill_timing = Column(String(10), default="")  # "1st", "1.5th", "2nd", "late", "pp"
    death_timing = Column(String(10), default="")
    
    # Round time in seconds when kill/death happened
    kill_time_seconds = Column(Float, default=0.0)
    death_time_seconds = Column(Float, default=0.0)


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
# Transcript Data
# ============================================


class TranscriptSegment(Base):
    """Speech transcript segment from audio."""
    
    __tablename__ = "transcript_segments"
    
    id = Column(String(100), primary_key=True)  # match_id_t{index}
    match_id = Column(String(36), ForeignKey("matches.match_id"), nullable=False)
    round_number = Column(Integer, nullable=True)  # May be null for full match
    start_time = Column(Float, nullable=False)  # Start time in seconds
    end_time = Column(Float, nullable=False)  # End time in seconds
    text = Column(Text, nullable=False)
    speaker = Column(String(50), default="Unknown")
    confidence = Column(Float, default=0.0)
    
    created_at = Column(DateTime, default=datetime.utcnow)


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

