"""
Detailed audio analysis report.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db.database import get_session, init_db
from src.ai.coach import CoachService

def main():
    init_db()
    session = next(get_session())
    
    match_id = 'coach_d0ad2850_1765434583'
    
    print('=' * 60)
    print('Audio Segment Analysis Report')
    print('=' * 60)
    print()
    
    # Initialize coach
    coach = CoachService(
        session=session,
        whisper_model='base',
    )
    
    # Run analysis
    print('Running transcription and analysis...')
    result = coach.quick_analysis(match_id)
    
    if result.get('status') != 'success':
        print(f"Error: {result.get('message', 'Unknown error')}")
        return 1
    
    print()
    print('=' * 60)
    print('ANALYSIS RESULTS')
    print('=' * 60)
    print()
    
    # Basic stats
    print('[Basic Statistics]')
    print(f'  Total segments: {result["transcript_count"]}')
    print(f'  Total duration: {result["total_duration"]:.1f} seconds ({result["total_duration"]/60:.1f} minutes)')
    print(f'  Average segment length: {result["avg_segment_length"]:.1f} seconds')
    print()
    
    # Score
    print('[Communication Score]')
    print(f'  Score: {result["score"]}/100')
    print()
    
    # Issues and strengths
    issues = result.get('issues', [])
    strengths = result.get('strengths', [])
    
    if issues:
        print('[Issues Detected]')
        for issue in issues:
            print(f'  - {issue}')
        print()
    
    if strengths:
        print('[Strengths]')
        for strength in strengths:
            print(f'  - {strength}')
        print()
    
    # Detailed segment analysis
    transcripts = result.get('transcripts', [])
    if transcripts:
        print('=' * 60)
        print('TRANSCRIPT SEGMENTS')
        print('=' * 60)
        print()
        
        # Group by duration
        short_segments = [t for t in transcripts if t.get('duration', 0) < 3]
        medium_segments = [t for t in transcripts if 3 <= t.get('duration', 0) <= 10]
        long_segments = [t for t in transcripts if t.get('duration', 0) > 10]
        
        print(f'Duration Distribution:')
        print(f'  Short (<3s): {len(short_segments)} segments')
        print(f'  Medium (3-10s): {len(medium_segments)} segments')
        print(f'  Long (>10s): {len(long_segments)} segments')
        print()
        
        # Show sample segments
        print('Sample Segments:')
        print()
        
        if short_segments:
            print('Short callouts (good):')
            for i, t in enumerate(short_segments[:3], 1):
                start = t.get('start', 0)
                start_min = int(start // 60)
                start_sec = int(start % 60)
                duration = t.get('duration', 0)
                text = t.get('text', '')
                print(f'  {i}. [{start_min}:{start_sec:02d}] ({duration:.1f}s) {text[:60]}...')
            print()
        
        if long_segments:
            print('Long callouts (needs improvement):')
            for i, t in enumerate(long_segments[:3], 1):
                start = t.get('start', 0)
                start_min = int(start // 60)
                start_sec = int(start % 60)
                duration = t.get('duration', 0)
                text = t.get('text', '')
                print(f'  {i}. [{start_min}:{start_sec:02d}] ({duration:.1f}s) {text[:60]}...')
            print()
        
        # Timeline
        print('Timeline (first 10 segments):')
        for i, t in enumerate(transcripts[:10], 1):
            start = t.get('start', 0)
            start_min = int(start // 60)
            start_sec = int(start % 60)
            duration = t.get('duration', 0)
            text = t.get('text', '')
            text_preview = text[:50] + '...' if len(text) > 50 else text
            print(f'  {i:2}. [{start_min}:{start_sec:02d}] ({duration:5.1f}s) {text_preview}')
    
    print()
    print('=' * 60)
    print('Analysis Complete')
    print('=' * 60)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())

