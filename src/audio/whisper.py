"""
Faster-Whisper Transcription Module

Valorant-optimized speech-to-text with terminology injection.
"""

import json
import logging
from pathlib import Path
from typing import Iterator, Optional

from faster_whisper import WhisperModel
from faster_whisper.transcribe import Segment

from src.models.schemas import TranscriptSegment, Sentiment

logger = logging.getLogger(__name__)


class ValorantWhisperTranscriber:
    """
    Whisper-based transcription optimized for Valorant voice comms.

    Uses Faster-Whisper with CTranslate2 backend for CPU efficiency.
    Injects Valorant terminology into initial_prompt for accuracy.
    """

    def __init__(
        self,
        model_size: str = "large-v3-turbo",
        device: str = "cpu",
        compute_type: str = "int8",
        terms_path: Optional[Path] = None,
    ):
        """
        Initialize Whisper transcriber.

        Args:
            model_size: Whisper model size (large-v3-turbo recommended)
            device: "cpu" or "cuda" (for NVIDIA) or "auto"
            compute_type: Quantization type (int8 for CPU, float16 for GPU)
            terms_path: Path to valorant_terms.json for prompt injection
        """
        logger.info(f"Loading Whisper model: {model_size} on {device}")

        self.model = WhisperModel(
            model_size,
            device=device,
            compute_type=compute_type,
        )

        self.terms_prompt = self._load_terms_prompt(terms_path)
        logger.info("Whisper model loaded successfully")

    def _load_terms_prompt(self, terms_path: Optional[Path]) -> str:
        """Load Valorant terminology for prompt injection."""
        if not terms_path or not terms_path.exists():
            # Default prompt
            return (
                "Valorant voice chat. Agents: Jett, Reyna, Sage, Sova, Omen. "
                "Terms: プッシュ、ラッシュ、エントリー、カバー、クラッチ。"
            )

        try:
            with open(terms_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("whisper_prompt", "")
        except Exception as e:
            logger.warning(f"Failed to load terms: {e}")
            return ""

    def transcribe_file(
        self,
        audio_path: Path,
        language: str = "ja",
        initial_prompt: Optional[str] = None,
    ) -> list[TranscriptSegment]:
        """
        Transcribe audio file to text segments.

        Args:
            audio_path: Path to audio file (wav, mp3, etc.)
            language: Target language code ("ja" for Japanese)
            initial_prompt: Override default terminology prompt

        Returns:
            List of TranscriptSegment with timing information
        """
        prompt = initial_prompt or self.terms_prompt

        segments, info = self.model.transcribe(
            str(audio_path),
            language=language,
            initial_prompt=prompt,
            vad_filter=True,  # Filter silence
            vad_parameters=dict(
                min_silence_duration_ms=500,
                speech_pad_ms=200,
            ),
        )

        logger.info(f"Detected language: {info.language} ({info.language_probability:.2%})")

        return self._convert_segments(segments)

    def transcribe_stream(
        self,
        audio_generator: Iterator[bytes],
        sample_rate: int = 16000,
        language: str = "ja",
    ) -> Iterator[TranscriptSegment]:
        """
        Transcribe streaming audio (future: real-time support).

        Note: Faster-Whisper doesn't natively support streaming.
        This is a placeholder for chunked processing.
        """
        # TODO: Implement chunked streaming transcription
        raise NotImplementedError(
            "Streaming transcription not yet implemented. Use transcribe_file()."
        )

    def _convert_segments(
        self, segments: Iterator[Segment]
    ) -> list[TranscriptSegment]:
        """Convert Whisper segments to our schema."""
        results = []

        for segment in segments:
            # Create transcript segment (speaker will be filled by diarization)
            ts = TranscriptSegment(
                time_offset=segment.start,
                speaker_id="unknown",  # To be filled by diarization
                content=segment.text.strip(),
                sentiment=Sentiment.NEUTRAL,  # To be filled by post-processing
                confidence=segment.avg_logprob,
            )
            results.append(ts)

        return results


class WhisperPostProcessor:
    """
    Post-process Whisper transcripts with LLM.

    Fixes transcription errors, normalizes terminology,
    and adds sentiment classification.
    """

    SENTIMENT_KEYWORDS = {
        Sentiment.PANIC: [
            "やばい", "まずい", "逃げ", "助け", "無理", "死",
            "落ち", "やられ", "きつい", "終わ",
        ],
        Sentiment.POSITIVE: [
            "ナイス", "いいね", "ありがと", "完璧", "勝ち",
            "倒した", "クリア", "取れ", "いける",
        ],
        Sentiment.NEGATIVE: [
            "違う", "ダメ", "なんで", "ミス", "負け",
            "しまった", "失敗", "遅い",
        ],
    }

    def classify_sentiment(self, text: str) -> Sentiment:
        """Simple keyword-based sentiment classification."""
        text_lower = text.lower()

        for sentiment, keywords in self.SENTIMENT_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                return sentiment

        return Sentiment.NEUTRAL

    def is_useful_callout(self, text: str) -> bool:
        """Determine if the callout contains useful tactical information."""
        # Useful callouts typically contain:
        # - Numbers (enemy counts)
        # - Location names
        # - Action words (push, rotate, etc.)
        useful_indicators = [
            "人", "枚", "ショート", "ロング", "メイン", "サイト",
            "プッシュ", "ローテ", "カバー", "セット", "スモーク",
            "フラッシュ", "ウルト", "敵", "味方", "落ち", "残り",
        ]

        return any(ind in text for ind in useful_indicators) or len(text) > 10

    def process_transcript(
        self, segments: list[TranscriptSegment]
    ) -> list[TranscriptSegment]:
        """Add sentiment and usefulness tags to transcript segments."""
        for segment in segments:
            segment.sentiment = self.classify_sentiment(segment.content)
            segment.is_useful = self.is_useful_callout(segment.content)

        return segments
