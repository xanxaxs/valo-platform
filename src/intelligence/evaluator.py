"""
Multi-Modal Evaluator Module

Combines vision and audio analysis for round evaluation.
"""

import logging
from typing import Optional

from src.intelligence.llm import LMStudioClient, COACHING_SYSTEM_PROMPT
from src.intelligence.rag import CoachingKnowledgeBase
from src.models.schemas import (
    AIFeedback,
    Round,
    RoundResult,
    TranscriptSegment,
    VisionAnalysis,
)

logger = logging.getLogger(__name__)


class RoundEvaluator:
    """
    Multi-modal round evaluator.

    Combines vision data (game state) with audio data (communications)
    to generate coaching feedback using RAG-enhanced LLM.
    """

    EVALUATION_PROMPT_TEMPLATE = """
ラウンド分析を行います。

## ラウンド情報
- 結果: {result}
- 決着条件: {win_condition}
- 経済状況: {economy_tag}
- 生存者: 味方 {survivors} vs 敵 {enemies}
- ラウンド時間: {duration}秒

## 会話ログ
{transcript}

## 参考知識
{knowledge}

## 分析タスク
1. コミュニケーションの質を評価してください
2. 報告のタイミングや内容に問題はありましたか？
3. 結果と会話内容に整合性はありますか？
4. 具体的な改善点を挙げてください

以下のJSON形式で回答してください:
{{
    "summary": "1-2文の総評",
    "score": 0-100の評価スコア,
    "improvements": ["改善点1", "改善点2"],
    "highlights": ["良かった点1", "良かった点2"]
}}
"""

    def __init__(
        self,
        llm_client: LMStudioClient,
        knowledge_base: Optional[CoachingKnowledgeBase] = None,
    ):
        """
        Initialize evaluator.

        Args:
            llm_client: LM Studio client for inference
            knowledge_base: Optional RAG knowledge base
        """
        self.llm = llm_client
        self.kb = knowledge_base

    def evaluate_round(
        self,
        vision: VisionAnalysis,
        transcript: list[TranscriptSegment],
        duration_seconds: int = 0,
    ) -> AIFeedback:
        """
        Evaluate a round based on vision and audio data.

        Args:
            vision: Vision analysis result
            transcript: List of transcript segments
            duration_seconds: Round duration

        Returns:
            AIFeedback with summary, score, and improvements
        """
        # Format transcript
        transcript_text = self._format_transcript(transcript)

        # Query knowledge base if available
        knowledge_text = ""
        if self.kb:
            context = self._build_context(vision, transcript)
            docs = self.kb.query_for_round(
                round_context=context,
                transcript_summary=transcript_text[:200],
                n_results=2,
            )
            knowledge_text = "\n\n".join(d["content"] for d in docs)

        # Build evaluation prompt
        prompt = self.EVALUATION_PROMPT_TEMPLATE.format(
            result=vision.result.value,
            win_condition=vision.win_condition.value,
            economy_tag=vision.economy_tag.value,
            survivors=vision.vision_metadata.survivors_count,
            enemies=vision.vision_metadata.enemy_survivors,
            duration=duration_seconds,
            transcript=transcript_text or "(会話なし)",
            knowledge=knowledge_text or "(参考知識なし)",
        )

        try:
            response = self.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                system_prompt=COACHING_SYSTEM_PROMPT,
                temperature=0.3,
                max_tokens=800,
            )

            return self._parse_feedback(response)

        except Exception as e:
            logger.error(f"Evaluation failed: {e}")
            return AIFeedback(
                summary="評価処理中にエラーが発生しました",
                score=50,
                improvements=["LLMへの接続を確認してください"],
                highlights=[],
            )

    async def aevaluate_round(
        self,
        vision: VisionAnalysis,
        transcript: list[TranscriptSegment],
        duration_seconds: int = 0,
    ) -> AIFeedback:
        """Async version of evaluate_round."""
        transcript_text = self._format_transcript(transcript)

        knowledge_text = ""
        if self.kb:
            context = self._build_context(vision, transcript)
            docs = self.kb.query_for_round(
                round_context=context,
                transcript_summary=transcript_text[:200],
                n_results=2,
            )
            knowledge_text = "\n\n".join(d["content"] for d in docs)

        prompt = self.EVALUATION_PROMPT_TEMPLATE.format(
            result=vision.result.value,
            win_condition=vision.win_condition.value,
            economy_tag=vision.economy_tag.value,
            survivors=vision.vision_metadata.survivors_count,
            enemies=vision.vision_metadata.enemy_survivors,
            duration=duration_seconds,
            transcript=transcript_text or "(会話なし)",
            knowledge=knowledge_text or "(参考知識なし)",
        )

        try:
            response = await self.llm.achat(
                messages=[{"role": "user", "content": prompt}],
                system_prompt=COACHING_SYSTEM_PROMPT,
                temperature=0.3,
                max_tokens=800,
            )

            return self._parse_feedback(response)

        except Exception as e:
            logger.error(f"Async evaluation failed: {e}")
            return AIFeedback(
                summary="評価処理中にエラーが発生しました",
                score=50,
            )

    def _format_transcript(self, transcript: list[TranscriptSegment]) -> str:
        """Format transcript segments for LLM prompt."""
        if not transcript:
            return ""

        lines = []
        for seg in transcript:
            sentiment_tag = f"[{seg.sentiment.value}]" if seg.sentiment else ""
            lines.append(
                f"[{seg.time_offset:.1f}s] {seg.speaker_id}: {seg.content} {sentiment_tag}"
            )

        return "\n".join(lines)

    def _build_context(
        self, vision: VisionAnalysis, transcript: list[TranscriptSegment]
    ) -> str:
        """Build context string for RAG query."""
        result_text = "勝利" if vision.result == RoundResult.WIN else "敗北"
        survivors = f"{vision.vision_metadata.survivors_count}vs{vision.vision_metadata.enemy_survivors}"

        return f"{result_text}ラウンド ({survivors}), {vision.economy_tag.value}"

    def _parse_feedback(self, response: str) -> AIFeedback:
        """Parse LLM response into AIFeedback."""
        import json

        # Try to extract JSON from response
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0]
        elif "```" in response:
            response = response.split("```")[1].split("```")[0]

        try:
            data = json.loads(response.strip())
            return AIFeedback(
                summary=data.get("summary", ""),
                score=min(100, max(0, int(data.get("score", 50)))),
                improvements=data.get("improvements", []),
                highlights=data.get("highlights", []),
            )
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse feedback JSON: {e}")
            # Return raw response as summary
            return AIFeedback(
                summary=response[:200],
                score=50,
            )

    def batch_evaluate(self, rounds: list[Round]) -> list[AIFeedback]:
        """
        Evaluate multiple rounds.

        Args:
            rounds: List of Round objects with vision and transcript data

        Returns:
            List of AIFeedback for each round
        """
        results = []

        for round_data in rounds:
            # Reconstruct VisionAnalysis from Round
            vision = VisionAnalysis(
                result=round_data.result,
                win_condition=round_data.win_condition,
                economy_tag=round_data.economy_tag,
                vision_metadata=round_data.vision_metadata,
            )

            feedback = self.evaluate_round(
                vision=vision,
                transcript=round_data.transcript,
                duration_seconds=round_data.duration_seconds,
            )
            results.append(feedback)

        return results
