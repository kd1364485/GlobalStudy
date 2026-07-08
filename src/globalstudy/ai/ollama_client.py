"""Ollama API クライアント実装。

/api/chat（非ストリーミング）でテキスト生成を行う。
qwen3 系の思考モード（<think> タグ）は設定で制御し、
残留した場合も除去して返す。
"""

import re

import requests

from globalstudy.ai.base import LlmClient, LlmError
from globalstudy.config import Config
from globalstudy.utils.logger import get_logger

logger = get_logger(__name__)

_THINK_TAG_PATTERN = re.compile(r"<think>.*?</think>\s*", re.DOTALL)
_AVAILABILITY_TIMEOUT_SECONDS = 3


class OllamaClient(LlmClient):
    """Ollama サーバーと通信する LLM クライアント。"""

    def __init__(self, config: Config) -> None:
        self._config = config.llm

    def is_available(self) -> bool:
        try:
            response = requests.get(
                f"{self._config.base_url}/api/tags",
                timeout=_AVAILABILITY_TIMEOUT_SECONDS,
            )
            return response.ok
        except requests.RequestException:
            return False

    def generate(self, prompt: str) -> str:
        payload = {
            "model": self._config.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "think": self._config.enable_thinking,
        }
        logger.debug("Ollama へ送信 (model=%s, %d文字)", self._config.model, len(prompt))

        try:
            response = requests.post(
                f"{self._config.base_url}/api/chat",
                json=payload,
                timeout=self._config.timeout_seconds,
            )
            response.raise_for_status()
        except requests.ConnectionError as exc:
            raise LlmError(
                f"Ollama へ接続できません（{self._config.base_url}）。"
                "Ollama が起動しているか確認してください。"
            ) from exc
        except requests.Timeout as exc:
            raise LlmError(
                f"Ollama の応答がタイムアウトしました（{self._config.timeout_seconds}秒）。"
            ) from exc
        except requests.RequestException as exc:
            raise LlmError(f"Ollama へのリクエストに失敗しました: {exc}") from exc

        return self._extract_content(response.json())

    @staticmethod
    def _extract_content(body: dict) -> str:
        try:
            content = body["message"]["content"]
        except (KeyError, TypeError) as exc:
            raise LlmError(f"Ollama の応答形式が不正です: {body}") from exc

        content = _THINK_TAG_PATTERN.sub("", content).strip()
        logger.debug("Ollama から受信 (%d文字)", len(content))
        return content
