"""LLM クライアントの抽象インターフェース。

バックエンド（Ollama / 他のローカルLLM等）を差し替え可能にするための境界。
"""

from abc import ABC, abstractmethod


class LlmError(Exception):
    """LLM との通信・生成失敗時に送出される例外。"""


class LlmClient(ABC):
    """LLM クライアントの共通インターフェース。"""

    @abstractmethod
    def is_available(self) -> bool:
        """バックエンドへ接続可能かを返す。"""

    @abstractmethod
    def generate(self, prompt: str) -> str:
        """プロンプトを送信し、生成テキストを返す。

        Raises:
            LlmError: 接続失敗・タイムアウト・不正応答の場合。
        """
