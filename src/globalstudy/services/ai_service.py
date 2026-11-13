"""AI ユースケース。

LLM クライアントの生成と実行を担当する。
"""

from collections.abc import Iterator

from globalstudy.ai.base import LlmClient
from globalstudy.ai.ollama_client import OllamaClient
from globalstudy.config import Config
from globalstudy.utils.logger import get_logger

logger = get_logger(__name__)


class AiService:
    """LLM への問い合わせを提供するサービス。

    LlmClient への委譲とロギングを担当する。
    UI層からはこのサービスのみを利用する。
    """

    def __init__(self, config: Config, client: LlmClient | None = None) -> None:
        # 外部からクライアントを注入可能（テスト用）。未指定時は OllamaClient を生成。
        self._client = client or OllamaClient(config)

    def is_available(self) -> bool:
        """LLM バックエンドが利用可能かを返す。"""
        return self._client.is_available()

    def ask(self, prompt: str) -> str:
        """プロンプトを送信し、応答テキストを返す。

        Raises:
            LlmError: LLM との通信に失敗した場合。
        """
        logger.info("LLM へ問い合わせ中...")
        response = self._client.generate(prompt)
        logger.info("LLM 応答受信（%d 文字）", len(response))
        return response

    def ask_stream(self, prompt: str) -> Iterator[str]:
        """プロンプトを送信し、応答テキストをチャンク単位で逐次返す。

        Raises:
            LlmError: LLM との通信に失敗した場合。
        """
        logger.info("LLM へストリーミング問い合わせ中...")
        yield from self._client.generate_stream(prompt)
