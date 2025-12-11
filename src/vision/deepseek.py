"""
DeepSeek VLM API Client

Sends screenshots to DeepSeek API for detailed vision analysis.
Supports both cloud API and local VLM deployment.
"""

import base64
import logging
from typing import Optional

import httpx

from src.models.schemas import (
    EconomyTag,
    PlayerPosition,
    RoundResult,
    VisionAnalysis,
    VisionMetadata,
    WinCondition,
)

logger = logging.getLogger(__name__)


class DeepSeekVisionClient:
    """
    DeepSeek Vision Language Model client.

    Analyzes Valorant screenshots for round results,
    economy status, and player positions.
    """

    DEFAULT_SYSTEM_PROMPT = """You are a Valorant game analyzer. Analyze the provided screenshot and extract:
1. Round result (WIN/LOSS)
2. Win condition (ELIMINATION/DEFUSE/DETONATE/TIME)
3. Economy status (ECO/FORCE/HALF_BUY/FULL_BUY/THRIFTY/BONUS)
4. Survivor counts (team and enemy)

Respond ONLY in this JSON format:
{
    "result": "WIN" or "LOSS",
    "win_condition": "ELIMINATION" or "DEFUSE" or "DETONATE" or "TIME",
    "economy_tag": "ECO" or "FORCE" or "HALF_BUY" or "FULL_BUY" or "THRIFTY" or "BONUS",
    "survivors_count": 0-5,
    "enemy_survivors": 0-5
}"""

    MINIMAP_SYSTEM_PROMPT = """You are a Valorant minimap analyzer. Extract player positions from the minimap.
For each visible player indicator, provide:
- player_id: "ally_1", "ally_2", etc. or "enemy_1", "enemy_2", etc.
- x: horizontal position (0.0 = left, 1.0 = right)
- y: vertical position (0.0 = top, 1.0 = bottom)
- is_alive: true if the player marker is visible and not crossed out

Respond ONLY in this JSON format:
{
    "positions": [
        {"player_id": "ally_1", "x": 0.3, "y": 0.5, "is_alive": true},
        ...
    ]
}"""

    def __init__(
        self,
        api_key: str,
        api_url: str = "https://api.deepseek.com",
        model: str = "deepseek-vl",
        timeout: float = 30.0,
    ):
        """
        Initialize DeepSeek VLM client.

        Args:
            api_key: DeepSeek API key
            api_url: API base URL (can be local endpoint)
            model: Model name to use
            timeout: Request timeout in seconds
        """
        self.api_key = api_key
        self.api_url = api_url.rstrip("/")
        self.model = model
        self.timeout = timeout

        self._client = httpx.AsyncClient(
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )

    async def analyze_screenshot(
        self, image_bytes: bytes, custom_prompt: Optional[str] = None
    ) -> VisionAnalysis:
        """
        Analyze screenshot for round result and game state.

        Args:
            image_bytes: PNG/JPEG image bytes
            custom_prompt: Override default analysis prompt

        Returns:
            VisionAnalysis with extracted data
        """
        base64_image = base64.b64encode(image_bytes).decode("utf-8")

        messages = [
            {"role": "system", "content": self.DEFAULT_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{base64_image}"
                        },
                    },
                    {
                        "type": "text",
                        "text": custom_prompt or "Analyze this Valorant round end screen.",
                    },
                ],
            },
        ]

        try:
            response = await self._client.post(
                f"{self.api_url}/v1/chat/completions",
                json={
                    "model": self.model,
                    "messages": messages,
                    "max_tokens": 500,
                    "temperature": 0.1,
                },
            )
            response.raise_for_status()
            data = response.json()

            content = data["choices"][0]["message"]["content"]
            return self._parse_vision_response(content)

        except httpx.HTTPStatusError as e:
            logger.error(f"DeepSeek API error: {e.response.status_code}")
            raise
        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            raise

    async def extract_minimap_positions(
        self, image_bytes: bytes
    ) -> list[PlayerPosition]:
        """
        Extract player positions from minimap screenshot.

        Args:
            image_bytes: Minimap PNG/JPEG image bytes

        Returns:
            List of PlayerPosition objects
        """
        base64_image = base64.b64encode(image_bytes).decode("utf-8")

        messages = [
            {"role": "system", "content": self.MINIMAP_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{base64_image}"
                        },
                    },
                    {
                        "type": "text",
                        "text": "Extract all player positions from this Valorant minimap.",
                    },
                ],
            },
        ]

        try:
            response = await self._client.post(
                f"{self.api_url}/v1/chat/completions",
                json={
                    "model": self.model,
                    "messages": messages,
                    "max_tokens": 500,
                    "temperature": 0.1,
                },
            )
            response.raise_for_status()
            data = response.json()

            content = data["choices"][0]["message"]["content"]
            return self._parse_minimap_response(content)

        except Exception as e:
            logger.error(f"Minimap analysis failed: {e}")
            return []

    def _parse_vision_response(self, content: str) -> VisionAnalysis:
        """Parse JSON response from VLM into VisionAnalysis."""
        import json

        # Extract JSON from response (may be wrapped in markdown)
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        try:
            data = json.loads(content.strip())
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse VLM response: {content}")
            # Return default values
            return VisionAnalysis(
                result=RoundResult.LOSS,
                win_condition=WinCondition.ELIMINATION,
                economy_tag=EconomyTag.FULL_BUY,
                vision_metadata=VisionMetadata(survivors_count=0, enemy_survivors=0),
                raw_response=content,
            )

        return VisionAnalysis(
            result=RoundResult(data.get("result", "LOSS")),
            win_condition=WinCondition(data.get("win_condition", "ELIMINATION")),
            economy_tag=EconomyTag(data.get("economy_tag", "FULL_BUY")),
            vision_metadata=VisionMetadata(
                survivors_count=data.get("survivors_count", 0),
                enemy_survivors=data.get("enemy_survivors", 0),
            ),
            raw_response=content,
        )

    def _parse_minimap_response(self, content: str) -> list[PlayerPosition]:
        """Parse JSON response from VLM into PlayerPosition list."""
        import json

        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        try:
            data = json.loads(content.strip())
            positions = data.get("positions", [])
            return [
                PlayerPosition(
                    player_id=p["player_id"],
                    x=p["x"],
                    y=p["y"],
                    is_alive=p.get("is_alive", True),
                )
                for p in positions
            ]
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to parse minimap response: {e}")
            return []

    async def close(self) -> None:
        """Close HTTP client."""
        await self._client.aclose()

    async def __aenter__(self) -> "DeepSeekVisionClient":
        return self

    async def __aexit__(self, *args) -> None:
        await self.close()


class LocalVLMClient(DeepSeekVisionClient):
    """
    Local VLM client for self-hosted vision models.

    Compatible with LM Studio or other OpenAI-compatible endpoints
    that support vision models (e.g., LLaVA, Qwen-VL).
    """

    def __init__(
        self,
        api_url: str = "http://localhost:1234/v1",
        model: str = "local-vlm",
        timeout: float = 60.0,
    ):
        """
        Initialize local VLM client.

        Args:
            api_url: Local server URL (LM Studio default: http://localhost:1234/v1)
            model: Model identifier (depends on loaded model in LM Studio)
            timeout: Request timeout (longer for local inference)
        """
        # No API key needed for local
        super().__init__(
            api_key="local",
            api_url=api_url,
            model=model,
            timeout=timeout,
        )

        # Override client without auth header
        self._client = httpx.AsyncClient(
            timeout=timeout,
            headers={"Content-Type": "application/json"},
        )
