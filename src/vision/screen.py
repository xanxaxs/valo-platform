"""
Screen Capture Utilities

Cross-platform screen capture using mss library.
"""

from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from mss import mss
from PIL import Image


class ScreenCapture:
    """Screen capture utility for Valorant game window."""

    def __init__(self, monitor_index: int = 1):
        """
        Initialize screen capture.

        Args:
            monitor_index: Monitor to capture (0=all, 1=primary, 2+=secondary)
        """
        self.monitor_index = monitor_index
        self._sct = mss()

    @property
    def monitor(self) -> dict:
        """Get monitor dimensions."""
        return self._sct.monitors[self.monitor_index]

    def capture_full(self) -> np.ndarray:
        """Capture full screen as numpy array (BGR format for OpenCV)."""
        screenshot = self._sct.grab(self.monitor)
        img = np.array(screenshot)
        # Convert BGRA to BGR
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

    def capture_region(
        self, x: int, y: int, width: int, height: int
    ) -> np.ndarray:
        """
        Capture specific region of screen.

        Args:
            x: Left position
            y: Top position
            width: Region width
            height: Region height

        Returns:
            numpy array in BGR format
        """
        region = {
            "left": self.monitor["left"] + x,
            "top": self.monitor["top"] + y,
            "width": width,
            "height": height,
        }
        screenshot = self._sct.grab(region)
        img = np.array(screenshot)
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

    def capture_timer_region(self) -> np.ndarray:
        """Capture the timer region (top center of screen)."""
        # Timer is typically at top center, ~200px wide
        screen_width = self.monitor["width"]
        timer_width = 200
        timer_height = 60
        x = (screen_width - timer_width) // 2
        return self.capture_region(x, 0, timer_width, timer_height)

    def capture_killfeed_region(self) -> np.ndarray:
        """Capture the kill feed region (top right of screen)."""
        # Kill feed is on the right side
        screen_width = self.monitor["width"]
        killfeed_width = 400
        killfeed_height = 200
        x = screen_width - killfeed_width
        return self.capture_region(x, 50, killfeed_width, killfeed_height)

    def capture_minimap_region(self) -> np.ndarray:
        """Capture the minimap region (top left of screen)."""
        # Minimap is typically in top-left corner
        return self.capture_region(10, 10, 250, 250)

    def capture_center_banner(self) -> np.ndarray:
        """Capture center screen for VICTORY/DEFEAT banners."""
        screen_width = self.monitor["width"]
        screen_height = self.monitor["height"]
        banner_width = 600
        banner_height = 200
        x = (screen_width - banner_width) // 2
        y = (screen_height - banner_height) // 2
        return self.capture_region(x, y, banner_width, banner_height)

    def save_screenshot(
        self, frame: np.ndarray, path: Path, prefix: str = "screenshot"
    ) -> Path:
        """
        Save frame as PNG file.

        Args:
            frame: numpy array (BGR format)
            path: Directory to save to
            prefix: Filename prefix

        Returns:
            Path to saved file
        """
        from datetime import datetime

        path.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = path / f"{prefix}_{timestamp}.png"
        cv2.imwrite(str(filename), frame)
        return filename

    @staticmethod
    def frame_to_bytes(frame: np.ndarray, format: str = "png") -> bytes:
        """Convert numpy frame to bytes for API upload."""
        # Convert BGR to RGB for PIL
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(rgb_frame)

        from io import BytesIO

        buffer = BytesIO()
        img.save(buffer, format=format.upper())
        return buffer.getvalue()

    def close(self) -> None:
        """Clean up resources."""
        self._sct.close()

    def __enter__(self) -> "ScreenCapture":
        return self

    def __exit__(self, *args) -> None:
        self.close()
