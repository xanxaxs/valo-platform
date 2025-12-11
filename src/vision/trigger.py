"""
OpenCV Event Detection Triggers

Detects round events (VICTORY/DEFEAT/CLUTCH) and game state changes.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Detected event types."""

    VICTORY = "VICTORY"
    DEFEAT = "DEFEAT"
    CLUTCH = "CLUTCH"
    ROUND_START = "ROUND_START"
    ROUND_END = "ROUND_END"
    KILL_FEED = "KILL_FEED"
    UNKNOWN = "UNKNOWN"


@dataclass
class DetectedEvent:
    """Detected game event."""

    event_type: EventType
    confidence: float
    timestamp: datetime
    frame: Optional[np.ndarray] = None


class RoundEventTrigger:
    """
    OpenCV-based round event detection.

    Uses template matching and color detection to identify
    VICTORY/DEFEAT banners and round state changes.
    """

    # Color ranges for detection (HSV)
    VICTORY_GREEN_LOWER = np.array([35, 100, 100])
    VICTORY_GREEN_UPPER = np.array([85, 255, 255])

    DEFEAT_RED_LOWER = np.array([0, 100, 100])
    DEFEAT_RED_UPPER = np.array([10, 255, 255])

    TIMER_YELLOW_LOWER = np.array([20, 100, 100])
    TIMER_YELLOW_UPPER = np.array([40, 255, 255])

    def __init__(self, templates_dir: Optional[Path] = None):
        """
        Initialize the trigger system.

        Args:
            templates_dir: Directory containing template images for matching
        """
        self.templates_dir = templates_dir
        self.templates: dict[str, np.ndarray] = {}
        self._last_timer_state: Optional[str] = None
        self._last_killfeed_hash: Optional[str] = None

        if templates_dir and templates_dir.exists():
            self._load_templates()

    def _load_templates(self) -> None:
        """Load template images for matching."""
        if not self.templates_dir:
            return

        template_files = {
            "victory": "victory_banner.png",
            "defeat": "defeat_banner.png",
            "clutch": "clutch_banner.png",
        }

        for name, filename in template_files.items():
            path = self.templates_dir / filename
            if path.exists():
                self.templates[name] = cv2.imread(str(path), cv2.IMREAD_COLOR)
                logger.info(f"Loaded template: {name}")

    def detect_banner_by_color(
        self, frame: np.ndarray
    ) -> tuple[Optional[EventType], float]:
        """
        Detect VICTORY/DEFEAT by dominant color in center banner region.

        Args:
            frame: BGR image of center banner area

        Returns:
            Tuple of (event_type, confidence)
        """
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        # Check for victory (green)
        green_mask = cv2.inRange(hsv, self.VICTORY_GREEN_LOWER, self.VICTORY_GREEN_UPPER)
        green_ratio = np.sum(green_mask > 0) / green_mask.size

        # Check for defeat (red)
        red_mask = cv2.inRange(hsv, self.DEFEAT_RED_LOWER, self.DEFEAT_RED_UPPER)
        red_ratio = np.sum(red_mask > 0) / red_mask.size

        # Threshold for detection
        threshold = 0.05  # 5% of pixels

        if green_ratio > threshold and green_ratio > red_ratio:
            return EventType.VICTORY, min(green_ratio * 10, 1.0)
        elif red_ratio > threshold and red_ratio > green_ratio:
            return EventType.DEFEAT, min(red_ratio * 10, 1.0)

        return None, 0.0

    def detect_banner_by_template(
        self, frame: np.ndarray
    ) -> tuple[Optional[EventType], float]:
        """
        Detect events using template matching.

        Args:
            frame: BGR image of center banner area

        Returns:
            Tuple of (event_type, confidence)
        """
        if not self.templates:
            return None, 0.0

        best_match: tuple[Optional[EventType], float] = (None, 0.0)

        for name, template in self.templates.items():
            # Resize template if needed
            if template.shape[0] > frame.shape[0] or template.shape[1] > frame.shape[1]:
                scale = min(
                    frame.shape[0] / template.shape[0],
                    frame.shape[1] / template.shape[1],
                )
                template = cv2.resize(template, None, fx=scale, fy=scale)

            result = cv2.matchTemplate(frame, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(result)

            if max_val > best_match[1]:
                event_type = EventType[name.upper()]
                best_match = (event_type, max_val)

        if best_match[1] > 0.7:  # Confidence threshold
            return best_match

        return None, 0.0

    def detect_event(self, frame: np.ndarray) -> Optional[DetectedEvent]:
        """
        Detect round event from center banner frame.

        Combines color and template matching for robust detection.

        Args:
            frame: BGR image of center banner area

        Returns:
            DetectedEvent if detected, None otherwise
        """
        # Try color detection first (faster)
        event_type, color_conf = self.detect_banner_by_color(frame)

        # If color detection is confident, use it
        if event_type and color_conf > 0.3:
            return DetectedEvent(
                event_type=event_type,
                confidence=color_conf,
                timestamp=datetime.now(),
                frame=frame.copy(),
            )

        # Fall back to template matching
        event_type, template_conf = self.detect_banner_by_template(frame)

        if event_type and template_conf > 0.7:
            return DetectedEvent(
                event_type=event_type,
                confidence=template_conf,
                timestamp=datetime.now(),
                frame=frame.copy(),
            )

        return None

    def detect_timer_color_change(self, timer_frame: np.ndarray) -> bool:
        """
        Detect if timer has changed color (indicating round state change).

        Args:
            timer_frame: BGR image of timer region

        Returns:
            True if color change detected
        """
        hsv = cv2.cvtColor(timer_frame, cv2.COLOR_BGR2HSV)

        # Calculate dominant hue
        hue_hist = cv2.calcHist([hsv], [0], None, [180], [0, 180])
        dominant_hue = np.argmax(hue_hist)

        # Classify timer state
        if 20 <= dominant_hue <= 40:
            current_state = "yellow"
        elif 0 <= dominant_hue <= 10 or 170 <= dominant_hue <= 180:
            current_state = "red"
        elif 100 <= dominant_hue <= 130:
            current_state = "blue"
        else:
            current_state = "unknown"

        # Check for change
        changed = (
            self._last_timer_state is not None
            and self._last_timer_state != current_state
        )
        self._last_timer_state = current_state

        return changed

    def detect_killfeed_change(
        self, current_frame: np.ndarray, prev_frame: Optional[np.ndarray] = None
    ) -> bool:
        """
        Detect changes in kill feed region.

        Args:
            current_frame: Current kill feed image
            prev_frame: Previous kill feed image (optional, uses internal cache)

        Returns:
            True if kill feed has changed
        """
        # Simple hash comparison
        current_hash = self._compute_frame_hash(current_frame)

        if prev_frame is not None:
            prev_hash = self._compute_frame_hash(prev_frame)
            changed = current_hash != prev_hash
        else:
            changed = (
                self._last_killfeed_hash is not None
                and self._last_killfeed_hash != current_hash
            )

        self._last_killfeed_hash = current_hash
        return changed

    @staticmethod
    def _compute_frame_hash(frame: np.ndarray, size: int = 16) -> str:
        """Compute perceptual hash of frame."""
        # Resize and convert to grayscale
        small = cv2.resize(frame, (size, size))
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

        # Compute average
        avg = gray.mean()

        # Create binary hash
        bits = (gray > avg).flatten()
        return "".join("1" if b else "0" for b in bits)
