"""
Valorant Lockfile Reader.

Reads the Valorant lockfile to get local API connection details.
"""

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Default lockfile path on Windows
DEFAULT_LOCKFILE_PATH = Path(os.environ.get("LOCALAPPDATA", "")) / "Riot Games" / "Riot Client" / "Config" / "lockfile"


@dataclass
class LockfileData:
    """Data from Valorant lockfile."""
    
    name: str
    pid: int
    port: int
    password: str
    protocol: str
    
    @property
    def auth_header(self) -> str:
        """Get Basic auth header value."""
        import base64
        credentials = f"riot:{self.password}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded}"
    
    @property
    def base_url(self) -> str:
        """Get base URL for local API."""
        return f"{self.protocol}://127.0.0.1:{self.port}"


class LockfileReader:
    """
    Reads and parses the Valorant lockfile.
    
    The lockfile contains connection details for the local Valorant API.
    """
    
    def __init__(self, lockfile_path: Optional[Path] = None):
        """
        Initialize lockfile reader.
        
        Args:
            lockfile_path: Custom path to lockfile (uses default if None)
        """
        self.lockfile_path = lockfile_path or DEFAULT_LOCKFILE_PATH
    
    def read(self) -> Optional[LockfileData]:
        """
        Read and parse the lockfile.
        
        Returns:
            LockfileData if successful, None if file doesn't exist or can't be read
        """
        if not self.lockfile_path.exists():
            logger.debug(f"Lockfile not found: {self.lockfile_path}")
            return None
        
        try:
            content = self.lockfile_path.read_text(encoding="utf-8")
            parts = content.strip().split(":")
            
            if len(parts) != 5:
                logger.error(f"Invalid lockfile format: {content}")
                return None
            
            return LockfileData(
                name=parts[0],
                pid=int(parts[1]),
                port=int(parts[2]),
                password=parts[3],
                protocol=parts[4],
            )
            
        except Exception as e:
            logger.error(f"Failed to read lockfile: {e}")
            return None
    
    def is_available(self) -> bool:
        """Check if lockfile exists (Valorant is running)."""
        return self.lockfile_path.exists()
    
    def wait_for_lockfile(self, timeout: float = 60.0, interval: float = 1.0) -> Optional[LockfileData]:
        """
        Wait for lockfile to become available.
        
        Args:
            timeout: Maximum time to wait in seconds
            interval: Check interval in seconds
            
        Returns:
            LockfileData when available, None if timeout
        """
        import time
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            data = self.read()
            if data:
                return data
            time.sleep(interval)
        
        return None

