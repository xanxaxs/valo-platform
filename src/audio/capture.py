"""
Audio Capture Module

Captures audio from system devices or files.
"""

import logging
from pathlib import Path
from typing import Optional, Generator
from dataclasses import dataclass
from datetime import datetime

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class AudioChunk:
    """Captured audio chunk with metadata."""

    data: np.ndarray
    sample_rate: int
    timestamp: datetime
    duration_seconds: float


class AudioCapture:
    """
    Audio capture utility.

    Supports file-based input and system audio capture
    (when virtual audio device is configured).
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        device_name: Optional[str] = None,
    ):
        """
        Initialize audio capture.

        Args:
            sample_rate: Target sample rate (16000 for Whisper)
            channels: Number of audio channels (1 = mono)
            device_name: Audio input device name (optional)
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.device_name = device_name
        self._device_id: Optional[int] = None

        if device_name:
            self._find_device()

    def _find_device(self) -> None:
        """Find audio device by name."""
        try:
            import sounddevice as sd

            devices = sd.query_devices()
            for i, dev in enumerate(devices):
                if self.device_name.lower() in dev["name"].lower():
                    if dev["max_input_channels"] > 0:
                        self._device_id = i
                        logger.info(f"Found audio device: {dev['name']} (id={i})")
                        return

            logger.warning(f"Audio device not found: {self.device_name}")

        except Exception as e:
            logger.warning(f"Failed to query audio devices: {e}")

    def load_file(self, audio_path: Path) -> AudioChunk:
        """
        Load audio from file.

        Args:
            audio_path: Path to audio file

        Returns:
            AudioChunk with audio data
        """
        import soundfile as sf

        data, original_sr = sf.read(str(audio_path))

        # Convert to mono if stereo
        if len(data.shape) > 1:
            data = data.mean(axis=1)

        # Resample if needed
        if original_sr != self.sample_rate:
            data = self._resample(data, original_sr, self.sample_rate)

        duration = len(data) / self.sample_rate

        return AudioChunk(
            data=data.astype(np.float32),
            sample_rate=self.sample_rate,
            timestamp=datetime.now(),
            duration_seconds=duration,
        )

    def _resample(
        self, audio: np.ndarray, src_rate: int, dst_rate: int
    ) -> np.ndarray:
        """Resample audio to target sample rate."""
        import scipy.signal as signal

        duration = len(audio) / src_rate
        target_length = int(duration * dst_rate)
        return signal.resample(audio, target_length)

    def capture_stream(
        self,
        duration_seconds: float,
        chunk_seconds: float = 5.0,
    ) -> Generator[AudioChunk, None, None]:
        """
        Capture audio stream from device.

        Args:
            duration_seconds: Total capture duration
            chunk_seconds: Size of each chunk

        Yields:
            AudioChunk for each captured segment
        """
        try:
            import sounddevice as sd

            chunk_samples = int(chunk_seconds * self.sample_rate)
            total_samples = int(duration_seconds * self.sample_rate)
            captured = 0

            while captured < total_samples:
                remaining = min(chunk_samples, total_samples - captured)

                data = sd.rec(
                    remaining,
                    samplerate=self.sample_rate,
                    channels=self.channels,
                    device=self._device_id,
                    dtype=np.float32,
                )
                sd.wait()

                yield AudioChunk(
                    data=data.flatten(),
                    sample_rate=self.sample_rate,
                    timestamp=datetime.now(),
                    duration_seconds=remaining / self.sample_rate,
                )

                captured += remaining

        except ImportError:
            logger.error("sounddevice not available for audio capture")
            raise
        except Exception as e:
            logger.error(f"Audio capture failed: {e}")
            raise

    def save_chunk(self, chunk: AudioChunk, output_path: Path) -> Path:
        """Save audio chunk to file."""
        import soundfile as sf

        output_path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(output_path), chunk.data, chunk.sample_rate)
        return output_path

    @staticmethod
    def list_devices() -> list[dict]:
        """List available audio devices."""
        try:
            import sounddevice as sd

            devices = sd.query_devices()
            return [
                {
                    "id": i,
                    "name": dev["name"],
                    "input_channels": dev["max_input_channels"],
                    "output_channels": dev["max_output_channels"],
                }
                for i, dev in enumerate(devices)
            ]
        except Exception as e:
            logger.warning(f"Failed to list devices: {e}")
            return []
