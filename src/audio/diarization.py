"""
Speaker Diarization Module

Identifies speakers using Pyannote and voice embedding matching.
"""

import logging
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


class SpeakerDiarizer:
    """
    Speaker diarization using Pyannote.audio.

    Matches audio segments to registered speaker embeddings
    using cosine similarity.
    """

    def __init__(
        self,
        embeddings_dir: Path,
        model_name: str = "pyannote/embedding",
        similarity_threshold: float = 0.7,
    ):
        """
        Initialize speaker diarizer.

        Args:
            embeddings_dir: Directory containing speaker embeddings
            model_name: Pyannote embedding model
            similarity_threshold: Minimum cosine similarity for speaker match
        """
        self.embeddings_dir = Path(embeddings_dir)
        self.embeddings_dir.mkdir(parents=True, exist_ok=True)
        self.similarity_threshold = similarity_threshold

        self._model = None
        self._pipeline = None
        self._speaker_embeddings: dict[str, np.ndarray] = {}

        # Lazy load models
        self._load_registered_speakers()

    def _ensure_model_loaded(self) -> None:
        """Lazy load Pyannote models."""
        if self._model is not None:
            return

        try:
            from pyannote.audio import Model, Pipeline

            logger.info("Loading Pyannote embedding model...")
            # Note: Requires HuggingFace token for some models
            self._model = Model.from_pretrained("pyannote/embedding")
            logger.info("Pyannote model loaded")

        except ImportError:
            logger.warning("Pyannote not available. Using mock diarization.")
        except Exception as e:
            logger.warning(f"Failed to load Pyannote: {e}")

    def _load_registered_speakers(self) -> None:
        """Load pre-registered speaker embeddings from disk."""
        if not self.embeddings_dir.exists():
            return

        for emb_file in self.embeddings_dir.glob("*.npy"):
            user_id = emb_file.stem
            try:
                embedding = np.load(str(emb_file))
                self._speaker_embeddings[user_id] = embedding
                logger.info(f"Loaded speaker embedding: {user_id}")
            except Exception as e:
                logger.warning(f"Failed to load embedding {emb_file}: {e}")

    def register_speaker(
        self,
        user_id: str,
        audio_path: Path,
        display_name: Optional[str] = None,
    ) -> bool:
        """
        Register a new speaker from audio sample.

        Args:
            user_id: Unique identifier for the speaker
            audio_path: Path to audio sample (5-30 seconds recommended)
            display_name: Human-readable name (optional)

        Returns:
            True if registration successful
        """
        self._ensure_model_loaded()

        if self._model is None:
            logger.error("Model not available for speaker registration")
            return False

        try:
            from pyannote.audio import Inference

            inference = Inference(self._model, window="whole")
            embedding = inference(str(audio_path))

            # Convert to numpy and normalize
            emb_array = np.array(embedding).flatten()
            emb_array = emb_array / np.linalg.norm(emb_array)

            # Save embedding
            emb_path = self.embeddings_dir / f"{user_id}.npy"
            np.save(str(emb_path), emb_array)

            self._speaker_embeddings[user_id] = emb_array
            logger.info(f"Registered speaker: {user_id}")

            return True

        except Exception as e:
            logger.error(f"Speaker registration failed: {e}")
            return False

    def identify_speaker(
        self,
        audio_segment: np.ndarray,
        sample_rate: int = 16000,
    ) -> tuple[str, float]:
        """
        Identify speaker from audio segment.

        Args:
            audio_segment: Audio numpy array
            sample_rate: Audio sample rate

        Returns:
            Tuple of (speaker_id, confidence)
        """
        self._ensure_model_loaded()

        if self._model is None or not self._speaker_embeddings:
            return "unknown", 0.0

        try:
            import torch
            from pyannote.audio import Inference

            # Create temporary audio for inference
            import soundfile as sf
            import tempfile

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                sf.write(tmp.name, audio_segment, sample_rate)

                inference = Inference(self._model, window="whole")
                embedding = inference(tmp.name)

            # Convert and normalize
            query_emb = np.array(embedding).flatten()
            query_emb = query_emb / np.linalg.norm(query_emb)

            # Find best match
            best_match = ("unknown", 0.0)

            for user_id, ref_emb in self._speaker_embeddings.items():
                similarity = np.dot(query_emb, ref_emb)

                if similarity > best_match[1]:
                    best_match = (user_id, float(similarity))

            # Apply threshold
            if best_match[1] < self.similarity_threshold:
                return "unknown", best_match[1]

            return best_match

        except Exception as e:
            logger.error(f"Speaker identification failed: {e}")
            return "unknown", 0.0

    def diarize_audio(
        self, audio_path: Path
    ) -> list[dict]:
        """
        Perform full speaker diarization on audio file.

        Args:
            audio_path: Path to audio file

        Returns:
            List of diarization segments with speaker IDs and timing
        """
        self._ensure_model_loaded()

        if self._pipeline is None:
            try:
                from pyannote.audio import Pipeline

                # Note: Requires HuggingFace token
                self._pipeline = Pipeline.from_pretrained(
                    "pyannote/speaker-diarization-3.1"
                )
                logger.info("Loaded diarization pipeline")
            except Exception as e:
                logger.warning(f"Diarization pipeline unavailable: {e}")
                return []

        try:
            diarization = self._pipeline(str(audio_path))
            segments = []

            for turn, _, speaker in diarization.itertracks(yield_label=True):
                # Match to registered speakers
                # (In production, would use embedding matching here)
                segments.append({
                    "start": turn.start,
                    "end": turn.end,
                    "speaker": speaker,  # e.g., "SPEAKER_00"
                    "duration": turn.end - turn.start,
                })

            return segments

        except Exception as e:
            logger.error(f"Diarization failed: {e}")
            return []

    @property
    def registered_speakers(self) -> list[str]:
        """List of registered speaker IDs."""
        return list(self._speaker_embeddings.keys())
