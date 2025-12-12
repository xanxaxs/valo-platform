# -*- coding: utf-8 -*-
"""
Post-Match Data Retrieval Test
"""
import asyncio
import sys
import json
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.api.client import ValorantClient

async def main():
    print("=" * 60)
    print("Post-Match Data Retrieval Test")
    print("=" * 60)
    
    client = ValorantClient()
    
    print("\n[1] Connecting...")
    if not await client.connect():
        print("[FAIL] Connection failed")
        return
    print(f"[OK] Connected: {client.puuid[:8]}...")
    
    # Check game state
    print("\n[2] Game state...")
    state = await client.get_game_state()
    print(f"   State: {state.value}")
    
    # Get own match history
    print("\n[3] Getting own match history...")
    history = await client.get_match_history(client.puuid, count=5)
    
    if not history or not history.get("History"):
        print("[FAIL] No match history")
        await client.disconnect()
        return
    
    matches = history["History"]
    print(f"[OK] Got {len(matches)} matches")
    
    # Show recent matches
    print("\n[4] Recent matches:")
    for i, m in enumerate(matches[:3]):
        match_id = m.get("MatchID", "?")
        game_start = m.get("GameStartTime", 0)
        queue = m.get("QueueID", "?")
        print(f"   {i+1}. {match_id[:30]}...")
        print(f"      Queue: {queue}, Start: {game_start}")
    
    # Get details for the most recent match
    latest_match_id = matches[0].get("MatchID")
    print(f"\n[5] Getting details for latest match: {latest_match_id[:20]}...")
    
    details = await client.get_match_details(latest_match_id)
    
    if not details:
        print("[FAIL] No match details")
        await client.disconnect()
        return
    
    print("[OK] Got match details!")
    
    # Parse and display
    print("\n[6] Match Summary:")
    match_info = details.get("matchInfo", {})
    print(f"   Map: {match_info.get('mapId', '?')}")
    print(f"   Mode: {match_info.get('gameMode', '?')}")
    print(f"   Duration: {match_info.get('gameLengthMillis', 0) // 1000 // 60} min")
    
    # Teams
    print("\n[7] Teams:")
    teams = details.get("teams", [])
    for team in teams:
        team_id = team.get("teamId", "?")
        won = team.get("won", False)
        rounds_won = team.get("roundsWon", 0)
        print(f"   {team_id}: {rounds_won} rounds {'(Winner)' if won else ''}")
    
    # Players
    print("\n[8] Players:")
    players = details.get("players", [])
    for p in players:
        name = p.get("gameName", "Unknown")
        tag = p.get("tagLine", "")
        team = p.get("teamId", "?")
        agent = p.get("characterId", "?")[:8]
        stats = p.get("stats", {})
        k = stats.get("kills", 0)
        d = stats.get("deaths", 0)
        a = stats.get("assists", 0)
        score = stats.get("score", 0)
        print(f"   [{team}] {name}#{tag}: {k}/{d}/{a} (Score: {score})")
    
    # Rounds
    print("\n[9] Round Results:")
    rounds = details.get("roundResults", [])
    print(f"   Total rounds: {len(rounds)}")
    for r in rounds[:5]:
        round_num = r.get("roundNum", 0)
        winner = r.get("winningTeam", "?")
        result = r.get("roundResult", "?")
        print(f"   Round {round_num}: {winner} - {result}")
    if len(rounds) > 5:
        print(f"   ... and {len(rounds) - 5} more rounds")
    
    # Save full details to file for inspection
    output_path = Path(__file__).parent.parent / "data" / "output" / "latest_match.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(details, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f"\n[10] Full details saved to: {output_path}")
    
    print("\n" + "=" * 60)
    print("Test complete!")
    print("=" * 60)
    
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())

