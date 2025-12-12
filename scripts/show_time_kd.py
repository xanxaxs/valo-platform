# -*- coding: utf-8 -*-
"""Show time-based K/D stats"""
import json
import sys
from pathlib import Path
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8')

data = json.load(open(Path(__file__).parent.parent / "data/output/coached_match.json", encoding='utf-8'))

# Agent lookup
AGENTS = {
    "5f8d3a7f-467b-97f3-062c-13acf203c006": "Breach",
    "f94c3b30-42be-e959-889c-5aa313dba261": "Raze",
    "6f2a04ca-43e0-be17-7f36-b3908627744d": "Skye",
    "117ed9e3-49f3-6512-3ccf-0cada7e3823b": "Cypher",
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
    "601dbbe7-43ce-be57-2a40-4abd24953621": "KAY/O",
    "1dbf2edd-4729-0984-3115-daa5eed44993": "Clove",
    "e370fa57-4757-3604-3648-499e1f642d3f": "Gekko",
    "cc8b64c8-4b25-4ff9-6e7f-37b4da43d235": "Deadlock",
    "dade69b4-4f5a-8528-247b-219e5a1facd6": "Fade",
    "22697a3d-45bf-8dd7-4fec-84a9e28c69d7": "Chamber",
    "95b78ed7-4637-86d9-7e41-71ba8c293152": "Harbor",
    "bb2a4828-46eb-8cd1-e765-15848195d751": "Neon",
    "0e38b510-41a8-5780-5e8f-568b2a4f2d6c": "Iso",
    "efba5359-4016-a1e5-7626-b1ae76895940": "Vyse",
    "df1cb487-4902-002e-5c17-d28e83e78588": "Waylay",
}

# Build player info
players = data.get("players", [])
player_info = {}
for p in players:
    puuid = p.get("subject", "")
    player_info[puuid] = {
        "name": p.get("gameName", "?"),
        "team": p.get("teamId", "?"),
        "agent": AGENTS.get(p.get("characterId", ""), "?"),
    }

# Time zones (based on round time elapsed in ms)
# Round is 100 seconds (1:40)
# 1st:    0-20s  (1:40-1:20 remaining) - Opening
# 1.5th: 20-40s  (1:20-1:00 remaining) - Prepare  
# 2nd:   40-60s  (1:00-0:40 remaining) - Mid
# Late:  60-100s (0:40-0:00 remaining) - Late
# PP:    After plant (need to check plant event)

def get_time_zone(round_time_ms, has_plant=False, plant_time_ms=0):
    """Get time zone for a kill based on round time."""
    t = round_time_ms / 1000  # Convert to seconds
    
    # Check if this is post-plant
    if has_plant and round_time_ms > plant_time_ms:
        return "PP"
    
    if t <= 20:
        return "1st"
    elif t <= 40:
        return "1.5th"
    elif t <= 60:
        return "2nd"
    else:
        return "Late"

# Process rounds
time_kd = defaultdict(lambda: {
    "1st": {"k": 0, "d": 0},
    "1.5th": {"k": 0, "d": 0},
    "2nd": {"k": 0, "d": 0},
    "Late": {"k": 0, "d": 0},
    "PP": {"k": 0, "d": 0},
})

rounds = data.get("roundResults", [])

for r in rounds:
    # Check for plant event
    plant_time = None
    plant_events = r.get("plantEvents", {})
    if plant_events:
        plant_time = plant_events.get("plantRoundTime", None)
    
    # Also check bombPlanter
    if not plant_time and r.get("bombPlanter"):
        # Estimate plant time from round result
        plant_time = 45000  # Default estimate: 45 seconds into round
    
    has_plant = plant_time is not None
    
    # Process kills
    for ps in r.get("playerStats", []):
        for kill in ps.get("kills", []):
            round_time = kill.get("roundTime", 0)
            killer = kill.get("killer", "")
            victim = kill.get("victim", "")
            
            zone = get_time_zone(round_time, has_plant, plant_time or 0)
            
            if killer in player_info:
                time_kd[killer][zone]["k"] += 1
            if victim in player_info:
                time_kd[victim][zone]["d"] += 1

print("=" * 100)
print("TIME-BASED K/D ANALYSIS")
print("=" * 100)
print("""
Time Zones:
  1st:   0-20s  (1:40-1:20 remaining) - Opening/Entry
  1.5th: 20-40s (1:20-1:00 remaining) - Prepare/Setup
  2nd:   40-60s (1:00-0:40 remaining) - Mid-round
  Late:  60s+   (0:40-0:00 remaining) - Late round
  PP:    Post-plant
""")

# Sort by team
red_players = [(puuid, info) for puuid, info in player_info.items() if info["team"] == "Red"]
blue_players = [(puuid, info) for puuid, info in player_info.items() if info["team"] == "Blue"]

def print_time_kd_table(team_name, team_players):
    print(f"\n{'=' * 100}")
    print(f"{team_name}")
    print("=" * 100)
    print(f"{'Name':<20} {'Agent':<8} | {'1st':^10} | {'1.5th':^10} | {'2nd':^10} | {'Late':^10} | {'PP':^10} |")
    print("-" * 100)
    
    for puuid, info in team_players:
        name = info["name"][:19]
        agent = info["agent"]
        kd = time_kd[puuid]
        
        zones = []
        for zone in ["1st", "1.5th", "2nd", "Late", "PP"]:
            k = kd[zone]["k"]
            d = kd[zone]["d"]
            zones.append(f"{k}K/{d}D")
        
        print(f"{name:<20} {agent:<8} | {zones[0]:^10} | {zones[1]:^10} | {zones[2]:^10} | {zones[3]:^10} | {zones[4]:^10} |")

print_time_kd_table("RED TEAM", red_players)
print_time_kd_table("BLUE TEAM", blue_players)

# Summary - who is strong in each time zone
print(f"\n{'=' * 100}")
print("TIME ZONE SPECIALISTS")
print("=" * 100)

for zone in ["1st", "1.5th", "2nd", "Late", "PP"]:
    print(f"\n{zone} Time Zone:")
    
    # Get all players with activity in this zone
    zone_stats = []
    for puuid, kd in time_kd.items():
        k = kd[zone]["k"]
        d = kd[zone]["d"]
        if k > 0 or d > 0:
            info = player_info.get(puuid, {})
            kd_ratio = k / d if d > 0 else float(k) if k > 0 else 0
            zone_stats.append({
                "name": info.get("name", "?"),
                "agent": info.get("agent", "?"),
                "k": k,
                "d": d,
                "kd": kd_ratio,
            })
    
    # Sort by K/D ratio
    zone_stats.sort(key=lambda x: x["kd"], reverse=True)
    
    # Top performers
    top = zone_stats[:3]
    for p in top:
        kd_str = f"{p['kd']:.2f}" if isinstance(p['kd'], float) else str(p['kd'])
        print(f"  {p['name']} ({p['agent']}): {p['k']}K/{p['d']}D (K/D: {kd_str})")

# Overall early vs late comparison
print(f"\n{'=' * 100}")
print("EARLY vs LATE PERFORMANCE")
print("=" * 100)

print(f"\n{'Name':<20} {'Agent':<8} | {'Early (1st+1.5th)':^15} | {'Late (2nd+Late+PP)':^15} | {'Type':<12}")
print("-" * 80)

for puuid, info in list(red_players) + list(blue_players):
    name = info["name"][:19]
    agent = info["agent"]
    kd = time_kd[puuid]
    
    early_k = kd["1st"]["k"] + kd["1.5th"]["k"]
    early_d = kd["1st"]["d"] + kd["1.5th"]["d"]
    late_k = kd["2nd"]["k"] + kd["Late"]["k"] + kd["PP"]["k"]
    late_d = kd["2nd"]["d"] + kd["Late"]["d"] + kd["PP"]["d"]
    
    early_str = f"{early_k}K/{early_d}D"
    late_str = f"{late_k}K/{late_d}D"
    
    # Determine player type
    early_kd = early_k / early_d if early_d > 0 else float(early_k)
    late_kd = late_k / late_d if late_d > 0 else float(late_k)
    
    if early_kd > late_kd + 0.3:
        player_type = "Early Fragger"
    elif late_kd > early_kd + 0.3:
        player_type = "Clutch Player"
    else:
        player_type = "Consistent"
    
    print(f"{name:<20} {agent:<8} | {early_str:^15} | {late_str:^15} | {player_type:<12}")

print("\n" + "=" * 100)

