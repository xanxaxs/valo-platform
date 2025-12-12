"""
Synchronized Audio Recorder.

Records audio automatically synchronized with match events.
Handles:
- Starting recording when match starts
- Splitting audio by rounds
- Stopping recording when match ends
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

import numpy as np

try:
    import sounddevice as sd
    import soundfile as sf
    AUDIO_AVAILABLE = True
except ImportError:
    AUDIO_AVAILABLE = False

from sqlalchemy.orm import Session

from ..db.models import AudioSegment

logger = logging.getLogger(__name__)


@dataclass
class RecordingConfig:
    """Configuration for audio recording."""
    
    sample_rate: int = 16000
    channels: int = 1
    dtype: str = "float32"
    device: Optional[str] = None  # None = default device
    buffer_duration: float = 0.5  # seconds per buffer


class SyncRecorder:
    """
    Synchronized audio recorder for match tracking.
    
    Automatically records audio when matches start and creates
    audio segments aligned with match timeline.
    """
    
    def __init__(
        self,
        output_dir: Path,
        config: Optional[RecordingConfig] = None,
        session: Optional[Session] = None,
    ):
        """
        Initialize synchronized recorder.
        
        Args:
            output_dir: Directory to save audio files
            config: Recording configuration
            session: Optional database session for saving segments
        """
        if not AUDIO_AVAILABLE:
            logger.warning("Audio recording unavailable: sounddevice/soundfile not installed")
        
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.config = config or RecordingConfig()
        self.session = session
        
        # Recording state
        self._is_recording = False
        self._match_id: Optional[str] = None
        self._match_start_time: Optional[datetime] = None
        self._current_round: int = 0
        
        # Audio data
        self._audio_buffer: list[np.ndarray] = []
        self._round_start_index: int = 0
        self._stream: Optional["sd.InputStream"] = None
        
        # Callbacks
        self._on_segment_saved: Optional[Callable[[AudioSegment], None]] = None
        
        # Saved segments info
        self._segments: list[AudioSegment] = []
    
    @property
    def is_recording(self) -> bool:
        """Check if currently recording."""
        return self._is_recording
    
    @property
    def recording_duration(self) -> float:
        """Get current recording duration in seconds."""
        if not self._is_recording or not self._audio_buffer:
            return 0.0
        
        total_samples = sum(len(buf) for buf in self._audio_buffer)
        return total_samples / self.config.sample_rate
    
    def set_on_segment_saved(self, callback: Callable[[AudioSegment], None]) -> None:
        """Set callback for when a segment is saved."""
        self._on_segment_saved = callback
    
    # ============================================
    # Recording Control
    # ============================================
    
    def _resolve_device_id(self, device_name: Optional[str]) -> Optional[int]:
        """
        Resolve device name to device ID.
        
        Prioritizes WASAPI > DirectSound > MME backends.
        
        Args:
            device_name: Device name to search for
            
        Returns:
            Device ID (int) or None if not found
        """
        if device_name is None:
            return None
        
        if not AUDIO_AVAILABLE:
            return None
        
        # Search for matching devices, prioritize by backend
        matches = []
        for i, dev in enumerate(sd.query_devices()):
            if dev["max_input_channels"] > 0 and device_name.lower() in dev["name"].lower():
                # Determine backend priority (WASAPI > DirectSound > MME)
                name = dev["name"]
                if "WASAPI" in name:
                    priority = 0
                elif "DirectSound" in name:
                    priority = 1
                else:  # MME or other
                    priority = 2
                matches.append((priority, i, dev["name"]))
        
        if not matches:
            logger.warning(f"No input device found matching: {device_name}")
            return None
        
        # Sort by priority and return the best match
        matches.sort(key=lambda x: x[0])
        best_match = matches[0]
        logger.info(f"Selected audio device: [{best_match[1]}] {best_match[2]}")
        return best_match[1]
    
    def start_recording(self, match_id: str) -> bool:
        """
        Start recording for a match.
        
        Args:
            match_id: ID of the match being recorded
            
        Returns:
            True if recording started successfully
        """
        if not AUDIO_AVAILABLE:
            logger.error("Cannot start recording: audio libraries not available")
            return False
        
        if self._is_recording:
            logger.warning("Recording already in progress")
            return False
        
        self._match_id = match_id
        self._match_start_time = datetime.now()
        self._current_round = 0
        self._audio_buffer = []
        self._round_start_index = 0
        self._segments = []
        
        try:
            # Resolve device name to ID (handles multiple backends)
            device_id = self._resolve_device_id(self.config.device)
            
            # Create input stream
            self._stream = sd.InputStream(
                samplerate=self.config.sample_rate,
                channels=self.config.channels,
                dtype=self.config.dtype,
                device=device_id,  # Use resolved ID instead of name
                callback=self._audio_callback,
                blocksize=int(self.config.sample_rate * self.config.buffer_duration),
            )
            self._stream.start()
            self._is_recording = True
            
            logger.info(f"Started recording for match {match_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start recording: {e}")
            return False
    
    def stop_recording(self) -> Optional[Path]:
        """
        Stop recording and save the full match audio.
        
        Returns:
            Path to the saved audio file, or None if failed
        """
        if not self._is_recording:
            return None
        
        self._is_recording = False
        
        # Stop stream
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        
        # Save remaining audio as final segment
        if self._audio_buffer:
            return self._save_current_audio(is_final=True)
        
        return None
    
    def mark_round_start(self, round_number: int) -> None:
        """
        Mark the start of a new round.
        
        Saves the previous round's audio and starts a new segment.
        
        Args:
            round_number: Round number starting
        """
        if not self._is_recording:
            return
        
        # Save previous round's audio if any
        if self._current_round > 0 and self._audio_buffer:
            self._save_round_audio(self._current_round)
        
        self._current_round = round_number
        self._round_start_index = len(self._audio_buffer)
        
        logger.debug(f"Round {round_number} started, audio index: {self._round_start_index}")
    
    def mark_round_end(self, round_number: int) -> Optional[Path]:
        """
        Mark the end of a round and save its audio.
        
        Args:
            round_number: Round number ending
            
        Returns:
            Path to saved round audio file
        """
        if not self._is_recording:
            return None
        
        return self._save_round_audio(round_number)
    
    # ============================================
    # Audio Processing
    # ============================================
    
    def _audio_callback(
        self,
        indata: np.ndarray,
        frames: int,
        time_info: dict,
        status: sd.CallbackFlags,
    ) -> None:
        """Callback for audio stream."""
        if status:
            logger.warning(f"Audio callback status: {status}")
        
        if self._is_recording:
            # Store a copy of the audio data
            self._audio_buffer.append(indata.copy())
    
    def _save_current_audio(self, is_final: bool = False) -> Optional[Path]:
        """
        Save current audio buffer to file.
        
        Args:
            is_final: Whether this is the final save (full match)
            
        Returns:
            Path to saved file
        """
        if not self._audio_buffer:
            return None
        
        # Concatenate all audio
        audio_data = np.concatenate(self._audio_buffer, axis=0)
        
        # Generate filename
        if is_final:
            filename = f"{self._match_id}_full.wav"
        else:
            filename = f"{self._match_id}_round_{self._current_round}.wav"
        
        filepath = self.output_dir / filename
        
        try:
            sf.write(
                filepath,
                audio_data,
                self.config.sample_rate,
                subtype="PCM_16",
            )
            
            # Calculate timing
            duration = len(audio_data) / self.config.sample_rate
            end_offset = self.recording_duration
            start_offset = end_offset - duration
            
            # Create database record if session available
            segment = None
            if self.session:
                segment = AudioSegment(
                    match_id=self._match_id,
                    round_number=None if is_final else self._current_round,
                    file_path=str(filepath),
                    start_offset=start_offset,
                    end_offset=end_offset,
                    duration=duration,
                    sample_rate=self.config.sample_rate,
                    channels=self.config.channels,
                )
                self.session.add(segment)
                self.session.commit()
                self._segments.append(segment)
                
                if self._on_segment_saved:
                    self._on_segment_saved(segment)
            
            logger.info(f"Saved audio: {filepath} ({duration:.1f}s)")
            return filepath
            
        except Exception as e:
            logger.error(f"Failed to save audio: {e}")
            return None
    
    def _save_round_audio(self, round_number: int) -> Optional[Path]:
        """
        Save audio for a specific round.
        
        Args:
            round_number: Round to save
            
        Returns:
            Path to saved file
        """
        if self._round_start_index >= len(self._audio_buffer):
            return None
        
        # Get audio from round start to now
        round_buffers = self._audio_buffer[self._round_start_index:]
        if not round_buffers:
            return None
        
        audio_data = np.concatenate(round_buffers, axis=0)
        
        # Generate filename
        filename = f"{self._match_id}_round_{round_number}.wav"
        filepath = self.output_dir / filename
        
        try:
            sf.write(
                filepath,
                audio_data,
                self.config.sample_rate,
                subtype="PCM_16",
            )
            
            # Calculate timing
            duration = len(audio_data) / self.config.sample_rate
            
            # Calculate start offset based on all previous audio
            previous_samples = sum(
                len(buf) for buf in self._audio_buffer[:self._round_start_index]
            )
            start_offset = previous_samples / self.config.sample_rate
            end_offset = start_offset + duration
            
            # Create database record if session available
            segment = None
            if self.session:
                segment = AudioSegment(
                    match_id=self._match_id,
                    round_number=round_number,
                    file_path=str(filepath),
                    start_offset=start_offset,
                    end_offset=end_offset,
                    duration=duration,
                    sample_rate=self.config.sample_rate,
                    channels=self.config.channels,
                )
                self.session.add(segment)
                self.session.commit()
                self._segments.append(segment)
                
                if self._on_segment_saved:
                    self._on_segment_saved(segment)
            
            logger.info(f"Saved round {round_number} audio: {filepath} ({duration:.1f}s)")
            return filepath
            
        except Exception as e:
            logger.error(f"Failed to save round audio: {e}")
            return None
    
    def get_saved_segments(self) -> list[AudioSegment]:
        """Get all saved audio segments for the current match."""
        return self._segments.copy()
    
    # ============================================
    # Utility Methods
    # ============================================
    
    @staticmethod
    def list_audio_devices() -> list[dict]:
        """List available audio input devices."""
        if not AUDIO_AVAILABLE:
            return []
        
        devices = []
        for i, device in enumerate(sd.query_devices()):
            if device["max_input_channels"] > 0:
                devices.append({
                    "index": i,
                    "name": device["name"],
                    "channels": device["max_input_channels"],
                    "sample_rate": device["default_samplerate"],
                })
        return devices
    
    @staticmethod
    def get_default_device() -> Optional[dict]:
        """Get default input device info."""
        if not AUDIO_AVAILABLE:
            return None
        
        try:
            device_id = sd.default.device[0]
            if device_id is not None:
                device = sd.query_devices(device_id)
                return {
                    "index": device_id,
                    "name": device["name"],
                    "channels": device["max_input_channels"],
                    "sample_rate": device["default_samplerate"],
                }
        except Exception:
            pass
        return None

