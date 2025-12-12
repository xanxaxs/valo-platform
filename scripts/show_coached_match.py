# -*- coding: utf-8 -*-
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

data = json.load(open(Path(__file__).parent.parent / "data/output/coached_match.json", encoding='utf-8'))

print("=" * 60)
print("COACHED MATCH DETAILS")
print("=" * 60)

match_info = data.get("matchInfo", {})
print(f"\nMap: Abyss (Infinity)")
print(f"Duration: {match_info.get('gameLengthMillis', 0) // 1000 // 60} minutes")

print("\n--- Teams ---")
teams = data.get("teams", [])
for t in teams:
    winner = "(WINNER)" if t.get("won") else ""
    print(f"  {t.get('teamId')}: {t.get('roundsWon')} rounds {winner}")

print("\n--- Players ---")
players = data.get("players", [])

# Sort by team
red_team = [p for p in players if p.get("teamId") == "Red"]
blue_team = [p for p in players if p.get("teamId") == "Blue"]

print("\n[RED TEAM]")
for p in red_team:
    name = p.get("gameName", "?")
    tag = p.get("tagLine", "")
    stats = p.get("stats", {})
    k, d, a = stats.get("kills", 0), stats.get("deaths", 0), stats.get("assists", 0)
    score = stats.get("score", 0)
    print(f"  {name}#{tag}: {k}/{d}/{a} (Score: {score})")

print("\n[BLUE TEAM]")
for p in blue_team:
    name = p.get("gameName", "?")
    tag = p.get("tagLine", "")
    stats = p.get("stats", {})
    k, d, a = stats.get("kills", 0), stats.get("deaths", 0), stats.get("assists", 0)
    score = stats.get("score", 0)
    print(f"  {name}#{tag}: {k}/{d}/{a} (Score: {score})")

print("\n--- Round Results ---")
rounds = data.get("roundResults", [])
print(f"Total: {len(rounds)} rounds")
for r in rounds:
    rnum = r.get("roundNum", 0)
    winner = r.get("winningTeam", "?")
    result = r.get("roundResult", "?")
    print(f"  Round {rnum+1}: {winner} - {result}")

print("\n" + "=" * 60)
print("Data retrieval SUCCESS!")
print("=" * 60)

