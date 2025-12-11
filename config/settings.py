"""
Configuration settings for Valorant Tracker.

Loads settings from environment variables and .env file.
"""

import os
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class AudioSettings(BaseSettings):
    """Audio recording settings."""
    
    device_name: Optional[str] = Field(default=None, alias="AUDIO_DEVICE_NAME")
    sample_rate: int = Field(default=16000, alias="AUDIO_SAMPLE_RATE")
    channels: int = 1
    
    class Config:
        env_prefix = "AUDIO_"


class WhisperSettings(BaseSettings):
    """Whisper speech recognition settings."""
    
    model: str = Field(default="base", alias="WHISPER_MODEL")
    device: str = Field(default="cuda", alias="WHISPER_DEVICE")
    compute_type: str = Field(default="float16", alias="WHISPER_COMPUTE_TYPE")
    
    class Config:
        env_prefix = "WHISPER_"


class LMStudioSettings(BaseSettings):
    """LM Studio settings for AI coach."""
    
    url: str = Field(default="http://localhost:1234/v1", alias="LM_STUDIO_URL")
    model: str = Field(default="llama-3.1-8b-instruct", alias="LM_STUDIO_MODEL")
    
    class Config:
        env_prefix = "LM_STUDIO_"


class DeepSeekSettings(BaseSettings):
    """DeepSeek API settings for vision analysis."""
    
    api_key: Optional[str] = Field(default=None, alias="DEEPSEEK_API_KEY")
    api_url: str = Field(default="https://api.deepseek.com/v1", alias="DEEPSEEK_API_URL")
    
    class Config:
        env_prefix = "DEEPSEEK_"


class Settings(BaseSettings):
    """Main application settings."""
    
    # Project paths
    project_root: Path = Path(__file__).parent.parent
    
    # Database
    database_path: str = Field(default="data/valorant_tracker.db", alias="DATABASE_PATH")
    
    # Directories
    recordings_dir: str = Field(default="data/recordings", alias="RECORDINGS_DIR")
    output_dir: str = Field(default="data/output", alias="OUTPUT_DIR")
    embeddings_dir: str = "data/embeddings"
    
    # Logging
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    
    # Valorant terms file
    valorant_terms_path: Path = Path(__file__).parent / "valorant_terms.json"
    
    # Nested settings
    audio: AudioSettings = AudioSettings()
    whisper: WhisperSettings = WhisperSettings()
    lm_studio: LMStudioSettings = LMStudioSettings()
    deepseek: DeepSeekSettings = DeepSeekSettings()
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"
    
    @property
    def database_url(self) -> str:
        """Get full database URL."""
        db_path = self.project_root / self.database_path
        return f"sqlite:///{db_path}"
    
    @property
    def recordings_path(self) -> Path:
        """Get full recordings directory path."""
        return self.project_root / self.recordings_dir
    
    @property
    def output_path(self) -> Path:
        """Get full output directory path."""
        return self.project_root / self.output_dir
    
    def ensure_directories(self) -> None:
        """Create required directories if they don't exist."""
        dirs = [
            self.project_root / self.recordings_dir,
            self.project_root / self.output_dir,
            self.project_root / self.embeddings_dir,
            self.project_root / "data",
        ]
        for dir_path in dirs:
            dir_path.mkdir(parents=True, exist_ok=True)


# Global settings instance
settings = Settings()
