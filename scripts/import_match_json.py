"""
Import match data from JSON to database.
"""
import json
import sys
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db.database import get_session, init_db
from src.db.models import Match, PlayerMatchStats, Round, Kill, MatchResult, MatchCategory, WinCondition

# Initialize DB
init_db()

# Agent ID to name mapping
AGENT_NAMES = {
    "e370fa57-4757-3604-3648-499e1f642d3f": "Gekko",
    "dade69b4-4f5a-8528-247b-219e5a1facd6": "Fade",
    "5f8d3a7f-467b-97f3-062c-13acf203c006": "Breach",
    "cc8b64c8-4b25-4ff9-6e7f-37b4da43d235": "Deadlock",
    "f94c3b30-42be-e959-889c-5aa313dba261": "Raze",
    "22697a3d-45bf-8dd7-4fec-84a9e28c69d7": "Chamber",
    "601dbbe7-43ce-be57-2a40-4abd24953621": "KAY/O",
    "6f2a04ca-43e0-be17-7f36-b3908627744d": "Skye",
    "117ed9e3-49f3-6512-3ccf-0cada7e3823b": "Cypher",
    "ded3520f-4264-bfed-162d-b080e2abccf9": "Sova",
    "320b2a48-4d9b-a075-30f1-1f93a9b638fa": "Sova",
    "1e58de9c-4950-5125-93e9-a0aee9f98746": "Killjoy",
    "707eab51-4836-f488-046a-cda6bf494859": "Viper",
    "eb93336a-449b-9c1b-0a54-a891f7921d69": "Phoenix",
    "41fb69c1-4189-7b37-f117-bcaf1e96f1bf": "Astra",
    "9f0d8ba9-4140-b941-57d3-a7ad57c6b417": "Brimstone",
    "7f94d92c-4234-0a36-9646-3a87eb8b5c89": "Yoru",
    "569fdd95-4d10-43ab-ca70-79becc718b46": "Sage",
    "a3bfb853-43b2-7238-a4f1-ad90e9e46bcc": "Reyna",
    "8e253930-4c05-31dd-1b6c-968525494517": "Omen",
    "add6443a-41bd-e414-f6ad-e58d267f4e95": "Jett",
    "bb2a4828-46eb-8cd1-e765-15848195d751": "Neon",
    "0e38b510-41a8-5780-5e8f-568b2a4f2d6c": "Iso",
    "efba5359-4016-a1e5-7626-b1ae76895940": "Harbor",
    "95b78ed7-4637-86d9-7e41-71ba8c293152": "Harbor",
    "1dbf2edd-4729-0984-3115-daa5eed44993": "Clove",
    "df1cb487-1d77-a042-2203-d4a89ef2da10": "Waylay",
    "df1cb487-4902-002e-5c17-d28e83e78588": "Waylay",  # Tejo -> Waylay (variant ID)
}

# Map ID to name
MAP_NAMES = {
    "Ascent": "Ascent",
    "Duality": "Bind", 
    "Bonsai": "Split",
    "Triad": "Haven",
    "Port": "Icebox",
    "Foxtrot": "Breeze",
    "Canyon": "Fracture",
    "Pitt": "Pearl",
    "Jam": "Lotus",
    "Juliett": "Sunset",
    "Infinity": "Abyss",
    "HURM_Alley": "District",
    "HURM_Bowl": "Kasbah",
    "HURM_Yard": "Drift",
    "HURM_Helix": "Piazza",
    "Corro": "Corrode",
    "Rook": "Corrode",  # Rook is internal name for Corrode
}

def get_map_name(map_id: str) -> str:
    """Extract map name from map ID."""
    # Extract map code from path
    if "/" in map_id:
        parts = map_id.split("/")
        map_code = parts[-1] if parts else map_id
    else:
        map_code = map_id
    
    return MAP_NAMES.get(map_code, map_code)

def get_agent_name(agent_id: str) -> str:
    """Get agent name from ID."""
    if not agent_id:
        return "Unknown"
    return AGENT_NAMES.get(agent_id, f"Unknown ({agent_id[:8]})")

def calculate_detailed_stats(match_data: dict) -> dict:
    """Calculate FK, FD, TrueFK, HS%, time-based K/D, and KAST."""
    players = match_data.get("players", [])
    rounds = match_data.get("roundResults", [])
    
    # Build player team map
    player_teams = {p.get("subject"): p.get("teamId") for p in players}
    all_puuids = set(player_teams.keys())
    
    # Initialize stats
    stats = defaultdict(lambda: {
        "first_kills": 0,
        "first_deaths": 0,
        "true_first_kills": 0,
        "headshots": 0,
        "bodyshots": 0,
        "legshots": 0,
        "kast_rounds": 0,
        "rounds_played": 0,
        "time_based_kd": {
            "1st": {"k": 0, "d": 0},
            "1.5th": {"k": 0, "d": 0},
            "2nd": {"k": 0, "d": 0},
            "Late": {"k": 0, "d": 0},
            "PP": {"k": 0, "d": 0},
        },
    })
    
    TRADE_WINDOW_MS = 5000  # 5 seconds for trade
    
    for r in rounds:
        winning_team = r.get("winningTeam", "")
        plant_time = r.get("plantRoundTime")
        
        first_kill_time = float('inf')
        first_killer = None
        first_victim = None
        
        # Collect all kills in this round with timing
        round_kills = []  # [(time, killer, victim), ...]
        round_killers = set()
        round_assisters = set()
        round_deaths = set()
        
        for ps in r.get("playerStats", []):
            puuid = ps.get("subject", "")
            stats[puuid]["rounds_played"] += 1
            
            # Headshot stats from damage
            for dmg in ps.get("damage", []):
                stats[puuid]["headshots"] += dmg.get("headshots", 0)
                stats[puuid]["bodyshots"] += dmg.get("bodyshots", 0)
                stats[puuid]["legshots"] += dmg.get("legshots", 0)
            
            # Process kills
            for kill in ps.get("kills", []):
                round_time = kill.get("roundTime", 0)
                killer = kill.get("killer", "")
                victim = kill.get("victim", "")
                assistants = kill.get("assistants", []) or []
                
                round_kills.append((round_time, killer, victim))
                if killer:
                    round_killers.add(killer)
                if victim:
                    round_deaths.add(victim)
                for assist in assistants:
                    if assist:
                        round_assisters.add(assist)
                
                if round_time < first_kill_time:
                    first_kill_time = round_time
                    first_killer = killer
                    first_victim = victim
                
                # Time zone
                zone = get_time_zone(round_time, plant_time)
                if killer in stats:
                    stats[killer]["time_based_kd"][zone]["k"] += 1
                if victim in stats:
                    stats[victim]["time_based_kd"][zone]["d"] += 1
        
        # Calculate trades (victim was traded if their killer died within TRADE_WINDOW_MS)
        round_kills_sorted = sorted(round_kills, key=lambda x: x[0])
        traded_players = set()
        
        for i, (death_time, killer, victim) in enumerate(round_kills_sorted):
            if not victim or not killer:
                continue
            # Check if killer died within trade window after this kill
            for j in range(i + 1, len(round_kills_sorted)):
                later_time, later_killer, later_victim = round_kills_sorted[j]
                if later_time - death_time > TRADE_WINDOW_MS:
                    break
                if later_victim == killer:
                    # The killer was traded - original victim gets trade credit
                    traded_players.add(victim)
                    break
        
        # Survivors = players who participated but didn't die
        round_survivors = all_puuids - round_deaths
        
        # Calculate KAST for each player
        for puuid in all_puuids:
            has_k = puuid in round_killers
            has_a = puuid in round_assisters
            has_s = puuid in round_survivors
            has_t = puuid in traded_players
            
            if has_k or has_a or has_s or has_t:
                stats[puuid]["kast_rounds"] += 1
        
        # Record FK/FD
        if first_killer and first_victim:
            stats[first_killer]["first_kills"] += 1
            stats[first_victim]["first_deaths"] += 1
            
            killer_team = player_teams.get(first_killer, "")
            if killer_team == winning_team:
                stats[first_killer]["true_first_kills"] += 1
    
    return dict(stats)

def get_time_zone(round_time_ms: int, plant_time_ms) -> str:
    """Get time zone for kill."""
    if plant_time_ms and round_time_ms > plant_time_ms:
        return "PP"
    
    t = round_time_ms / 1000
    
    if t <= 20:
        return "1st"
    elif t <= 40:
        return "1.5th"
    elif t <= 60:
        return "2nd"
    else:
        return "Late"

def import_match(json_path: str):
    """Import match from JSON file."""
    print(f"\n=== Importing match from {json_path} ===\n")
    
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    match_info = data.get("matchInfo", {})
    match_id = match_info.get("matchId", "")
    
    if not match_id:
        print("Error: No match ID found in JSON")
        return
    
    print(f"Match ID: {match_id}")
    
    # Get session
    session = next(get_session())
    
    # Check if match exists
    existing = session.query(Match).filter_by(match_id=match_id).first()
    
    # Get map name
    map_id = match_info.get("mapId", "")
    map_name = get_map_name(map_id)
    print(f"Map: {map_name}")
    
    # Get scores from teams
    teams = data.get("teams", [])
    blue_score = 0
    red_score = 0
    for team in teams:
        if team.get("teamId") == "Blue":
            blue_score = team.get("roundsWon", 0)
        elif team.get("teamId") == "Red":
            red_score = team.get("roundsWon", 0)
    
    print(f"Score: Blue {blue_score} - {red_score} Red")
    
    # Determine result (from Blue team perspective)
    if blue_score > red_score:
        result = MatchResult.WIN
    elif blue_score < red_score:
        result = MatchResult.LOSE
    else:
        result = MatchResult.DRAW
    
    # Calculate detailed stats
    detailed_stats = calculate_detailed_stats(data)
    
    if existing:
        print(f"Match exists, updating...")
        match = existing
        match.map_name = map_name
        match.ally_score = blue_score
        match.enemy_score = red_score
        match.result = result
        match.game_length_millis = match_info.get("gameLengthMillis", 0)
        match.game_start_millis = match_info.get("gameStartMillis", 0)
        
        # Delete existing player stats
        session.query(PlayerMatchStats).filter_by(match_id=match_id).delete()
        session.query(Round).filter_by(match_id=match_id).delete()
        session.query(Kill).filter_by(match_id=match_id).delete()
    else:
        print(f"Creating new match...")
        match = Match(
            match_id=match_id,
            map_id=map_id,
            map_name=map_name,
            queue_id=match_info.get("queueID", ""),
            game_start_millis=match_info.get("gameStartMillis", 0),
            game_length_millis=match_info.get("gameLengthMillis", 0),
            result=result,
            ally_score=blue_score,
            enemy_score=red_score,
            completion_state="Completed",
            is_coach_view=True,
            category=MatchCategory.CUSTOM,
        )
        session.add(match)
    
    # Save players
    players = data.get("players", [])
    print(f"\nPlayers ({len(players)}):")
    
    for player in players:
        puuid = player.get("subject", "")
        game_name = player.get("gameName", "Unknown")
        tag_line = player.get("tagLine", "")
        team_id = player.get("teamId", "")
        agent_id = player.get("characterId", "")
        
        # Skip observers/neutral players (no agent)
        if team_id == "Neutral" or not agent_id:
            print(f"  [Skip] {game_name}#{tag_line} ({team_id}) - Observer/No agent")
            continue
        
        stats_data = player.get("stats") or {}
        kills = stats_data.get("kills", 0) or 0
        deaths = stats_data.get("deaths", 0) or 0
        assists = stats_data.get("assists", 0) or 0
        score = stats_data.get("score", 0) or 0
        rounds_played = stats_data.get("roundsPlayed", 0) or 0
        
        # Calculate damage
        round_damage = player.get("roundDamage") or []
        total_damage = sum(rd.get("damage", 0) for rd in round_damage) if round_damage else 0
        
        # Get detailed stats
        player_detailed = detailed_stats.get(puuid, {})
        
        print(f"  {game_name}#{tag_line} ({team_id}) - {get_agent_name(agent_id)}")
        print(f"    K/D/A: {kills}/{deaths}/{assists}, Score: {score}")
        print(f"    FK: {player_detailed.get('first_kills', 0)}, FD: {player_detailed.get('first_deaths', 0)}, TFK: {player_detailed.get('true_first_kills', 0)}")
        
        player_stats = PlayerMatchStats(
            id=f"{match_id}_{puuid}",
            match_id=match_id,
            puuid=puuid,
            player_name=game_name,
            tag_line=tag_line,
            agent_id=agent_id,
            agent_name=get_agent_name(agent_id),
            team_id=team_id,
            is_ally=(team_id == "Blue"),
            kills=kills,
            deaths=deaths,
            assists=assists,
            score=score,
            rounds_played=rounds_played,
            damage_dealt=total_damage,
            first_kills=player_detailed.get("first_kills", 0),
            first_deaths=player_detailed.get("first_deaths", 0),
            true_first_kills=player_detailed.get("true_first_kills", 0),
            headshots=player_detailed.get("headshots", 0),
            bodyshots=player_detailed.get("bodyshots", 0),
            legshots=player_detailed.get("legshots", 0),
            kast_rounds=player_detailed.get("kast_rounds", 0),
            time_based_kd=json.dumps(player_detailed.get("time_based_kd", {})),
        )
        session.add(player_stats)
    
    # Save rounds
    round_results = data.get("roundResults", [])
    print(f"\nRounds ({len(round_results)}):")
    
    for rr in round_results:
        round_num = rr.get("roundNum", 0)
        winning_team = rr.get("winningTeam", "")
        round_result_str = rr.get("roundResult", "")
        
        # Map win condition
        win_condition = None
        if "Eliminated" in round_result_str:
            win_condition = WinCondition.ELIMINATION
        elif "detonated" in round_result_str.lower():
            win_condition = WinCondition.DETONATE
        elif "defused" in round_result_str.lower():
            win_condition = WinCondition.DEFUSE
        elif "timer" in round_result_str.lower():
            win_condition = WinCondition.TIME
        
        # Determine result (Blue team perspective)
        result_val = "WIN" if winning_team == "Blue" else "LOSS"
        
        round_rec = Round(
            match_id=match_id,
            round_number=round_num,
            result=result_val,
            win_condition=win_condition,
        )
        session.add(round_rec)
        session.flush()  # Get the round.id
        
        # Save kills (with position data)
        for ps in rr.get("playerStats", []):
            for kill in ps.get("kills", []):
                victim_loc = kill.get("victimLocation", {}) or {}
                kill_rec = Kill(
                    match_id=match_id,
                    round_id=round_rec.id,
                    round_number=round_num,
                    game_time=kill.get("roundTime", 0),
                    killer_puuid=kill.get("killer", "") or "",
                    victim_puuid=kill.get("victim", "") or "",
                    victim_location_x=victim_loc.get("x", 0) or 0,
                    victim_location_y=victim_loc.get("y", 0) or 0,
                    weapon_id=kill.get("finishingDamage", {}).get("damageItem", ""),
                )
                session.add(kill_rec)
    
    session.commit()
    print(f"\n[OK] Match imported successfully!")
    print(f"   Players: 10 (excluding observer)")
    print(f"   Rounds: {len(round_results)}")

if __name__ == "__main__":
    json_file = sys.argv[1] if len(sys.argv) > 1 else "data/output/coached_match.json"
    import_match(json_file)

