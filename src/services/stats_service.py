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
    RoundPlayerStats,
    TimeSector,
)

logger = logging.getLogger(__name__)


def get_timing_zone(round_time_remaining_seconds: float, is_post_plant: bool = False) -> str:
    """
    Get the timing zone based on round time remaining.
    
    Zones:
    - "1st": 1:40-1:20 (100s-80s remaining)
    - "1.5th": 1:20-1:00 (80s-60s remaining)
    - "2nd": 1:00-0:40 (60s-40s remaining)
    - "late": 0:40-0:00 (40s-0s remaining)
    - "pp": Post Plant
    
    Args:
        round_time_remaining_seconds: Seconds remaining in round
        is_post_plant: Whether spike has been planted
        
    Returns:
        Timing zone string
    """
    if is_post_plant:
        return "pp"
    
    if round_time_remaining_seconds >= 80:
        return "1st"
    elif round_time_remaining_seconds >= 60:
        return "1.5th"
    elif round_time_remaining_seconds >= 40:
        return "2nd"
    else:
        return "late"


def get_timing_zone_from_elapsed(round_time_elapsed_ms: int, round_duration_ms: int = 100000, is_post_plant: bool = False) -> str:
    """
    Get timing zone from elapsed time (Valorant API format).
    
    Args:
        round_time_elapsed_ms: Milliseconds elapsed since round start
        round_duration_ms: Total round duration in ms (default 100s)
        is_post_plant: Whether spike has been planted
        
    Returns:
        Timing zone string
    """
    if is_post_plant:
        return "pp"
    
    remaining_seconds = (round_duration_ms - round_time_elapsed_ms) / 1000
    return get_timing_zone(remaining_seconds, is_post_plant)


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
    
    # ============================================
    # Detailed Match Stats Display
    # ============================================
    
    def get_match_detailed_stats(self, match_id: str) -> list[dict]:
        """
        Get detailed stats for all players in a match.
        
        Returns stats in display format: ACS, KDA, FK, FD, True FK, KAST, etc.
        
        Args:
            match_id: Match ID
            
        Returns:
            List of player stats dictionaries sorted by ACS
        """
        stats = self.session.query(PlayerMatchStats).filter(
            PlayerMatchStats.match_id == match_id
        ).all()
        
        result = []
        for s in stats:
            rounds = max(s.rounds_played, 1)
            
            # Calculate time-based KD from JSON
            import json
            try:
                time_kd = json.loads(s.time_based_kd) if s.time_based_kd else {}
            except:
                time_kd = {}
            
            result.append({
                "puuid": s.puuid,
                "player_name": s.player_name,
                "tag_line": s.tag_line,
                "agent_name": s.agent_name,
                "team_id": s.team_id,
                "is_ally": s.is_ally,
                
                # Core stats
                "acs": s.acs,
                "kda": s.kda,
                "kills": s.kills,
                "deaths": s.deaths,
                "assists": s.assists,
                "kd_ratio": s.kd_ratio,
                
                # First blood
                "fk": s.first_kills,
                "fd": s.first_deaths,
                "fk_fd_diff": s.fk_fd_diff,
                "true_fk": s.true_first_kills,  # FK取得かつラウンド勝利
                "true_fk_rate": s.true_fk_rate,
                
                # KAST
                "kast": s.kast_percentage,
                
                # Damage
                "damage_dealt": s.damage_dealt,
                "adr": round(s.damage_dealt / rounds, 1),
                
                # Accuracy
                "hs_percent": s.headshot_percentage,
                
                # Multi-kills
                "multi_kills": {
                    "2k": s.multi_kills_2,
                    "3k": s.multi_kills_3,
                    "4k": s.multi_kills_4,
                    "ace": s.multi_kills_5,
                },
                
                # Clutches
                "clutch_wins": s.clutch_wins,
                "clutch_attempts": s.clutch_attempts,
                
                # Time-based KD (5 zones)
                # 1st: 1:40-1:20, 1.5th: 1:20-1:00, 2nd: 1:00-0:40, late: 0:40-0:00, pp: post plant
                "time_kd": {
                    "1st": time_kd.get("1st", {"k": 0, "d": 0}),
                    "1.5th": time_kd.get("1.5th", {"k": 0, "d": 0}),
                    "2nd": time_kd.get("2nd", {"k": 0, "d": 0}),
                    "late": time_kd.get("late", {"k": 0, "d": 0}),
                    "pp": time_kd.get("pp", {"k": 0, "d": 0}),
                },
                
                # Economy
                "avg_loadout": s.avg_loadout_value,
                
                # Utility
                "plants": s.plants,
                "defuses": s.defuses,
                
                # Rounds played
                "rounds_played": s.rounds_played,
            })
        
        # Sort by ACS descending
        result.sort(key=lambda x: x["acs"], reverse=True)
        return result
    
    def format_stats_table(self, match_id: str) -> str:
        """
        Format match stats as a text table.
        
        Args:
            match_id: Match ID
            
        Returns:
            Formatted table string
        """
        stats = self.get_match_detailed_stats(match_id)
        
        if not stats:
            return "No stats available"
        
        # Header
        lines = [
            "=" * 110,
            f"{'Player':<20} {'Agent':<10} {'ACS':>5} {'K/D/A':>10} {'KD':>5} {'FK':>3} {'FD':>3} {'TFK':>3} {'±FK':>4} {'KAST':>6} {'HS%':>5}",
            "-" * 110,
        ]
        
        current_team = None
        for s in stats:
            # Team separator
            if current_team != s["team_id"]:
                if current_team is not None:
                    lines.append("-" * 110)
                current_team = s["team_id"]
            
            lines.append(
                f"{s['player_name']:<20} {s['agent_name']:<10} "
                f"{s['acs']:>5.0f} {s['kda']:>10} {s['kd_ratio']:>5.2f} "
                f"{s['fk']:>3} {s['fd']:>3} {s['true_fk']:>3} {s['fk_fd_diff']:>+4} "
                f"{s['kast']:>5.1f}% {s['hs_percent']:>4.1f}%"
            )
        
        lines.append("=" * 110)
        return "\n".join(lines)
    
    # ============================================
    # Parse Match Details from API
    # ============================================
    
    def parse_match_details(self, match_details: dict) -> dict:
        """
        Parse match details from Valorant API into player stats.
        
        Args:
            match_details: Raw match details from API
            
        Returns:
            Parsed stats by player
        """
        players_stats = {}
        
        # Get players data
        players = match_details.get("players", [])
        rounds = match_details.get("roundResults", [])
        
        # Build team mapping
        team_players = {}  # team_id -> set of puuids
        
        for player in players:
            puuid = player.get("subject", "")
            team_id = player.get("teamId", "")
            stats = player.get("stats", {})
            
            if team_id not in team_players:
                team_players[team_id] = set()
            team_players[team_id].add(puuid)
            
            players_stats[puuid] = {
                "puuid": puuid,
                "team_id": team_id,
                "character_id": player.get("characterId", ""),
                "kills": stats.get("kills", 0),
                "deaths": stats.get("deaths", 0),
                "assists": stats.get("assists", 0),
                "score": stats.get("score", 0),
                "rounds_played": stats.get("roundsPlayed", len(rounds)),
                "damage_dealt": 0,
                "first_kills": 0,
                "first_deaths": 0,
                "true_first_kills": 0,  # FK取得 & ラウンド勝利
                "kast_rounds": 0,
                "multi_kills": {2: 0, 3: 0, 4: 0, 5: 0},
                "time_based_kd": {
                    "1st": {"k": 0, "d": 0},
                    "1.5th": {"k": 0, "d": 0},
                    "2nd": {"k": 0, "d": 0},
                    "late": {"k": 0, "d": 0},
                    "pp": {"k": 0, "d": 0},
                },
            }
        
        # Process each round for detailed stats
        for round_data in rounds:
            round_num = round_data.get("roundNum", 0)
            winning_team = round_data.get("winningTeam", "")
            plant_time = round_data.get("plantRoundTime", 0)  # Time of plant in ms
            player_stats_in_round = round_data.get("playerStats", [])
            
            # Find first kill/death in round
            first_killer = None
            first_victim = None
            first_kill_time = float("inf")
            
            kills_in_round = {}  # puuid -> kill count
            deaths_in_round = set()  # puuids who died
            assists_in_round = set()  # puuids who assisted
            traded_deaths = set()  # puuids who were traded
            
            # Collect all kills for time-based analysis
            all_kills = []
            
            for ps in player_stats_in_round:
                puuid = ps.get("subject", "")
                damage = ps.get("damage", [])
                kills = ps.get("kills", [])
                
                # Add damage
                if puuid in players_stats:
                    for d in damage:
                        players_stats[puuid]["damage_dealt"] += d.get("damage", 0)
                
                # Track kills
                kills_in_round[puuid] = len(kills)
                
                for kill in kills:
                    victim = kill.get("victim", "")
                    kill_time = kill.get("roundTimeMillis", 0)
                    
                    all_kills.append({
                        "killer": puuid,
                        "victim": victim,
                        "time": kill_time,
                    })
                    
                    # Track first kill
                    if kill_time < first_kill_time:
                        first_kill_time = kill_time
                        first_killer = puuid
                        first_victim = victim
                    
                    deaths_in_round.add(victim)
                    
                    # Track assists
                    for assist in kill.get("assistants", []):
                        assists_in_round.add(assist.get("assistantPuuid", ""))
            
            # Update first kill/death stats
            if first_killer and first_killer in players_stats:
                players_stats[first_killer]["first_kills"] += 1
                
                # True FK: FK取得かつラウンド勝利
                fk_team = players_stats[first_killer]["team_id"]
                if fk_team == winning_team:
                    players_stats[first_killer]["true_first_kills"] += 1
                    
            if first_victim and first_victim in players_stats:
                players_stats[first_victim]["first_deaths"] += 1
            
            # Process time-based KD
            for kill_data in all_kills:
                killer = kill_data["killer"]
                victim = kill_data["victim"]
                kill_time = kill_data["time"]
                
                # Check if post-plant
                is_post_plant = plant_time > 0 and kill_time > plant_time
                
                # Get timing zone
                timing_zone = get_timing_zone_from_elapsed(kill_time, is_post_plant=is_post_plant)
                
                # Update time-based KD
                if killer in players_stats:
                    players_stats[killer]["time_based_kd"][timing_zone]["k"] += 1
                if victim in players_stats:
                    players_stats[victim]["time_based_kd"][timing_zone]["d"] += 1
            
            # Calculate KAST and multi-kills for each player
            survivors = set(players_stats.keys()) - deaths_in_round
            
            for puuid in players_stats:
                got_kill = kills_in_round.get(puuid, 0) > 0
                got_assist = puuid in assists_in_round
                survived = puuid in survivors
                got_traded = puuid in traded_deaths
                
                if got_kill or got_assist or survived or got_traded:
                    players_stats[puuid]["kast_rounds"] += 1
                
                # Multi-kills
                kill_count = kills_in_round.get(puuid, 0)
                if kill_count >= 2:
                    players_stats[puuid]["multi_kills"][min(kill_count, 5)] += 1
        
        return players_stats

