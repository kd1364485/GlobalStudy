"""VLM 解析ユースケース。

VLM（視覚言語モデル）へ画像を送信し、視覚情報の補助解析を実行する。
OCR翻訳の代替ではなく、図・グラフ・イラストの意味を補足する目的。
"""

from collections.abc import Iterator
from pathlib import Path

from globalstudy.ai.prompts import build_vlm_prompt
from globalstudy.ai.vlm_client import VlmClient
from globalstudy.config import Config
from globalstudy.utils.logger import get_logger

logger = get_logger(__name__)


class VlmAnalysisService:
    """VLM を用いた視覚補助解析を提供するサービス。

    VLMへ画像を送信し、図・グラフ・イラストなどの視覚情報を
    日本語テキストで補足説明する。OCR翻訳の代替ではなく補完が目的。
    """

    def __init__(self, config: Config, client: VlmClient | None = None) -> None:
        # 外部からクライアントを注入可能（テスト用）。未指定時は VlmClient を生成。
        self._client = client or VlmClient(config)

    def is_available(self) -> bool:
        """VLM バックエンドが利用可能かを返す。"""
        return self._client.is_available()

    def analyze(
        self, image_path: Path, source_language: str = "english", target_language: str = "japanese"
    ) -> str:
        """画像をVLMへ送信し、解析テキストを返す。

        Args:
            image_path: キャプチャ画像のファイルパス。
            source_language: 翻訳元言語の表示名。
            target_language: 翻訳先言語の表示名。

        Raises:
            VlmError: VLM との通信に失敗した場合。
        """
        logger.info("VLM 解析開始: %s", image_path)
        prompt = build_vlm_prompt(source_language=source_language, target_language=target_language)
        response = self._client.analyze(image_path, prompt)
        logger.info("VLM 解析完了（%d 文字）", len(response))
        return response

    def analyze_stream(
        self, image_path: Path, source_language: str = "english", target_language: str = "japanese"
    ) -> Iterator[str]:
        """画像をVLMへ送信し、解析テキストをチャンク単位で逐次返す。

        Args:
            image_path: キャプチャ画像のファイルパス。
            source_language: 翻訳元言語の表示名。
            target_language: 翻訳先言語の表示名。

        Raises:
            VlmError: VLM との通信に失敗した場合。
        """
        logger.info("VLM ストリーミング解析開始: %s", image_path)
        prompt = build_vlm_prompt(source_language=source_language, target_language=target_language)
        for chunk in self._client.analyze_stream(image_path, prompt):
            yield chunk
        logger.info("VLM ストリーミング解析完了")
