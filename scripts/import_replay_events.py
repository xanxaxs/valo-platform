"""
Import replay events (kills, plants, defuses) from coached_match.json.
"""
import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db.database import get_session, init_db
from src.db.models import Match, MatchEventSnapshot, EventType

# Player name and agent mapping
PLAYER_NAMES = {}
PLAYER_AGENTS = {}  # puuid -> {"agent_id": ..., "agent_name": ...}
PLAYER_TEAMS = {}  # puuid -> team_id

# Agent ID to name mapping (same as import_match_json.py)
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
    "df1cb487-4902-002e-5c17-d28e83e78588": "Waylay",
}


def load_player_names(data):
    """Load player names, agents, and teams from match data."""
    global PLAYER_NAMES, PLAYER_AGENTS, PLAYER_TEAMS
    for player in data.get("players", []):
        puuid = player.get("subject")
        name = player.get("gameName", "Unknown")
        agent_id = player.get("characterId", "")
        team_id = player.get("teamId", "")
        
        PLAYER_NAMES[puuid] = name
        PLAYER_TEAMS[puuid] = team_id
        PLAYER_AGENTS[puuid] = {
            "agent_id": agent_id,
            "agent_name": AGENT_NAMES.get(agent_id, "Unknown"),
        }


def get_player_name(puuid):
    """Get player name by PUUID."""
    return PLAYER_NAMES.get(puuid, puuid[:8] if puuid else "Unknown")


def get_player_agent(puuid):
    """Get player agent info by PUUID."""
    return PLAYER_AGENTS.get(puuid, {"agent_id": "", "agent_name": "Unknown"})


def get_player_team(puuid):
    """Get player team by PUUID."""
    return PLAYER_TEAMS.get(puuid, "")


def format_round_time(ms):
    """Format round time from milliseconds to MM:SS format."""
    seconds = ms // 1000
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes}:{secs:02d}"


def import_events():
    """Import kill events from JSON."""
    init_db()
    session = next(get_session())
    
    # Load JSON
    json_path = Path("data/output/coached_match.json")
    if not json_path.exists():
        print(f"File not found: {json_path}")
        return
    
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # Load player names
    load_player_names(data)
    
    # Get match ID
    match_id = data.get("matchInfo", {}).get("matchId")
    if not match_id:
        print("No match ID found in JSON")
        return
    
    # Check if match exists
    match = session.query(Match).filter(Match.match_id == match_id).first()
    if not match:
        print(f"Match {match_id} not found in database")
        return
    
    print(f"Importing events for match: {match_id}")
    print(f"Map: {match.map_name}")
    
    # Delete existing events for this match
    deleted = session.query(MatchEventSnapshot).filter(
        MatchEventSnapshot.match_id == match_id
    ).delete()
    print(f"Deleted {deleted} existing events")
    
    events_added = 0
    
    # Process rounds
    for round_data in data.get("roundResults", []):
        round_num = round_data.get("roundNum", 0)
        
        # Process kills from all players
        for player_stats in round_data.get("playerStats", []):
            kills = player_stats.get("kills", [])
            
            for kill in kills:
                killer_puuid = kill.get("killer")
                victim_puuid = kill.get("victim")
                
                # Build event data
                event_data = {
                    "killer": killer_puuid,
                    "killer_name": get_player_name(killer_puuid),
                    "victim": victim_puuid,
                    "victim_name": get_player_name(victim_puuid),
                    "assistants": kill.get("assistants", []),
                    "weapon": kill.get("finishingDamage", {}).get("damageItem"),
                    "damage_type": kill.get("finishingDamage", {}).get("damageType"),
                    "victim_location": kill.get("victimLocation"),
                }
                
                # Build player positions
                player_positions = []
                for loc in kill.get("playerLocations", []):
                    puuid = loc.get("subject")
                    agent_info = get_player_agent(puuid)
                    player_positions.append({
                        "puuid": puuid,
                        "name": get_player_name(puuid),
                        "x": loc.get("location", {}).get("x"),
                        "y": loc.get("location", {}).get("y"),
                        "view_radians": loc.get("viewRadians"),
                        "agent_id": agent_info["agent_id"],
                        "agent_name": agent_info["agent_name"],
                        "team_id": get_player_team(puuid),
                    })
                
                # Create event snapshot
                event = MatchEventSnapshot(
                    match_id=match_id,
                    round_number=round_num,
                    event_type=EventType.KILL,
                    game_time=kill.get("gameTime", 0),
                    round_time=kill.get("roundTime", 0),
                    event_data=event_data,
                    player_positions=player_positions,
                )
                session.add(event)
                events_added += 1
        
        # Process plant event
        if round_data.get("bombPlanter"):
            plant_time = round_data.get("plantRoundTime", 0)
            planter_puuid = round_data.get("bombPlanter")
            
            event_data = {
                "planter": planter_puuid,
                "planter_name": get_player_name(planter_puuid),
                "site": round_data.get("plantSite"),
                "plant_location": round_data.get("plantLocation"),
            }
            
            player_positions = []
            for loc in round_data.get("plantPlayerLocations", []):
                puuid = loc.get("subject")
                agent_info = get_player_agent(puuid)
                player_positions.append({
                    "puuid": puuid,
                    "name": get_player_name(puuid),
                    "x": loc.get("location", {}).get("x"),
                    "y": loc.get("location", {}).get("y"),
                    "view_radians": loc.get("viewRadians"),
                    "agent_id": agent_info["agent_id"],
                    "agent_name": agent_info["agent_name"],
                    "team_id": get_player_team(puuid),
                })
            
            event = MatchEventSnapshot(
                match_id=match_id,
                round_number=round_num,
                event_type=EventType.PLANT,
                game_time=0,  # Not available
                round_time=plant_time,
                event_data=event_data,
                player_positions=player_positions,
            )
            session.add(event)
            events_added += 1
        
        # Process defuse event
        if round_data.get("defuseRoundTime"):
            defuse_time = round_data.get("defuseRoundTime", 0)
            defuse_loc = round_data.get("defuseLocation")
            
            event_data = {
                "defuse_location": defuse_loc,
            }
            
            player_positions = []
            for loc in round_data.get("defusePlayerLocations", []):
                puuid = loc.get("subject")
                agent_info = get_player_agent(puuid)
                player_positions.append({
                    "puuid": puuid,
                    "name": get_player_name(puuid),
                    "x": loc.get("location", {}).get("x"),
                    "y": loc.get("location", {}).get("y"),
                    "view_radians": loc.get("viewRadians"),
                    "agent_id": agent_info["agent_id"],
                    "agent_name": agent_info["agent_name"],
                    "team_id": get_player_team(puuid),
                })
            
            event = MatchEventSnapshot(
                match_id=match_id,
                round_number=round_num,
                event_type=EventType.DEFUSE,
                game_time=0,
                round_time=defuse_time,
                event_data=event_data,
                player_positions=player_positions,
            )
            session.add(event)
            events_added += 1
    
    session.commit()
    print(f"Added {events_added} events successfully!")
    
    # Verify
    total = session.query(MatchEventSnapshot).filter(
        MatchEventSnapshot.match_id == match_id
    ).count()
    print(f"Total events in database: {total}")


if __name__ == "__main__":
    import_events()

