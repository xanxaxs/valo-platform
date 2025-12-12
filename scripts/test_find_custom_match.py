# -*- coding: utf-8 -*-
"""
Find Custom Match from Other Players' History
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
    print("Find Custom Match from Other Players")
    print("=" * 60)
    
    client = ValorantClient()
    
    print("\n[1] Connecting...")
    if not await client.connect():
        print("[FAIL] Connection failed")
        return
    print(f"[OK] Connected: {client.puuid[:8]}...")
    
    # Get all presences to find players
    print("\n[2] Getting player list from presences...")
    presences = await client._request("GET", "/chat/v4/presences")
    
    if not presences or not presences.get("presences"):
        print("[FAIL] No presences")
        await client.disconnect()
        return
    
    other_puuids = []
    for p in presences["presences"]:
        puuid = p.get("puuid")
        if puuid and puuid != client.puuid:
            other_puuids.append(puuid)
    
    print(f"[OK] Found {len(other_puuids)} other players")
    
    # Search for custom match in their histories
    print("\n[3] Searching for custom match in player histories...")
    
    custom_match_id = None
    checked = 0
    
    for puuid in other_puuids[:20]:  # Check up to 20 players
        checked += 1
        history = await client.get_match_history(puuid, count=5)
        
        if not history or not history.get("History"):
            continue
        
        for match in history["History"]:
            queue = match.get("QueueID", "")
            match_id = match.get("MatchID", "")
            
            # Custom games have empty or special queue ID
            if queue == "" or queue == "custom" or "custom" in queue.lower():
                print(f"\n   [FOUND] Custom match from player {puuid[:8]}...")
                print(f"   Match ID: {match_id}")
                print(f"   Queue: '{queue}'")
                custom_match_id = match_id
                break
        
        if custom_match_id:
            break
        
        await asyncio.sleep(0.3)  # Rate limiting
    
    print(f"\n   Checked {checked} players")
    
    if not custom_match_id:
        print("\n[4] No custom match found. Showing all recent matches from first player...")
        
        # Show what we found
        for puuid in other_puuids[:3]:
            history = await client.get_match_history(puuid, count=5)
            if history and history.get("History"):
                print(f"\n   Player {puuid[:8]}...")
                for m in history["History"][:3]:
                    print(f"      - Queue: {m.get('QueueID', '?')}, ID: {m.get('MatchID', '?')[:20]}...")
                break
    else:
        # Get details for the custom match
        print(f"\n[4] Getting custom match details...")
        details = await client.get_match_details(custom_match_id)
        
        if details:
            print("[OK] Got custom match details!")
            
            match_info = details.get("matchInfo", {})
            print(f"\n   Map: {match_info.get('mapId', '?')}")
            print(f"   Mode: {match_info.get('gameMode', '?')}")
            print(f"   Queue: {match_info.get('queueId', '?')}")
            print(f"   Is Custom: {match_info.get('isMatchSampled', '?')}")
            
            teams = details.get("teams", [])
            for team in teams:
                print(f"   {team.get('teamId', '?')}: {team.get('roundsWon', 0)} rounds")
            
            players = details.get("players", [])
            print(f"\n   Players ({len(players)}):")
            for p in players[:5]:
                name = p.get("gameName", "?")
                stats = p.get("stats", {})
                k, d, a = stats.get("kills", 0), stats.get("deaths", 0), stats.get("assists", 0)
                print(f"      {name}: {k}/{d}/{a}")
            
            # Save to file
            output_path = Path(__file__).parent.parent / "data" / "output" / "custom_match.json"
            output_path.write_text(json.dumps(details, indent=2, ensure_ascii=False), encoding='utf-8')
            print(f"\n   Saved to: {output_path}")
        else:
            print("[FAIL] Could not get match details")
    
    print("\n" + "=" * 60)
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())

