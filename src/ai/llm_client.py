"""
Local LLM Client.

Supports LM Studio, Ollama, and OpenAI-compatible APIs.
"""

import json
import logging
from dataclasses import dataclass
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    """Response from LLM."""
    content: str
    model: str
    tokens_used: int = 0
    
    def to_json(self) -> Optional[dict]:
        """Try to parse content as JSON."""
        try:
            return json.loads(self.content)
        except:
            return None


# System prompt for Valorant coaching
COACHING_SYSTEM_PROMPT = """あなたはValorantのプロコーチです。
チームのコミュニケーションを分析し、具体的で実践的なフィードバックを提供します。

フィードバックのポイント:
- 報告のタイミングと内容
- 情報共有の質
- チーム連携の効率
- 改善可能な具体的ポイント

回答は日本語で、簡潔かつ具体的に行ってください。"""


class LocalLLMClient:
    """
    Client for local LLM inference.
    
    Supports:
    - LM Studio (default port 1234)
    - Ollama (default port 11434)
    - Any OpenAI-compatible API
    """
    
    def __init__(
        self,
        base_url: str = "http://localhost:1234/v1",
        model: str = "local-model",
        api_key: str = "not-needed",
        timeout: int = 120,
    ):
        """
        Initialize LLM client.
        
        Args:
            base_url: API base URL
            model: Model name
            api_key: API key (usually not needed for local)
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout = timeout
        
        logger.info(f"LocalLLMClient initialized: {base_url} ({model})")
    
    async def chat(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> LLMResponse:
        """
        Send a chat completion request.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
            
        Returns:
            LLMResponse object
        """
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    timeout=aiohttp.ClientTimeout(total=self.timeout),
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"LLM request failed: {response.status} - {error_text}")
                        return LLMResponse(
                            content=f"Error: {response.status}",
                            model=self.model,
                        )
                    
                    data = await response.json()
                    
                    content = data["choices"][0]["message"]["content"]
                    tokens = data.get("usage", {}).get("total_tokens", 0)
                    
                    return LLMResponse(
                        content=content,
                        model=self.model,
                        tokens_used=tokens,
                    )
                    
        except aiohttp.ClientError as e:
            logger.error(f"LLM connection error: {e}")
            return LLMResponse(
                content=f"Connection error: {e}",
                model=self.model,
            )
        except Exception as e:
            logger.error(f"LLM request failed: {e}")
            return LLMResponse(
                content=f"Error: {e}",
                model=self.model,
            )
    
    def chat_sync(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> LLMResponse:
        """
        Synchronous version of chat.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
            
        Returns:
            LLMResponse object
        """
        import asyncio
        
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(
            self.chat(prompt, system_prompt, temperature, max_tokens)
        )
    
    async def is_available(self) -> bool:
        """Check if the LLM server is available."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/models",
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as response:
                    return response.status == 200
        except:
            return False


class OllamaClient(LocalLLMClient):
    """
    Client specifically for Ollama.
    
    Uses Ollama's native API format.
    """
    
    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llama3.2",
        timeout: int = 120,
    ):
        """
        Initialize Ollama client.
        
        Args:
            base_url: Ollama API URL
            model: Model name (e.g., llama3.2, mistral, codellama)
            timeout: Request timeout
        """
        super().__init__(base_url=base_url, model=model, timeout=timeout)
    
    async def is_available(self) -> bool:
        """Check if Ollama server is available."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/api/tags",
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as response:
                    return response.status == 200
        except:
            return False
    
    async def chat(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> LLMResponse:
        """Send chat request to Ollama."""
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system_prompt or COACHING_SYSTEM_PROMPT,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self.timeout),
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Ollama request failed: {response.status}")
                        return LLMResponse(content=f"Error: {error_text}", model=self.model)
                    
                    data = await response.json()
                    
                    return LLMResponse(
                        content=data.get("response", ""),
                        model=self.model,
                        tokens_used=data.get("eval_count", 0),
                    )
                    
        except Exception as e:
            logger.error(f"Ollama request failed: {e}")
            return LLMResponse(content=f"Error: {e}", model=self.model)

