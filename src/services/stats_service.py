"""
Statistics Service.

Calculates and aggregates player statistics.
"""

import logging
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..db.models import (
    Kill,
    Match,
    PlayerAgentStats,
    PlayerMapStats,
    PlayerMatchStats,
    PlayerTimeStats,
    TimeSector,
)

logger = logging.getLogger(__name__)


class StatsService:
    """
    Service for calculating player statistics.
    
    Aggregates stats by:
    - Overall
    - Map
    - Agent
    - Time sector within rounds
    """
    
    def __init__(self, session: Session):
        """
        Initialize stats service.
        
        Args:
            session: Database session
        """
        self.session = session
    
    # ============================================
    # Overall Stats
    # ============================================
    
    def get_player_overall_stats(self, puuid: str) -> dict:
        """
        Get overall statistics for a player.
        
        Args:
            puuid: Player PUUID
            
        Returns:
            Dictionary of statistics
        """
        stats = self.session.query(PlayerMatchStats).filter(
            PlayerMatchStats.puuid == puuid
        ).all()
        
        if not stats:
            return {}
        
        total_kills = sum(s.kills for s in stats)
        total_deaths = sum(s.deaths for s in stats)
        total_assists = sum(s.assists for s in stats)
        total_games = len(stats)
        
        return {
            "games_played": total_games,
            "kills": total_kills,
            "deaths": total_deaths,
            "assists": total_assists,
            "kd_ratio": total_kills / max(total_deaths, 1),
            "kda_ratio": (total_kills + total_assists) / max(total_deaths, 1),
            "avg_kills": total_kills / total_games,
            "avg_deaths": total_deaths / total_games,
            "avg_assists": total_assists / total_games,
            "total_damage": sum(s.damage_dealt for s in stats),
            "avg_damage": sum(s.damage_dealt for s in stats) / total_games,
            "headshot_rate": self._calculate_headshot_rate(stats),
            "first_blood_rate": sum(s.first_bloods for s in stats) / total_games,
        }
    
    def _calculate_headshot_rate(self, stats: list[PlayerMatchStats]) -> float:
        """Calculate headshot percentage."""
        total_headshots = sum(s.headshots for s in stats)
        total_bodyshots = sum(s.bodyshots for s in stats)
        total_legshots = sum(s.legshots for s in stats)
        total_shots = total_headshots + total_bodyshots + total_legshots
        
        if total_shots == 0:
            return 0.0
        
        return total_headshots / total_shots
    
    # ============================================
    # Map Stats
    # ============================================
    
    def update_map_stats(self, puuid: str) -> None:
        """
        Update aggregated map statistics for a player.
        
        Args:
            puuid: Player PUUID
        """
        # Get all matches for player
        match_stats = self.session.query(PlayerMatchStats).filter(
            PlayerMatchStats.puuid == puuid
        ).all()
        
        # Group by map
        map_data: dict[str, dict] = {}
        
        for stat in match_stats:
            match = self.session.query(Match).filter(
                Match.match_id == stat.match_id
            ).first()
            
            if not match:
                continue
            
            map_id = match.map_id
            map_name = match.map_name
            
            if map_id not in map_data:
                map_data[map_id] = {
                    "map_name": map_name,
                    "games": 0,
                    "wins": 0,
                    "kills": 0,
                    "deaths": 0,
                    "assists": 0,
                    "damage": 0,
                    "headshots": 0,
                    "bodyshots": 0,
                    "legshots": 0,
                }
            
            data = map_data[map_id]
            data["games"] += 1
            if stat.is_ally:  # Only count wins for ally
                # Check if match was won
                is_win = match.result.value == "Win" if match.result else False
                if is_win:
                    data["wins"] += 1
            data["kills"] += stat.kills
            data["deaths"] += stat.deaths
            data["assists"] += stat.assists
            data["damage"] += stat.damage_dealt
            data["headshots"] += stat.headshots
            data["bodyshots"] += stat.bodyshots
            data["legshots"] += stat.legshots
        
        # Update/create map stats records
        import time
        now = int(time.time() * 1000)
        
        for map_id, data in map_data.items():
            stat_id = f"{puuid}_{map_id}"
            
            existing = self.session.query(PlayerMapStats).filter(
                PlayerMapStats.id == stat_id
            ).first()
            
            if existing:
                existing.games_played = data["games"]
                existing.wins = data["wins"]
                existing.kills = data["kills"]
                existing.deaths = data["deaths"]
                existing.assists = data["assists"]
                existing.damage_dealt = data["damage"]
                existing.headshots = data["headshots"]
                existing.bodyshots = data["bodyshots"]
                existing.legshots = data["legshots"]
                existing.updated_at = now
            else:
                new_stat = PlayerMapStats(
                    id=stat_id,
                    puuid=puuid,
                    map_id=map_id,
                    map_name=data["map_name"],
                    games_played=data["games"],
                    wins=data["wins"],
                    kills=data["kills"],
                    deaths=data["deaths"],
                    assists=data["assists"],
                    damage_dealt=data["damage"],
                    headshots=data["headshots"],
                    bodyshots=data["bodyshots"],
                    legshots=data["legshots"],
                    updated_at=now,
                )
                self.session.add(new_stat)
        
        self.session.commit()
    
    def get_map_stats(self, puuid: str) -> list[dict]:
        """
        Get map statistics for a player.
        
        Args:
            puuid: Player PUUID
            
        Returns:
            List of map stats dictionaries
        """
        stats = self.session.query(PlayerMapStats).filter(
            PlayerMapStats.puuid == puuid
        ).all()
        
        return [
            {
                "map_id": s.map_id,
                "map_name": s.map_name,
                "games_played": s.games_played,
                "wins": s.wins,
                "win_rate": s.wins / max(s.games_played, 1),
                "kills": s.kills,
                "deaths": s.deaths,
                "kd_ratio": s.kills / max(s.deaths, 1),
                "avg_damage": s.damage_dealt / max(s.games_played, 1),
            }
            for s in stats
        ]
    
    # ============================================
    # Agent Stats
    # ============================================
    
    def update_agent_stats(self, puuid: str) -> None:
        """
        Update aggregated agent statistics for a player.
        
        Args:
            puuid: Player PUUID
        """
        # Get all matches for player
        match_stats = self.session.query(PlayerMatchStats).filter(
            PlayerMatchStats.puuid == puuid
        ).all()
        
        # Group by agent
        agent_data: dict[str, dict] = {}
        
        for stat in match_stats:
            agent_id = stat.agent_id
            agent_name = stat.agent_name
            
            if agent_id not in agent_data:
                agent_data[agent_id] = {
                    "agent_name": agent_name,
                    "games": 0,
                    "wins": 0,
                    "kills": 0,
                    "deaths": 0,
                    "assists": 0,
                    "damage": 0,
                }
            
            data = agent_data[agent_id]
            data["games"] += 1
            data["kills"] += stat.kills
            data["deaths"] += stat.deaths
            data["assists"] += stat.assists
            data["damage"] += stat.damage_dealt
        
        # Update/create agent stats records
        import time
        now = int(time.time() * 1000)
        
        for agent_id, data in agent_data.items():
            stat_id = f"{puuid}_{agent_id}"
            
            existing = self.session.query(PlayerAgentStats).filter(
                PlayerAgentStats.id == stat_id
            ).first()
            
            if existing:
                existing.games_played = data["games"]
                existing.wins = data["wins"]
                existing.kills = data["kills"]
                existing.deaths = data["deaths"]
                existing.assists = data["assists"]
                existing.damage_dealt = data["damage"]
                existing.updated_at = now
            else:
                new_stat = PlayerAgentStats(
                    id=stat_id,
                    puuid=puuid,
                    agent_id=agent_id,
                    agent_name=data["agent_name"],
                    games_played=data["games"],
                    wins=data["wins"],
                    kills=data["kills"],
                    deaths=data["deaths"],
                    assists=data["assists"],
                    damage_dealt=data["damage"],
                    updated_at=now,
                )
                self.session.add(new_stat)
        
        self.session.commit()
    
    def get_agent_stats(self, puuid: str) -> list[dict]:
        """
        Get agent statistics for a player.
        
        Args:
            puuid: Player PUUID
            
        Returns:
            List of agent stats dictionaries
        """
        stats = self.session.query(PlayerAgentStats).filter(
            PlayerAgentStats.puuid == puuid
        ).all()
        
        return [
            {
                "agent_id": s.agent_id,
                "agent_name": s.agent_name,
                "games_played": s.games_played,
                "wins": s.wins,
                "win_rate": s.wins / max(s.games_played, 1),
                "kills": s.kills,
                "deaths": s.deaths,
                "kd_ratio": s.kills / max(s.deaths, 1),
            }
            for s in stats
        ]
    
    # ============================================
    # Time Sector Stats
    # ============================================
    
    def update_time_stats(self, puuid: str) -> None:
        """
        Update time sector statistics for a player.
        
        Tracks kills/deaths by time remaining in round.
        
        Args:
            puuid: Player PUUID
        """
        # Get all kills involving this player
        kills_as_killer = self.session.query(Kill).filter(
            Kill.killer_puuid == puuid,
            Kill.time_sector.isnot(None),
        ).all()
        
        kills_as_victim = self.session.query(Kill).filter(
            Kill.victim_puuid == puuid,
            Kill.time_sector.isnot(None),
        ).all()
        
        # Aggregate by time sector
        sector_kills = {sector: 0 for sector in TimeSector}
        sector_deaths = {sector: 0 for sector in TimeSector}
        
        for kill in kills_as_killer:
            if kill.time_sector:
                sector_kills[kill.time_sector] += 1
        
        for kill in kills_as_victim:
            if kill.time_sector:
                sector_deaths[kill.time_sector] += 1
        
        # Update/create time stats record
        import time
        now = int(time.time() * 1000)
        
        existing = self.session.query(PlayerTimeStats).filter(
            PlayerTimeStats.puuid == puuid
        ).first()
        
        if existing:
            existing.first_kills = sector_kills.get(TimeSector.FIRST, 0)
            existing.first_deaths = sector_deaths.get(TimeSector.FIRST, 0)
            existing.prepare_kills = sector_kills.get(TimeSector.PREPARE, 0)
            existing.prepare_deaths = sector_deaths.get(TimeSector.PREPARE, 0)
            existing.second_kills = sector_kills.get(TimeSector.SECOND, 0)
            existing.second_deaths = sector_deaths.get(TimeSector.SECOND, 0)
            existing.late_kills = sector_kills.get(TimeSector.LATE, 0)
            existing.late_deaths = sector_deaths.get(TimeSector.LATE, 0)
            existing.postplant_kills = sector_kills.get(TimeSector.POSTPLANT, 0)
            existing.postplant_deaths = sector_deaths.get(TimeSector.POSTPLANT, 0)
            existing.updated_at = now
        else:
            new_stat = PlayerTimeStats(
                id=puuid,
                puuid=puuid,
                first_kills=sector_kills.get(TimeSector.FIRST, 0),
                first_deaths=sector_deaths.get(TimeSector.FIRST, 0),
                prepare_kills=sector_kills.get(TimeSector.PREPARE, 0),
                prepare_deaths=sector_deaths.get(TimeSector.PREPARE, 0),
                second_kills=sector_kills.get(TimeSector.SECOND, 0),
                second_deaths=sector_deaths.get(TimeSector.SECOND, 0),
                late_kills=sector_kills.get(TimeSector.LATE, 0),
                late_deaths=sector_deaths.get(TimeSector.LATE, 0),
                postplant_kills=sector_kills.get(TimeSector.POSTPLANT, 0),
                postplant_deaths=sector_deaths.get(TimeSector.POSTPLANT, 0),
                updated_at=now,
            )
            self.session.add(new_stat)
        
        self.session.commit()
    
    def get_time_stats(self, puuid: str) -> Optional[dict]:
        """
        Get time sector statistics for a player.
        
        Args:
            puuid: Player PUUID
            
        Returns:
            Time stats dictionary or None
        """
        stat = self.session.query(PlayerTimeStats).filter(
            PlayerTimeStats.puuid == puuid
        ).first()
        
        if not stat:
            return None
        
        return {
            "first": {
                "kills": stat.first_kills,
                "deaths": stat.first_deaths,
                "kd": stat.first_kills / max(stat.first_deaths, 1),
            },
            "prepare": {
                "kills": stat.prepare_kills,
                "deaths": stat.prepare_deaths,
                "kd": stat.prepare_kills / max(stat.prepare_deaths, 1),
            },
            "second": {
                "kills": stat.second_kills,
                "deaths": stat.second_deaths,
                "kd": stat.second_kills / max(stat.second_deaths, 1),
            },
            "late": {
                "kills": stat.late_kills,
                "deaths": stat.late_deaths,
                "kd": stat.late_kills / max(stat.late_deaths, 1),
            },
            "postplant": {
                "kills": stat.postplant_kills,
                "deaths": stat.postplant_deaths,
                "kd": stat.postplant_kills / max(stat.postplant_deaths, 1),
            },
        }

