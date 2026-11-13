"""VLM（視覚言語モデル）クライアント実装。

Ollama の /api/chat エンドポイントで images を指定して
マルチモーダルモデル（例: llava, minicpm-v）と通信する。
共通処理は BaseOllamaClient に委譲する。
"""

import base64
from collections.abc import Iterator
from pathlib import Path

from globalstudy.ai.base_ollama_client import BaseOllamaClient, OllamaApiError
from globalstudy.config import Config
from globalstudy.utils.logger import get_logger

logger = get_logger(__name__)


class VlmError(Exception):
    """VLM との通信・生成失敗時に送出される例外。

    OllamaApiError を VLM 専用の例外に変換することで、
    呼び出し側が LLM と VLM のエラーを区別できる。
    """


class VlmClient(BaseOllamaClient):
    """Ollama サーバーと通信する VLM（視覚言語モデル）クライアント。

    BaseOllamaClient の共通通信処理を継承し、画像の base64
    エンコードと images フィールドを含むペイロード構築のみを
    追加実装する。OllamaApiError → VlmError の変換も行う。
    """

    def __init__(self, config: Config) -> None:
        # VLM設定（base_url, model, timeout, keep_alive）
        self._config = config.vlm

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
        """VLM バックエンドへ接続可能かを返す。"""
        return self._check_available()

    def analyze(self, image_path: Path, prompt: str) -> str:
        """画像とプロンプトをVLMへ送信し、解析テキストを一括で返す。

        Args:
            image_path: キャプチャ画像のファイルパス。
            prompt: VLMへ送信するプロンプト文字列。

        Returns:
            VLMが生成した解析テキスト（思考タグ除去済み）。

        Raises:
            VlmError: 接続失敗・タイムアウト・不正応答の場合。
        """
        image_b64 = self._encode_image(image_path)
        payload = self._build_payload(prompt, image_b64, stream=False)
        logger.debug(
            "VLM へ送信 (model=%s, image=%s, %d文字)",
            self._config.model,
            image_path.name,
            len(prompt),
        )
        try:
            return self._generate(payload)
        except OllamaApiError as exc:
            raise VlmError(str(exc)) from exc

    def analyze_stream(self, image_path: Path, prompt: str) -> Iterator[str]:
        """画像とプロンプトをVLMへ送信し、解析テキストをチャンク単位で逐次返す。

        Args:
            image_path: キャプチャ画像のファイルパス。
            prompt: VLMへ送信するプロンプト文字列。

        Yields:
            VLMが生成した解析テキストの部分文字列（思考タグ除去済み）。

        Raises:
            VlmError: 接続失敗・タイムアウト・不正応答の場合。
        """
        image_b64 = self._encode_image(image_path)
        payload = self._build_payload(prompt, image_b64, stream=True)
        logger.debug(
            "VLM へストリーミング送信 (model=%s, image=%s, %d文字)",
            self._config.model,
            image_path.name,
            len(prompt),
        )
        try:
            yield from self._generate_stream(payload)
        except OllamaApiError as exc:
            raise VlmError(str(exc)) from exc

    def _build_payload(self, prompt: str, image_b64: str, stream: bool) -> dict:
        """VLM用のAPIリクエストペイロードを構築する。

        LLM用ペイロードとの違い: messages 内に images フィールドを追加し、
        base64エンコードした画像データを含める点。
        """
        return {
            "model": self._config.model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                    "images": [image_b64],
                }
            ],
            "stream": stream,
            "think": False,
            "keep_alive": self._config.keep_alive,
        }

    @staticmethod
    def _encode_image(image_path: Path) -> str:
        """画像ファイルを base64 エンコードして返す。"""
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
