# -*- coding: utf-8 -*-
"""
Live API Test - Coach mode data retrieval test
"""
import asyncio
import sys
import json
from pathlib import Path

# Fix Windows console encoding
sys.stdout.reconfigure(encoding='utf-8')

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.api.client import ValorantClient

async def main():
    print("=" * 60)
    print("VALORANT API Live Test (Coach Mode)")
    print("=" * 60)
    
    client = ValorantClient()
    
    # 1. Connect
    print("\n[1] Connecting to Valorant...")
    connected = await client.connect()
    if not connected:
        print("[FAIL] Failed to connect. Is Valorant running?")
        return
    
    print(f"[OK] Connected as PUUID: {client.puuid[:8]}...")
    
    # 2. Check game state
    print("\n[2] Checking game state...")
    state = await client.get_game_state()
    print(f"   Game State: {state.value}")
    
    # 3. Get presence data
    print("\n[3] Getting presence data...")
    presence = await client.get_presence_data()
    if presence:
        print(f"   sessionLoopState: {presence.get('sessionLoopState', 'N/A')}")
        match_data = presence.get("matchPresenceData", {})
        print(f"   matchMap: {match_data.get('matchMap', 'N/A')}")
        party_data = presence.get("partyPresenceData", {})
        print(f"   partyOwnerSessionLoopState: {party_data.get('partyOwnerSessionLoopState', 'N/A')}")
        print(f"   customGameTeam: {party_data.get('customGameTeam', 'N/A')}")
        print(f"   Score: {party_data.get('partyOwnerMatchScoreAllyTeam', 0)}-{party_data.get('partyOwnerMatchScoreEnemyTeam', 0)}")
    else:
        print("   [FAIL] No presence data")
    
    # 4. Try to get current match ID
    print("\n[4] Getting current match ID...")
    match_id = await client.get_current_match_id()
    print(f"   Match ID: {match_id or 'Not available (coach mode?)'}")
    
    # 5. Try core-game player endpoint
    print("\n[5] Trying core-game player endpoint...")
    coregame = await client._request("GET", f"/core-game/v1/player/{client.puuid}")
    if coregame:
        print(f"   [OK] Core-game MatchID: {coregame.get('MatchID', 'N/A')}")
    else:
        print("   [FAIL] Core-game not available (expected in coach mode)")
    
    # 6. Try to get match data if we have match ID
    if match_id:
        print("\n[6] Getting current match data...")
        match_data = await client.get_current_match_data(match_id)
        if match_data:
            players = match_data.get("Players", [])
            print(f"   [OK] Found {len(players)} players in match")
            for p in players[:3]:
                print(f"      - {p.get('Subject', 'N/A')[:8]}... Team: {p.get('TeamID', 'N/A')}")
        else:
            print("   [FAIL] No match data")
    
    # 7. Test Remote PD API - Own match history
    print("\n[7] Testing Remote PD API - Own match history...")
    print(f"   Shard: {client._shard}")
    print(f"   Access Token: {'[OK] Set' if client._access_token else '[FAIL] Not set'}")
    print(f"   Entitlements: {'[OK] Set' if client._entitlements_token else '[FAIL] Not set'}")
    
    history = await client.get_match_history(client.puuid, count=3)
    if history:
        matches = history.get("History", [])
        print(f"   [OK] Got {len(matches)} matches from own history")
        for m in matches[:3]:
            print(f"      - {m.get('MatchID', 'N/A')[:16]}...")
    else:
        print("   [FAIL] No match history (may be expected for coach)")
    
    # 8. Get players from presence and try their history
    print("\n[8] Getting all presences to find other players...")
    presences = await client._request("GET", "/chat/v4/presences")
    other_puuids = []
    
    if presences and presences.get("presences"):
        for p in presences["presences"]:
            puuid = p.get("puuid")
            if puuid and puuid != client.puuid:
                other_puuids.append(puuid)
        print(f"   Found {len(other_puuids)} other players in presences")
    
    # 9. Try other players' match history
    if other_puuids:
        print("\n[9] Testing match history for other players...")
        for puuid in other_puuids[:5]:
            print(f"\n   Trying player {puuid[:8]}...")
            history = await client.get_match_history(puuid, count=3)
            if history:
                matches = history.get("History", [])
                print(f"   [OK] Got {len(matches)} matches")
                if matches:
                    latest = matches[0]
                    print(f"      Latest: {latest.get('MatchID', 'N/A')[:20]}...")
                    
                    # Try to get match details
                    print(f"   [9b] Getting match details...")
                    details = await client.get_match_details(latest.get("MatchID"))
                    if details:
                        players = details.get("players", [])
                        teams = details.get("teams", [])
                        print(f"      [OK] Match details: {len(players)} players, {len(teams)} teams")
                        if teams:
                            print(f"      Score: {teams[0].get('roundsWon', 0)}-{teams[1].get('roundsWon', 0) if len(teams) > 1 else '?'}")
                    else:
                        print(f"      [FAIL] No match details")
                    break
            else:
                print(f"   [FAIL] No history")
            
            await asyncio.sleep(0.5)  # Rate limiting
    
    # 10. Try help endpoint to find available events
    print("\n[10] Checking help endpoint for match events...")
    help_data = await client._request("GET", "/help")
    if help_data:
        events = help_data.get("events", {})
        match_events = [e for e in events.keys() if "match" in e.lower() or "game" in e.lower()]
        print(f"   Found {len(match_events)} match-related events:")
        for e in match_events[:10]:
            print(f"      - {e}")
    
    print("\n" + "=" * 60)
    print("Test complete!")
    print("=" * 60)
    
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())

