"""
RAG Coaching Service.

Combines transcription, knowledge base, and LLM for intelligent coaching feedback.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from ..db.models import AudioSegment, Match, PlayerMatchStats, TranscriptSegment as DBTranscript
from .transcriber import WhisperTranscriber, TranscriptSegment
from .knowledge_base import CoachingKnowledgeBase
from .llm_client import LocalLLMClient, OllamaClient, COACHING_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


@dataclass
class CoachingFeedback:
    """Structured coaching feedback."""
    summary: str
    score: int  # 0-100
    improvements: list[str] = field(default_factory=list)
    highlights: list[str] = field(default_factory=list)
    transcript_segments: list[dict] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "summary": self.summary,
            "score": self.score,
            "improvements": self.improvements,
            "highlights": self.highlights,
            "transcript_segments": self.transcript_segments,
        }


@dataclass 
class MatchAnalysis:
    """Full match analysis result."""
    match_id: str
    map_name: str
    result: str
    score: str
    
    overall_score: int
    communication_rating: str  # "Excellent", "Good", "Needs Improvement"
    key_issues: list[str]
    strengths: list[str]
    round_feedbacks: list[dict]
    
    generated_at: datetime = field(default_factory=datetime.now)


# Analysis prompt templates
ROUND_ANALYSIS_PROMPT = """
## ラウンド{round_number}の分析

### ラウンド情報
- 結果: {result}
- スコア: {ally_score}-{enemy_score}
- 時間帯: {timing_info}

### 会話ログ
{transcript}

### 参考知識
{knowledge}

### 分析タスク
1. このラウンドのコミュニケーションを評価してください
2. 良かった点と改善点を具体的に挙げてください
3. 次のラウンドへの提案があれば記載してください

以下のJSON形式で回答:
{{
    "summary": "1-2文の総評",
    "score": 0-100の評価スコア,
    "improvements": ["改善点1", "改善点2"],
    "highlights": ["良かった点1", "良かった点2"]
}}
"""

MATCH_SUMMARY_PROMPT = """
## 試合全体の分析

### 試合情報
- マップ: {map_name}
- 結果: {result}
- スコア: {ally_score}-{enemy_score}

### ラウンドごとの評価
{round_summaries}

### 分析タスク
1. 試合全体のコミュニケーション傾向を分析
2. 一貫して見られた問題点を特定
3. 次の試合への具体的な改善提案

以下のJSON形式で回答:
{{
    "overall_score": 0-100の総合スコア,
    "communication_rating": "Excellent"/"Good"/"Needs Improvement",
    "key_issues": ["問題点1", "問題点2", "問題点3"],
    "strengths": ["強み1", "強み2"],
    "recommendations": ["提案1", "提案2", "提案3"]
}}
"""


class CoachService:
    """
    Main coaching service that orchestrates AI analysis.
    
    Features:
    - Audio transcription with Whisper
    - RAG-enhanced analysis with ChromaDB
    - LLM-powered feedback generation
    - Match and round-level analysis
    """
    
    def __init__(
        self,
        session: Session,
        llm_url: str = "http://localhost:1234/v1",
        llm_model: str = "local-model",
        whisper_model: str = "large-v3-turbo",
        knowledge_dir: Optional[Path] = None,
        use_ollama: bool = False,
    ):
        """
        Initialize coaching service.
        
        Args:
            session: Database session
            llm_url: LLM API URL
            llm_model: LLM model name
            whisper_model: Whisper model size
            knowledge_dir: Path for ChromaDB storage
            use_ollama: Use Ollama instead of LM Studio
        """
        self.session = session
        
        # Initialize components
        self.transcriber = WhisperTranscriber(model_size=whisper_model)
        
        self.knowledge_base = CoachingKnowledgeBase(
            persist_directory=knowledge_dir,
        )
        # Bootstrap if empty
        if self.knowledge_base.document_count == 0:
            self.knowledge_base.bootstrap()
        
        if use_ollama:
            self.llm = OllamaClient(base_url=llm_url, model=llm_model)
        else:
            self.llm = LocalLLMClient(base_url=llm_url, model=llm_model)
        
        logger.info("CoachService initialized")
    
    # ============================================
    # Transcription
    # ============================================
    
    def transcribe_match_audio(self, match_id: str) -> list[TranscriptSegment]:
        """
        Transcribe all audio for a match.
        
        Args:
            match_id: Match ID
            
        Returns:
            List of transcript segments
        """
        # Get audio segments
        segments = self.session.query(AudioSegment).filter(
            AudioSegment.match_id == match_id
        ).all()
        
        if not segments:
            logger.warning(f"No audio segments found for match {match_id}")
            return []
        
        all_transcripts = []
        
        for seg in segments:
            audio_path = Path(seg.file_path)
            if not audio_path.exists():
                logger.warning(f"Audio file not found: {audio_path}")
                continue
            
            transcripts = self.transcriber.transcribe_file(audio_path)
            all_transcripts.extend(transcripts)
        
        logger.info(f"Transcribed {len(all_transcripts)} segments for match {match_id}")
        return all_transcripts
    
    def save_transcripts(self, match_id: str, transcripts: list[TranscriptSegment]) -> int:
        """
        Save transcripts to database.
        
        Args:
            match_id: Match ID
            transcripts: List of transcript segments
            
        Returns:
            Number of segments saved
        """
        # Get rounds for timing mapping
        from ..db.models import Round
        rounds = self.session.query(Round).filter(
            Round.match_id == match_id
        ).order_by(Round.round_number).all()
        
        # Create round timing map
        round_timings = {}
        for r in rounds:
            if r.start_offset is not None and r.end_offset is not None:
                round_timings[r.round_number] = (r.start_offset, r.end_offset)
        
        saved = 0
        
        for i, t in enumerate(transcripts):
            # Determine round number from timing
            round_number = None
            for rnd_num, (start, end) in round_timings.items():
                if start <= t.start < end:
                    round_number = rnd_num
                    break
            
            db_segment = DBTranscript(
                id=f"{match_id}_t{i}",
                match_id=match_id,
                round_number=round_number,
                start_time=t.start,
                end_time=t.end,
                text=t.text,
                speaker=t.speaker,
                confidence=t.confidence,
            )
            self.session.add(db_segment)
            saved += 1
        
        self.session.commit()
        logger.info(f"Saved {saved} transcript segments (assigned to rounds: {len([t for t in transcripts if any(r[0] <= t.start < r[1] for r in round_timings.values())])})")
        return saved
    
    # ============================================
    # Analysis
    # ============================================
    
    async def analyze_round(
        self,
        match_id: str,
        round_number: int,
        transcripts: list[TranscriptSegment],
    ) -> CoachingFeedback:
        """
        Analyze a single round.
        
        Args:
            match_id: Match ID
            round_number: Round number
            transcripts: Transcript segments for this round
            
        Returns:
            CoachingFeedback object
        """
        # Get match info
        match = self.session.query(Match).filter(Match.match_id == match_id).first()
        
        # Format transcript
        transcript_text = self._format_transcript(transcripts)
        
        # Query knowledge base
        knowledge_docs = self.knowledge_base.query_for_round(
            round_context=f"Round {round_number}",
            transcript_summary=transcript_text[:200] if transcript_text else "会話なし",
            n_results=2,
        )
        knowledge_text = "\n\n".join(d["content"] for d in knowledge_docs)
        
        # Build prompt
        prompt = ROUND_ANALYSIS_PROMPT.format(
            round_number=round_number,
            result=match.result.value if match and match.result else "Unknown",
            ally_score=match.ally_score if match else 0,
            enemy_score=match.enemy_score if match else 0,
            timing_info="N/A",
            transcript=transcript_text or "(会話なし)",
            knowledge=knowledge_text or "(参考知識なし)",
        )
        
        # Get LLM response
        response = await self.llm.chat(
            prompt=prompt,
            system_prompt=COACHING_SYSTEM_PROMPT,
            temperature=0.7,
        )
        
        # Parse response
        try:
            data = response.to_json()
            if data:
                return CoachingFeedback(
                    summary=data.get("summary", "分析完了"),
                    score=data.get("score", 50),
                    improvements=data.get("improvements", []),
                    highlights=data.get("highlights", []),
                    transcript_segments=[t.to_dict() for t in transcripts],
                )
        except:
            pass
        
        # Fallback if JSON parsing fails
        return CoachingFeedback(
            summary=response.content[:200] if response.content else "分析エラー",
            score=50,
            improvements=[],
            highlights=[],
            transcript_segments=[t.to_dict() for t in transcripts],
        )
    
    def get_round_transcripts(
        self,
        match_id: str,
        round_number: int,
        all_transcripts: list[TranscriptSegment],
    ) -> list[TranscriptSegment]:
        """
        Get transcripts for a specific round.
        
        Args:
            match_id: Match ID
            round_number: Round number
            all_transcripts: All transcripts for the match
            
        Returns:
            List of transcript segments for this round
        """
        from ..db.models import Round
        
        # Get round timing
        round_obj = self.session.query(Round).filter(
            Round.match_id == match_id,
            Round.round_number == round_number,
        ).first()
        
        if not round_obj or round_obj.start_offset is None or round_obj.end_offset is None:
            # Fallback: estimate from round number (assume ~2min per round)
            estimated_start = (round_number - 1) * 120
            estimated_end = round_number * 120
        else:
            estimated_start = round_obj.start_offset
            estimated_end = round_obj.end_offset
        
        # Filter transcripts by timing
        round_transcripts = [
            t for t in all_transcripts
            if estimated_start <= t.start < estimated_end
        ]
        
        return round_transcripts
    
    async def analyze_match(self, match_id: str) -> Optional[MatchAnalysis]:
        """
        Analyze an entire match with round-by-round breakdown.
        
        Args:
            match_id: Match ID
            
        Returns:
            MatchAnalysis object or None
        """
        # Get match
        match = self.session.query(Match).filter(Match.match_id == match_id).first()
        if not match:
            logger.error(f"Match not found: {match_id}")
            return None
        
        # Get rounds
        from ..db.models import Round
        rounds = self.session.query(Round).filter(
            Round.match_id == match_id
        ).order_by(Round.round_number).all()
        
        # Transcribe audio
        all_transcripts = self.transcribe_match_audio(match_id)
        
        if not all_transcripts:
            logger.warning("No transcripts available for analysis")
            all_transcripts = []
        
        # Analyze each round
        round_feedbacks = []
        
        for round_obj in rounds:
            round_transcripts = self.get_round_transcripts(
                match_id,
                round_obj.round_number,
                all_transcripts,
            )
            
            if round_transcripts:
                feedback = await self.analyze_round(
                    match_id,
                    round_obj.round_number,
                    round_transcripts,
                )
                round_feedbacks.append(feedback.to_dict())
            else:
                # No transcripts for this round
                round_feedbacks.append({
                    "round_number": round_obj.round_number,
                    "summary": "音声データなし",
                    "score": 0,
                    "improvements": [],
                    "highlights": [],
                })
        
        # If no rounds, analyze as single block
        if not round_feedbacks and all_transcripts:
            all_feedback = await self.analyze_round(match_id, 0, all_transcripts)
            round_feedbacks = [all_feedback.to_dict()]
        
        # Calculate overall stats from round feedbacks
        if round_feedbacks:
            avg_score = sum(fb.get("score", 0) for fb in round_feedbacks) / len(round_feedbacks)
            all_improvements = []
            all_highlights = []
            for fb in round_feedbacks:
                all_improvements.extend(fb.get("improvements", []))
                all_highlights.extend(fb.get("highlights", []))
            
            round_summaries = "\n".join([
                f"Round {fb.get('round_number', '?')}: {fb.get('score', 0)}/100 - {fb.get('summary', 'N/A')[:50]}"
                for fb in round_feedbacks[:10]  # First 10 rounds
            ])
        else:
            avg_score = 0
            all_improvements = []
            all_highlights = []
            round_summaries = "No round data available"
        
        # Generate match summary with LLM
        prompt = MATCH_SUMMARY_PROMPT.format(
            map_name=match.map_name,
            result=match.result.value if match.result else "Unknown",
            ally_score=match.ally_score,
            enemy_score=match.enemy_score,
            round_summaries=round_summaries,
        )
        
        response = await self.llm.chat(
            prompt=prompt,
            system_prompt=COACHING_SYSTEM_PROMPT,
            temperature=0.5,
        )
        
        # Parse response
        try:
            data = response.to_json()
            if data:
                return MatchAnalysis(
                    match_id=match_id,
                    map_name=match.map_name,
                    result=match.result.value if match.result else "Unknown",
                    score=f"{match.ally_score}-{match.enemy_score}",
                    overall_score=data.get("overall_score", int(avg_score)),
                    communication_rating=data.get("communication_rating", "Needs Improvement"),
                    key_issues=data.get("key_issues", all_improvements[:5]),
                    strengths=data.get("strengths", all_highlights[:5]),
                    round_feedbacks=round_feedbacks,
                )
        except:
            pass
        
        # Fallback
        return MatchAnalysis(
            match_id=match_id,
            map_name=match.map_name,
            result=match.result.value if match.result else "Unknown",
            score=f"{match.ally_score}-{match.enemy_score}",
            overall_score=int(avg_score),
            communication_rating="Needs Improvement",
            key_issues=all_improvements[:5],
            strengths=all_highlights[:5],
            round_feedbacks=round_feedbacks,
        )
    
    def _format_transcript(self, transcripts: list[TranscriptSegment]) -> str:
        """Format transcripts for prompt."""
        if not transcripts:
            return ""
        
        lines = []
        for t in transcripts:
            timestamp = f"{int(t.start // 60)}:{int(t.start % 60):02d}"
            speaker = t.speaker if t.speaker != "Unknown" else "?"
            lines.append(f"[{timestamp}] {speaker}: {t.text}")
        
        return "\n".join(lines)
    
    # ============================================
    # Quick Analysis (No LLM)
    # ============================================
    
    def quick_analysis(self, match_id: str) -> dict:
        """
        Quick analysis without LLM (for when LLM is unavailable).
        
        Uses rule-based evaluation.
        
        Args:
            match_id: Match ID
            
        Returns:
            Analysis dict
        """
        # Transcribe
        transcripts = self.transcribe_match_audio(match_id)
        
        if not transcripts:
            return {
                "status": "no_audio",
                "message": "音声データがありません",
                "transcript_count": 0,
            }
        
        # Save transcripts to database
        try:
            saved_count = self.save_transcripts(match_id, transcripts)
            logger.info(f"Saved {saved_count} transcript segments to database")
        except Exception as e:
            logger.warning(f"Failed to save transcripts: {e}")
        
        # Basic stats
        total_duration = sum(t.duration for t in transcripts)
        avg_segment_length = total_duration / len(transcripts) if transcripts else 0
        
        # Simple heuristics
        short_callouts = sum(1 for t in transcripts if t.duration < 3)
        long_callouts = sum(1 for t in transcripts if t.duration > 10)
        
        score = 50
        issues = []
        strengths = []
        
        # Score adjustments
        if short_callouts > len(transcripts) * 0.5:
            score += 10
            strengths.append("簡潔なコールアウトが多い")
        
        if long_callouts > len(transcripts) * 0.3:
            score -= 10
            issues.append("長すぎる発言が多い")
        
        if len(transcripts) < 10:
            score -= 15
            issues.append("コミュニケーション量が少ない")
        elif len(transcripts) > 50:
            score += 5
            strengths.append("積極的なコミュニケーション")
        
        return {
            "status": "success",
            "transcript_count": len(transcripts),
            "total_duration": total_duration,
            "avg_segment_length": avg_segment_length,
            "score": max(0, min(100, score)),
            "issues": issues,
            "strengths": strengths,
            "transcripts": [t.to_dict() for t in transcripts[:20]],  # First 20
        }

