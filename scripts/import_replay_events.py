"""
Import replay events (kills, plants, defuses) from coached_match.json.
"""
import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db.database import get_session, init_db
from src.db.models import Match, MatchEventSnapshot, EventType

# Player name mapping
PLAYER_NAMES = {}


def load_player_names(data):
    """Load player names from match data."""
    global PLAYER_NAMES
    for player in data.get("players", []):
        puuid = player.get("subject")
        name = player.get("gameName", "Unknown")
        PLAYER_NAMES[puuid] = name


def get_player_name(puuid):
    """Get player name by PUUID."""
    return PLAYER_NAMES.get(puuid, puuid[:8] if puuid else "Unknown")


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
                    player_positions.append({
                        "puuid": loc.get("subject"),
                        "name": get_player_name(loc.get("subject")),
                        "x": loc.get("location", {}).get("x"),
                        "y": loc.get("location", {}).get("y"),
                        "view_radians": loc.get("viewRadians"),
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
                player_positions.append({
                    "puuid": loc.get("subject"),
                    "name": get_player_name(loc.get("subject")),
                    "x": loc.get("location", {}).get("x"),
                    "y": loc.get("location", {}).get("y"),
                    "view_radians": loc.get("viewRadians"),
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
                player_positions.append({
                    "puuid": loc.get("subject"),
                    "name": get_player_name(loc.get("subject")),
                    "x": loc.get("location", {}).get("x"),
                    "y": loc.get("location", {}).get("y"),
                    "view_radians": loc.get("viewRadians"),
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

