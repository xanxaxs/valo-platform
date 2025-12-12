# -*- coding: utf-8 -*-
"""Check database status."""
import sqlite3
from pathlib import Path

db_path = Path(__file__).parent.parent / "data" / "valorant_tracker.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print("=== Database Tables ===")
for table in tables:
    table_name = table[0]
    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    count = cursor.fetchone()[0]
    print(f"  {table_name}: {count} rows")

print()
print("=== Recent Matches ===")
cursor.execute("""
    SELECT match_id, map_name, result, ally_score, enemy_score, is_coach_view
    FROM matches 
    ORDER BY game_start_millis DESC 
    LIMIT 5
""")
matches = cursor.fetchall()
for r in matches:
    match_id = r[0][:35] if len(r[0]) > 35 else r[0]
    map_name = r[1] if r[1] else "Unknown"
    result = r[2] if r[2] else "?"
    ally_score = r[3] if r[3] is not None else 0
    enemy_score = r[4] if r[4] is not None else 0
    coach = "Yes" if r[5] else "No"
    print(f"  {match_id}")
    print(f"    Map: {map_name} | Result: {result} | Score: {ally_score}-{enemy_score} | Coach: {coach}")

print()
print("=== Player Stats for Latest Match ===")
if matches:
    latest_match_id = matches[0][0]
    cursor.execute("""
        SELECT player_name, agent_name, is_ally, kills, deaths, assists, score
        FROM player_match_stats 
        WHERE match_id = ?
    """, (latest_match_id,))
    stats = cursor.fetchall()
    if stats:
        print(f"  Players: {len(stats)}")
        for s in stats:
            name = s[0] if s[0] else "Unknown"
            agent = s[1] if s[1] else "?"
            team = "Ally" if s[2] else "Enemy"
            k, d, a, sc = s[3] or 0, s[4] or 0, s[5] or 0, s[6] or 0
            print(f"    [{team}] {name:15} | {agent:10} | K/D/A: {k}/{d}/{a} | Score: {sc}")
    else:
        print("  No player stats")

print()
print("=== Round Information ===")
if matches:
    cursor.execute("""
        SELECT COUNT(*) FROM rounds WHERE match_id = ?
    """, (latest_match_id,))
    round_count = cursor.fetchone()[0]
    print(f"  Rounds recorded: {round_count}")

print()
print("=== Coach Analysis ===")
cursor.execute("""
    SELECT match_id, analysis_type, created_at FROM coach_analyses
    ORDER BY created_at DESC LIMIT 5
""")
analyses = cursor.fetchall()
if analyses:
    for a in analyses:
        print(f"  {a[0][:30]}... | Type: {a[1]} | At: {a[2]}")
else:
    print("  No coach analyses")

conn.close()

