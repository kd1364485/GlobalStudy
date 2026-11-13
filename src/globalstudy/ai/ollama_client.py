"""Ollama API クライアント実装。

テキストLLM（qwen3 等）との通信を行う。
共通処理は BaseOllamaClient に委譲し、プロンプト送信・ストリーミング生成を提供する。
"""

from collections.abc import Iterator

from globalstudy.ai.base import LlmClient, LlmError
from globalstudy.ai.base_ollama_client import BaseOllamaClient, OllamaApiError
from globalstudy.config import Config
from globalstudy.utils.logger import get_logger

logger = get_logger(__name__)


class OllamaClient(LlmClient, BaseOllamaClient):
    """Ollama サーバーと通信する LLM クライアント。

    LlmClient インターフェースを実装しつつ、BaseOllamaClient の
    共通通信処理を継承する。このクラスではテキストのみの
    ペイロード構築と、OllamaApiError → LlmError の変換のみを担当する。
    """

    def __init__(self, config: Config, llm_config=None) -> None:
        """クライアントを初期化する。

        Args:
            config: アプリ設定。
            llm_config: 使用する LlmConfig の上書き（省略時は config.llm）。
                オーバーレイ翻訳など、用途別に軽量モデルへ
                切り替える場合に指定する。
        """
        # LLM設定（base_url, model, timeout, keep_alive, enable_thinking）
        self._config = llm_config or config.llm

    @property
    def _base_url(self) -> str:
        return self._config.base_url

    @property
    def _model(self) -> str:
        return self._config.model

    @property
    def _timeout_seconds(self) -> int:
        return self._config.timeout_seconds

    def is_available(self) -> bool:
        """Ollama サーバーへ接続可能かを返す。"""
        return self._check_available()

    def generate(self, prompt: str) -> str:
        """プロンプトを送信し、生成テキストを一括で返す。

        Args:
            prompt: LLMへ送信するプロンプト文字列。

        Returns:
            LLMが生成したテキスト（思考タグ除去済み）。

        Raises:
            LlmError: 接続失敗・タイムアウト・不正応答の場合。
        """
        payload = {
            "model": self._config.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "think": self._config.enable_thinking,
            "keep_alive": self._config.keep_alive,
        }
        logger.debug("Ollama へ送信 (model=%s, %d文字)", self._config.model, len(prompt))
        try:
            return self._generate(payload)
        except OllamaApiError as exc:
            raise LlmError(str(exc)) from exc

    def generate_stream(self, prompt: str) -> Iterator[str]:
        """ストリーミングでテキストを生成し、チャンクを逐次返す。

        Args:
            prompt: LLMへ送信するプロンプト文字列。

        Yields:
            生成されたテキストの部分文字列（思考タグ除去済み）。

        Raises:
            LlmError: 接続失敗・タイムアウト・不正応答の場合。
        """
        payload = {
            "model": self._config.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": True,
            "think": self._config.enable_thinking,
            "keep_alive": self._config.keep_alive,
        }
        logger.debug("Ollama へストリーミング送信 (model=%s, %d文字)", self._config.model, len(prompt))
        try:
            yield from self._generate_stream(payload)
        except OllamaApiError as exc:
            raise LlmError(str(exc)) from exc
