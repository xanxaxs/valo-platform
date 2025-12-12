# -*- coding: utf-8 -*-
"""
Find the Abyss match we were coaching
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
    print("Find Abyss Custom Match")
    print("=" * 60)
    
    client = ValorantClient()
    
    print("\n[1] Connecting...")
    if not await client.connect():
        print("[FAIL] Connection failed")
        return
    print(f"[OK] Connected: {client.puuid[:8]}...")
    
    # Get presences
    presences = await client._request("GET", "/chat/v4/presences")
    other_puuids = []
    for p in presences.get("presences", []):
        puuid = p.get("puuid")
        if puuid and puuid != client.puuid:
            other_puuids.append(puuid)
    
    print(f"[OK] Found {len(other_puuids)} players")
    
    # Search for Abyss/Infinity map match
    print("\n[2] Searching for Abyss map in recent matches...")
    
    found_matches = []
    checked = 0
    
    for puuid in other_puuids[:30]:
        checked += 1
        history = await client.get_match_history(puuid, count=10)
        
        if not history or not history.get("History"):
            continue
        
        for match in history["History"]:
            match_id = match.get("MatchID", "")
            
            # Skip if already found
            if match_id in [m["id"] for m in found_matches]:
                continue
            
            # Get match details to check map
            details = await client.get_match_details(match_id)
            if not details:
                continue
            
            match_info = details.get("matchInfo", {})
            map_id = match_info.get("mapId", "")
            queue_id = match_info.get("queueID", "")
            
            # Check if it's Abyss/Infinity
            if "infinity" in map_id.lower() or "abyss" in map_id.lower():
                teams = details.get("teams", [])
                score = f"{teams[0].get('roundsWon', 0)}-{teams[1].get('roundsWon', 0)}" if len(teams) >= 2 else "?"
                
                found_matches.append({
                    "id": match_id,
                    "map": map_id,
                    "queue": queue_id,
                    "score": score,
                    "details": details,
                })
                
                print(f"\n   [FOUND] Abyss match!")
                print(f"   Match ID: {match_id}")
                print(f"   Queue: '{queue_id}'")
                print(f"   Score: {score}")
                
                # Show players
                players = details.get("players", [])
                print(f"   Players ({len(players)}):")
                for p in players[:5]:
                    name = p.get("gameName", "?")
                    team = p.get("teamId", "?")
                    stats = p.get("stats", {})
                    k, d, a = stats.get("kills", 0), stats.get("deaths", 0), stats.get("assists", 0)
                    print(f"      [{team}] {name}: {k}/{d}/{a}")
                if len(players) > 5:
                    print(f"      ... and {len(players) - 5} more")
                
                # Save it
                output_path = Path(__file__).parent.parent / "data" / "output" / f"abyss_match_{len(found_matches)}.json"
                output_path.write_text(json.dumps(details, indent=2, ensure_ascii=False), encoding='utf-8')
                print(f"   Saved to: {output_path}")
        
        if found_matches:
            break
        
        await asyncio.sleep(0.3)
    
    print(f"\n   Checked {checked} players")
    
    if not found_matches:
        print("\n[3] No Abyss match found. Showing all queue types found:")
        
        # Collect all queue types
        queues_seen = set()
        for puuid in other_puuids[:5]:
            history = await client.get_match_history(puuid, count=5)
            if history and history.get("History"):
                for m in history["History"]:
                    queues_seen.add(m.get("QueueID", "(empty)"))
        print(f"   Queue types: {queues_seen}")
    
    print("\n" + "=" * 60)
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())

