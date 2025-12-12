"""
Whisper Transcription Service.

Converts audio recordings to text using Faster-Whisper.
Optimized for Valorant voice comms with terminology injection.
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional

logger = logging.getLogger(__name__)


@dataclass
class TranscriptSegment:
    """A single segment of transcribed audio."""
    start: float  # Start time in seconds
    end: float  # End time in seconds
    text: str
    speaker: str = "Unknown"
    confidence: float = 0.0
    
    @property
    def duration(self) -> float:
        return self.end - self.start
    
    def to_dict(self) -> dict:
        return {
            "start": self.start,
            "end": self.end,
            "text": self.text,
            "speaker": self.speaker,
            "confidence": self.confidence,
        }


# Valorant terminology for prompt injection
VALORANT_TERMS = """
Valorant用語: エース, スパイク, 設置, 解除, ラッシュ, リテイク, ローテ, 
CT, Aサイト, Bサイト, Cサイト, ヘブン, ロング, ショート, ミッド, 
フラッシュ, スモーク, モロトフ, ウルト, アビリティ,
ジェット, レイナ, ソーヴァ, オーメン, ブリムストーン, ヴァイパー,
フェニックス, セージ, サイファー, キルジョイ, ブリーチ, スカイ,
レイズ, アストラ, ヨル, チェンバー, ネオン, フェイド, ハーバー, ゲッコー,
デッドロック, アイソ, クローヴ, テホ, ヴァイス,
バンダル, ファントム, オペレーター, シェリフ, ゴースト, クラシック,
エコラウンド, フルバイ, セーブ, ボーナス, ピストルラウンド
"""


class WhisperTranscriber:
    """
    Whisper-based transcription optimized for Valorant voice comms.
    
    Uses Faster-Whisper with CTranslate2 backend for efficient inference.
    """
    
    def __init__(
        self,
        model_size: str = "large-v3-turbo",
        device: str = "cpu",
        compute_type: str = "int8",
        language: str = "ja",
    ):
        """
        Initialize Whisper transcriber.
        
        Args:
            model_size: Model size (tiny, base, small, medium, large-v3-turbo)
            device: "cpu", "cuda", or "auto"
            compute_type: "int8" for CPU, "float16" for GPU
            language: Target language code
        """
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.language = language
        self._model = None
        
        logger.info(f"WhisperTranscriber initialized: {model_size} on {device}")
    
    def _load_model(self):
        """Lazy load the Whisper model."""
        if self._model is None:
            try:
                from faster_whisper import WhisperModel
                
                logger.info(f"Loading Whisper model: {self.model_size}")
                self._model = WhisperModel(
                    self.model_size,
                    device=self.device,
                    compute_type=self.compute_type,
                )
                logger.info("Whisper model loaded successfully")
            except ImportError:
                logger.error("faster-whisper not installed. Run: pip install faster-whisper")
                raise
            except Exception as e:
                logger.error(f"Failed to load Whisper model: {e}")
                raise
    
    def transcribe_file(
        self,
        audio_path: Path,
        initial_prompt: Optional[str] = None,
    ) -> list[TranscriptSegment]:
        """
        Transcribe an audio file.
        
        Args:
            audio_path: Path to audio file (WAV, MP3, etc.)
            initial_prompt: Optional prompt to guide transcription
            
        Returns:
            List of TranscriptSegment objects
        """
        self._load_model()
        
        if not audio_path.exists():
            logger.error(f"Audio file not found: {audio_path}")
            return []
        
        # Build prompt with Valorant terminology
        prompt = VALORANT_TERMS
        if initial_prompt:
            prompt = f"{initial_prompt}\n\n{prompt}"
        
        logger.info(f"Transcribing: {audio_path}")
        
        try:
            segments, info = self._model.transcribe(
                str(audio_path),
                language=self.language,
                initial_prompt=prompt,
                vad_filter=True,  # Voice Activity Detection
                vad_parameters=dict(
                    min_silence_duration_ms=500,
                    speech_pad_ms=200,
                ),
            )
            
            results = []
            for segment in segments:
                results.append(TranscriptSegment(
                    start=segment.start,
                    end=segment.end,
                    text=segment.text.strip(),
                    confidence=segment.avg_logprob if hasattr(segment, 'avg_logprob') else 0.0,
                ))
            
            logger.info(f"Transcribed {len(results)} segments ({info.duration:.1f}s audio)")
            return results
            
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return []
    
    def transcribe_segment(
        self,
        audio_path: Path,
        start_time: float,
        end_time: float,
    ) -> Optional[TranscriptSegment]:
        """
        Transcribe a specific time segment of an audio file.
        
        Args:
            audio_path: Path to audio file
            start_time: Start time in seconds
            end_time: End time in seconds
            
        Returns:
            TranscriptSegment or None
        """
        # For now, transcribe full file and filter
        # TODO: Implement segment extraction for efficiency
        segments = self.transcribe_file(audio_path)
        
        for seg in segments:
            if seg.start >= start_time and seg.end <= end_time:
                return seg
        
        return None

