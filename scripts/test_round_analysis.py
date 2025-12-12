"""
Test round-by-round analysis.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db.database import get_session, init_db
from src.ai.coach import CoachService
import asyncio

def main():
    init_db()
    session = next(get_session())
    
    match_id = 'coach_d0ad2850_1765434583'
    
    print('=' * 60)
    print('Round-by-Round Analysis Test')
    print('=' * 60)
    print()
    
    # Check rounds
    from src.db.models import Round
    rounds = session.query(Round).filter(Round.match_id == match_id).all()
    
    print(f'Rounds in database: {len(rounds)}')
    if rounds:
        for r in rounds[:5]:
            print(f'  Round {r.round_number}: {r.result} | start={r.start_offset}s, end={r.end_offset}s')
    else:
        print('  No rounds found - will analyze as single block')
    
    print()
    print('Running Quick Analysis (saves transcripts to DB)...')
    
    # Quick analysis (saves transcripts)
    coach = CoachService(session=session, whisper_model='base')
    result = coach.quick_analysis(match_id)
    
    if result.get('status') == 'success':
        print(f'Transcribed {result["transcript_count"]} segments')
        print(f'Score: {result["score"]}/100')
        
        # Check saved transcripts
        from src.db.models import TranscriptSegment as DBTranscript
        saved = session.query(DBTranscript).filter(
            DBTranscript.match_id == match_id
        ).all()
        
        print()
        print(f'Saved transcripts: {len(saved)}')
        if saved:
            rounds_with_transcripts = set(t.round_number for t in saved if t.round_number)
            print(f'Rounds with transcripts: {sorted(rounds_with_transcripts)}')
            
            # Show sample
            print()
            print('Sample transcripts:')
            for t in saved[:5]:
                start_min = int(t.start_time // 60)
                start_sec = int(t.start_time % 60)
                round_info = f"Round {t.round_number}" if t.round_number else "Unknown"
                print(f'  [{start_min}:{start_sec:02d}] ({round_info}) {t.text[:60]}...')
    else:
        print(f'Error: {result.get("message")}')
    
    print()
    print('=' * 60)
    print('Test Complete')
    print('=' * 60)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())

