# -*- coding: utf-8 -*-
"""Show detailed stats from coached match including FK/FD/TrueFK/HS%"""
import json
import sys
from pathlib import Path
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8')

data = json.load(open(Path(__file__).parent.parent / "data/output/coached_match.json", encoding='utf-8'))

# Agent name lookup (all agents as of 2025)
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

# Build player info lookup
players = data.get("players", [])
player_info = {}
for p in players:
    puuid = p.get("subject", "")
    player_info[puuid] = {
        "name": p.get("gameName", "?"),
        "tag": p.get("tagLine", ""),
        "team": p.get("teamId", "?"),
        "agent": AGENTS.get(p.get("characterId", ""), "?"),
        "stats": p.get("stats", {}),
        "roundDamage": p.get("roundDamage", []),
    }

# Calculate FK, FD, True FK, and HS% from round data
rounds = data.get("roundResults", [])
fk_counts = defaultdict(int)  # First Kills
fd_counts = defaultdict(int)  # First Deaths
true_fk_counts = defaultdict(int)  # First Kill + Round Win
hs_stats = defaultdict(lambda: {"headshots": 0, "bodyshots": 0, "legshots": 0})

for r in rounds:
    winning_team = r.get("winningTeam", "")
    player_stats = r.get("playerStats", [])
    
    # Find first kill in this round
    first_kill_time = float('inf')
    first_killer = None
    first_victim = None
    
    for ps in player_stats:
        puuid = ps.get("subject", "")
        
        # Collect headshot stats
        for dmg in ps.get("damage", []):
            hs_stats[puuid]["headshots"] += dmg.get("headshots", 0)
            hs_stats[puuid]["bodyshots"] += dmg.get("bodyshots", 0)
            hs_stats[puuid]["legshots"] += dmg.get("legshots", 0)
        
        # Find first kill
        for kill in ps.get("kills", []):
            kill_time = kill.get("roundTime", float('inf'))
            if kill_time < first_kill_time:
                first_kill_time = kill_time
                first_killer = kill.get("killer", "")
                first_victim = kill.get("victim", "")
    
    # Record FK and FD
    if first_killer and first_victim:
        fk_counts[first_killer] += 1
        fd_counts[first_victim] += 1
        
        # Check if it's a True FK (killer's team won)
        killer_team = player_info.get(first_killer, {}).get("team", "")
        if killer_team == winning_team:
            true_fk_counts[first_killer] += 1

print("=" * 90)
print("DETAILED MATCH STATISTICS")
print("=" * 90)

# Match Info
match_info = data.get("matchInfo", {})
print(f"\nMap: Abyss | Duration: {match_info.get('gameLengthMillis', 0) // 1000 // 60} min | Rounds: {len(rounds)}")

# Teams
teams = data.get("teams", [])
for t in teams:
    winner = "WINNER" if t.get("won") else ""
    print(f"{t.get('teamId')}: {t.get('roundsWon')} rounds {winner}")

# Players
def get_player_stats(puuid):
    info = player_info.get(puuid, {})
    stats = info.get("stats", {})
    
    k = stats.get("kills", 0)
    d = stats.get("deaths", 0)
    a = stats.get("assists", 0)
    score = stats.get("score", 0)
    rounds_played = stats.get("roundsPlayed", 24)
    
    # ACS
    acs = round(score / rounds_played, 1) if rounds_played > 0 else 0
    
    # K/D
    kd = round(k / d, 2) if d > 0 else float(k)
    
    # ADR from roundDamage
    round_damage = info.get("roundDamage", [])
    total_dmg = sum(rd.get("damage", 0) for rd in round_damage)
    adr = round(total_dmg / rounds_played, 1) if rounds_played > 0 else 0
    
    # FK/FD/TrueFK
    fk = fk_counts.get(puuid, 0)
    fd = fd_counts.get(puuid, 0)
    true_fk = true_fk_counts.get(puuid, 0)
    
    # HS%
    hs = hs_stats[puuid]
    total_shots = hs["headshots"] + hs["bodyshots"] + hs["legshots"]
    hs_pct = round(hs["headshots"] / total_shots * 100, 1) if total_shots > 0 else 0
    
    return {
        "name": info.get("name", "?"),
        "tag": info.get("tag", ""),
        "team": info.get("team", "?"),
        "agent": info.get("agent", "?"),
        "k": k, "d": d, "a": a,
        "kd": kd, "acs": acs, "adr": adr,
        "fk": fk, "fd": fd, "true_fk": true_fk,
        "hs_pct": hs_pct,
        "score": score, "damage": total_dmg,
    }

# Sort players by team and score
red_team = sorted([get_player_stats(p.get("subject")) for p in players if p.get("teamId") == "Red"],
                  key=lambda x: x["score"], reverse=True)
blue_team = sorted([get_player_stats(p.get("subject")) for p in players if p.get("teamId") == "Blue"],
                   key=lambda x: x["score"], reverse=True)

def print_team(team_name, team_data, is_winner=False):
    print(f"\n{'=' * 90}")
    print(f"{team_name} {'(WINNER)' if is_winner else ''}")
    print("=" * 90)
    print(f"{'Name':<25} {'Agent':<8} {'K/D/A':<10} {'K/D':<6} {'ACS':<6} {'ADR':<6} {'FK':<3} {'FD':<3} {'TFK':<3} {'HS%':<6}")
    print("-" * 90)
    
    for p in team_data:
        name = f"{p['name']}"[:24]
        kda = f"{p['k']}/{p['d']}/{p['a']}"
        print(f"{name:<25} {p['agent']:<8} {kda:<10} {p['kd']:<6} {p['acs']:<6} {p['adr']:<6} {p['fk']:<3} {p['fd']:<3} {p['true_fk']:<3} {p['hs_pct']:<6}")

print_team("RED TEAM", red_team, is_winner=teams[0].get("won") if teams and teams[0].get("teamId") == "Red" else False)
print_team("BLUE TEAM", blue_team, is_winner=teams[1].get("won") if len(teams) > 1 and teams[1].get("teamId") == "Blue" else (teams[0].get("won") if teams and teams[0].get("teamId") == "Blue" else False))

# Summary stats
print(f"\n{'=' * 90}")
print("FIRST KILL ANALYSIS")
print("=" * 90)

# Sort by FK
all_players = red_team + blue_team
fk_leaders = sorted(all_players, key=lambda x: x["fk"], reverse=True)[:5]
print("\nTop FK (First Kills):")
for p in fk_leaders:
    if p["fk"] > 0:
        tfk_rate = round(p["true_fk"] / p["fk"] * 100, 1) if p["fk"] > 0 else 0
        print(f"  {p['name']} ({p['agent']}): {p['fk']} FK, {p['true_fk']} TrueFK ({tfk_rate}% conversion)")

# Sort by FD
fd_leaders = sorted(all_players, key=lambda x: x["fd"], reverse=True)[:5]
print("\nTop FD (First Deaths):")
for p in fd_leaders:
    if p["fd"] > 0:
        print(f"  {p['name']} ({p['agent']}): {p['fd']} FD")

# FK Differential
print("\nFK Differential (FK - FD):")
fk_diff = sorted(all_players, key=lambda x: x["fk"] - x["fd"], reverse=True)
for p in fk_diff[:3]:
    diff = p["fk"] - p["fd"]
    print(f"  {p['name']}: +{diff}" if diff >= 0 else f"  {p['name']}: {diff}")
print("  ...")
for p in fk_diff[-3:]:
    diff = p["fk"] - p["fd"]
    print(f"  {p['name']}: +{diff}" if diff >= 0 else f"  {p['name']}: {diff}")

# Headshot leaders
print("\nTop HS% (Headshot Rate):")
hs_leaders = sorted(all_players, key=lambda x: x["hs_pct"], reverse=True)[:5]
for p in hs_leaders:
    print(f"  {p['name']} ({p['agent']}): {p['hs_pct']}%")

# Round summary
print(f"\n{'=' * 90}")
print("ROUND SUMMARY")
print("=" * 90)

red_wins = sum(1 for r in rounds if r.get("winningTeam") == "Red")
blue_wins = sum(1 for r in rounds if r.get("winningTeam") == "Blue")
print(f"Total: {len(rounds)} rounds | Red: {red_wins} | Blue: {blue_wins}")

conditions = {}
for r in rounds:
    cond = r.get("roundResult", "Unknown")
    conditions[cond] = conditions.get(cond, 0) + 1

print("\nWin Conditions:")
for cond, count in sorted(conditions.items(), key=lambda x: -x[1]):
    print(f"  {cond}: {count}")

print("\n" + "=" * 90)
