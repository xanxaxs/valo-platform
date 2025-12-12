"""Check match stats from database."""
import sqlite3
from pathlib import Path

db_path = Path(__file__).parent.parent / "data" / "valorant_tracker.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("=== 最近のマッチ ===")
cursor.execute("""
    SELECT match_id, map_name, result, ally_score, enemy_score, is_coach_view, game_start_millis
    FROM matches 
    ORDER BY game_start_millis DESC 
    LIMIT 5
""")
matches = cursor.fetchall()
for r in matches:
    match_id = r[0][:35] + "..." if len(r[0]) > 35 else r[0]
    print(f"  {match_id} | {r[1]} | {r[2]} | {r[3]}-{r[4]} | coach:{r[5]}")

print()
print("=== 最新マッチのプレイヤースタッツ ===")
if matches:
    latest_match_id = matches[0][0]
    cursor.execute("""
        SELECT player_name, agent_name, team_id, is_ally,
               kills, deaths, assists, score
        FROM player_match_stats 
        WHERE match_id = ?
    """, (latest_match_id,))
    stats = cursor.fetchall()
    if stats:
        print(f"  マッチID: {latest_match_id}")
        print(f"  プレイヤー数: {len(stats)}")
        print()
        for s in stats:
            name = s[0] if s[0] else "Unknown"
            agent = s[1] if s[1] else "Unknown"
            team = s[2] if s[2] else "?"
            kills = s[4] if s[4] is not None else "-"
            deaths = s[5] if s[5] is not None else "-"
            assists = s[6] if s[6] is not None else "-"
            score = s[7] if s[7] is not None else "-"
            print(f"    {name:15} | {agent:10} | Team:{team} | K:{kills} D:{deaths} A:{assists} | Score:{score}")
    else:
        print("  プレイヤースタッツなし")

print()
print("=== ラウンド情報 ===")
if matches:
    cursor.execute("""
        SELECT round_number, result, win_condition
        FROM rounds 
        WHERE match_id = ?
        ORDER BY round_number
    """, (latest_match_id,))
    rounds = cursor.fetchall()
    if rounds:
        print(f"  ラウンド数: {len(rounds)}")
        for r in rounds:
            print(f"    R{r[0]}: {r[1]} ({r[2]})")
    else:
        print("  ラウンド情報なし")

conn.close()

