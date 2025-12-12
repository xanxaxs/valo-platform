"""
Test coaching functionality with real data.
"""

import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db.database import get_session, init_db
from src.ai.coach import CoachService

def main():
    """Test coaching with real match data."""
    init_db()
    session = next(get_session())
    
    # Get match with audio
    match_id = 'coach_d0ad2850_1765434583'
    print(f'Testing Quick Analysis for match: {match_id}')
    print('=' * 60)
    
    # Initialize coach service
    coach = CoachService(
        session=session,
        whisper_model='base',  # Use smaller model for testing
    )
    
    # Run quick analysis
    print('\nRunning Quick Analysis (this may take a while for transcription)...')
    result = coach.quick_analysis(match_id)
    
    print()
    print('=== Quick Analysis Results ===')
    print(f'Status: {result.get("status", "unknown")}')
    
    if result.get('status') == 'success':
        print(f'Transcript segments: {result.get("transcript_count", 0)}')
        print(f'Total duration: {result.get("total_duration", 0):.1f}s')
        print(f'Average segment length: {result.get("avg_segment_length", 0):.1f}s')
        print()
        print(f'Communication Score: {result.get("score", 0)}/100')
        print()
        print('Issues:')
        for issue in result.get('issues', []):
            print(f'  - {issue}')
        print()
        print('Strengths:')
        for strength in result.get('strengths', []):
            print(f'  - {strength}')
        
        # Show sample transcripts
        transcripts = result.get('transcripts', [])
        if transcripts:
            print()
            print('Sample Transcripts (first 5):')
            for t in transcripts[:5]:
                start = int(t.get('start', 0))
                minutes = start // 60
                seconds = start % 60
                print(f'  [{minutes}:{seconds:02d}] {t.get("text", "")[:60]}...')
    else:
        print(f'Error: {result.get("message", "Unknown error")}')
    
    return 0

if __name__ == "__main__":
    sys.exit(main())

