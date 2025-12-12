"""
AI Module for local RAG coaching.

Components:
- Whisper transcription
- ChromaDB knowledge base
- Local LLM client
- Coaching evaluator
"""

from .transcriber import WhisperTranscriber
from .knowledge_base import CoachingKnowledgeBase
from .llm_client import LocalLLMClient
from .coach import CoachService

__all__ = [
    "WhisperTranscriber",
    "CoachingKnowledgeBase", 
    "LocalLLMClient",
    "CoachService",
]

