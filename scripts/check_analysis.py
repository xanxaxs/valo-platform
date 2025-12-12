"""
Check audio segment analysis results.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db.database import get_session, init_db
from src.db.models import TranscriptSegment, AudioSegment

def main():
    init_db()
    session = next(get_session())
    
    print('=== Audio Segments ===')
    segments = session.query(AudioSegment).all()
    for s in segments:
        fname = Path(s.file_path).name
        print(f'\nMatch: {s.match_id[:30]}...')
        print(f'  File: {fname}')
        round_info = s.round_number if s.round_number else "Full match"
        print(f'  Round: {round_info}')
        exists = Path(s.file_path).exists()
        print(f'  Exists: {exists}')
        if exists:
            size_mb = Path(s.file_path).stat().st_size / (1024*1024)
            print(f'  Size: {size_mb:.1f} MB')
    
    print()
    print('=== Transcript Segments ===')
    transcripts = session.query(TranscriptSegment).all()
    print(f'Total: {len(transcripts)} segments in database')
    
    if transcripts:
        print()
        print('Sample (first 10):')
        for i, t in enumerate(transcripts[:10], 1):
            start_min = int(t.start_time // 60)
            start_sec = int(t.start_time % 60)
            end_min = int(t.end_time // 60)
            end_sec = int(t.end_time % 60)
            duration = t.end_time - t.start_time
            print(f'\n{i:2}. [{start_min}:{start_sec:02d}-{end_min}:{end_sec:02d}] ({duration:.1f}s)')
            print(f'    Speaker: {t.speaker}')
            text_preview = t.text[:80] + '...' if len(t.text) > 80 else t.text
            print(f'    Text: {text_preview}')
            print(f'    Confidence: {t.confidence:.2f}')
    else:
        print('  No transcripts found in database')
        print('  (Transcription results are not saved to DB yet)')
        print('  (They are only returned by quick_analysis)')
    
    # Check what quick_analysis actually returns
    print()
    print('=== Quick Analysis Output ===')
    print('Running quick_analysis to see actual results...')
    
    from src.ai.coach import CoachService
    
    match_id = 'coach_d0ad2850_1765434583'
    coach = CoachService(
        session=session,
        whisper_model='base',
    )
    
    result = coach.quick_analysis(match_id)
    
    if result.get('status') == 'success':
        print(f'Status: {result["status"]}')
        print(f'Transcript segments: {result["transcript_count"]}')
        print(f'Total duration: {result["total_duration"]:.1f}s')
        print(f'Average segment length: {result["avg_segment_length"]:.1f}s')
        print(f'Score: {result["score"]}/100')
        
        transcripts = result.get('transcripts', [])
        if transcripts:
            print()
            print('Sample transcripts from analysis:')
            for i, t in enumerate(transcripts[:5], 1):
                start = t.get('start', 0)
                start_min = int(start // 60)
                start_sec = int(start % 60)
                text = t.get('text', '')
                print(f'{i}. [{start_min}:{start_sec:02d}] {text[:100]}...' if len(text) > 100 else f'{i}. [{start_min}:{start_sec:02d}] {text}')
    
    return 0

if __name__ == "__main__":
    sys.exit(main())

