# -*- coding: utf-8 -*-
"""
Show ALL recent matches from multiple players to find the custom match
"""
import asyncio
import sys
import json
from pathlib import Path
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.api.client import ValorantClient

async def main():
    print("=" * 60)
    print("All Recent Matches Search")
    print("=" * 60)
    
    client = ValorantClient()
    
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
    
    # Collect all unique matches
    all_matches = {}
    
    print("\n[2] Collecting matches from players...")
    
    for i, puuid in enumerate(other_puuids[:15]):
        history = await client.get_match_history(puuid, count=5)
        
        if not history or not history.get("History"):
            continue
        
        for match in history["History"]:
            match_id = match.get("MatchID", "")
            if match_id not in all_matches:
                game_start = match.get("GameStartTime", 0)
                queue = match.get("QueueID", "(empty)")
                all_matches[match_id] = {
                    "id": match_id,
                    "queue": queue,
                    "start": game_start,
                    "start_str": datetime.fromtimestamp(game_start/1000).strftime("%Y-%m-%d %H:%M") if game_start else "?"
                }
        
        print(f"   Checked player {i+1}/15, found {len(all_matches)} unique matches", end="\r")
        await asyncio.sleep(0.2)
    
    print(f"\n\n[3] Found {len(all_matches)} unique matches total")
    
    # Sort by start time (most recent first)
    sorted_matches = sorted(all_matches.values(), key=lambda x: x["start"], reverse=True)
    
    print("\n[4] Most recent matches:")
    print("-" * 70)
    
    for i, m in enumerate(sorted_matches[:15]):
        queue_display = m["queue"] if m["queue"] else "(CUSTOM?)"
        print(f"   {i+1:2}. {m['start_str']} | Queue: {queue_display:15} | {m['id'][:25]}...")
    
    # Find matches with empty queue (likely custom)
    custom_candidates = [m for m in sorted_matches if not m["queue"] or m["queue"] == ""]
    
    if custom_candidates:
        print(f"\n[5] Found {len(custom_candidates)} potential custom matches:")
        for m in custom_candidates[:5]:
            print(f"\n   Match: {m['id']}")
            print(f"   Time: {m['start_str']}")
            
            # Get details
            details = await client.get_match_details(m["id"])
            if details:
                match_info = details.get("matchInfo", {})
                map_id = match_info.get("mapId", "?")
                teams = details.get("teams", [])
                score = f"{teams[0].get('roundsWon', 0)}-{teams[1].get('roundsWon', 0)}" if len(teams) >= 2 else "?"
                
                print(f"   Map: {map_id}")
                print(f"   Score: {score}")
                
                # Check if this is likely our match (Abyss map)
                if "infinity" in map_id.lower():
                    print("   >>> This might be the coached match! <<<")
                    
                    # Save it
                    output_path = Path(__file__).parent.parent / "data" / "output" / "coached_match.json"
                    output_path.write_text(json.dumps(details, indent=2, ensure_ascii=False), encoding='utf-8')
                    print(f"   Saved to: {output_path}")
    else:
        print("\n[5] No custom matches found in recent history")
        print("    The custom match might not be in the API yet, or it's stored differently.")
    
    print("\n" + "=" * 60)
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())

