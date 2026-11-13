"""Ollama API クライアントの共通基底クラス。

OllamaClient（テキストLLM）と VlmClient（視覚言語モデル）の
共通処理（API通信・ストリーミング・思考タグ除去・エラーハンドリング）を抽出する。
"""

import json
import re
from collections.abc import Iterator

import requests

from globalstudy.utils.logger import get_logger

logger = get_logger(__name__)

# qwen3系モデルが出力する思考タグ (<think>...</think>) を除去するための正規表現。
# DOTALLフラグにより改行を含む複数行の思考ブロックもマッチする。
_THINK_TAG_PATTERN = re.compile(
    r"\u003cthink\u003e.*?\u003c/think\u003e\s*", re.DOTALL
)

# is_available() でOllamaサーバーの生存確認に使用するタイムアウト秒数。
# 起動時のブロックを防ぐため短めに設定している。
_AVAILABILITY_TIMEOUT_SECONDS = 3

# 思考タグの開始・終了文字列（エスケープシーケンスで表現）
_THINK_OPEN = "\u003cthink\u003e"
_THINK_CLOSE = "\u003c/think\u003e"


class OllamaApiError(Exception):
    """Ollama API との通信・生成失敗時に送出される例外。

    この例外は BaseOllamaClient 内部で使用され、サブクラス
    （OllamaClient / VlmClient）でそれぞれの例外
    （LlmError / VlmError）に変換される。
    """


class BaseOllamaClient:
    """Ollama /api/chat エンドポイントと通信するクライアントの共通基底。

    サブクラスは _base_url / _model / _timeout_seconds プロパティを
    実装し、ペイロードを構築して _generate() / _generate_stream() に渡す。
    共通のHTTP通信・ストリーミング解析・思考タグ除去・エラー処理を提供する。
    """

    def _check_available(self) -> bool:
        """Ollama サーバーへ接続可能か、指定モデルが存在するかを返す。

        /api/tags エンドポイントにGETリクエストを送り、
        インストール済みモデル一覧の中に指定モデルが含まれているか確認する。
        ネットワークエラー時は例外を送出せず False を返す。
        """
        try:
            response = requests.get(
                f"{self._base_url}/api/tags",
                timeout=_AVAILABILITY_TIMEOUT_SECONDS,
            )
            if not response.ok:
                return False
            tags = response.json()
            models = [m.get("name", "") for m in tags.get("models", [])]
            return any(self._model in m for m in models)
        except requests.RequestException:
            return False

    def _post_chat(self, payload: dict, stream: bool = False) -> requests.Response:
        """Ollama /api/chat へ POST リクエストを送信する。

        Args:
            payload: Ollama API のリクエストペイロード（dict）。
            stream: True の場合はストリーミング応答を有効にする。

        Returns:
            requests.Response オブジェクト。

        Raises:
            OllamaApiError: 接続失敗・タイムアウト・HTTPエラーの場合。
        """
        try:
            response = requests.post(
                f"{self._base_url}/api/chat",
                json=payload,
                stream=stream,
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
            return response
        except requests.ConnectionError as exc:
            raise OllamaApiError(
                f"Ollama へ接続できません（{self._base_url}）。"
                "Ollama が起動しているか確認してください。"
            ) from exc
        except requests.Timeout as exc:
            raise OllamaApiError(
                f"Ollama の応答がタイムアウトしました（{self._timeout_seconds}秒）。"
            ) from exc
        except requests.RequestException as exc:
            raise OllamaApiError(f"Ollama へのリクエストに失敗しました: {exc}") from exc

    def _generate(self, payload: dict) -> str:
        """非ストリーミングで生成し、テキストを一括で返す。

        Args:
            payload: stream=False を含むリクエストペイロード。

        Returns:
            生成されたテキスト（思考タグ除去済み）。
        """
        response = self._post_chat(payload, stream=False)
        return self._extract_content(response.json())

    def _generate_stream(self, payload: dict) -> Iterator[str]:
        """ストリーミングで生成し、チャンクを逐次返す。思考タグは除去する。

        Ollama のストリーミング応答は1行ごとにJSONオブジェクトとして
        送られてくる。各チャンクからテキストを抽出し、思考タグ
        で囲まれた部分をスキップして本文のみを yield する。

        Args:
            payload: stream=True を含むリクエストペイロード。

        Yields:
            生成されたテキストの部分文字列（思考タグ除去済み）。
        """
        response = self._post_chat(payload, stream=True)

        # 思考タグの途中かどうかを追跡するフラグ
        in_think = False
        try:
            for line in response.iter_lines(decode_unicode=True):
                if not line:
                    continue
                # 1行のJSONからテキストチャンクを抽出
                chunk = self._extract_stream_chunk(json.loads(line))
                if not chunk:
                    continue
                # 思考タグの開始を検出: 開始タグより前の本文のみ残す
                if _THINK_OPEN in chunk:
                    in_think = True
                    chunk = chunk.split(_THINK_OPEN)[0]
                # 思考タグの終了を検出: 終了タグより後の本文のみ残す
                if _THINK_CLOSE in chunk:
                    in_think = False
                    chunk = chunk.split(_THINK_CLOSE)[1]
                # 思考タグ内のチャンクはスキップ
                if in_think:
                    continue
                if chunk:
                    yield chunk
        except json.JSONDecodeError as exc:
            raise OllamaApiError(
                f"Ollama のストリーミング応答のパースに失敗しました: {exc}"
            ) from exc
        except requests.RequestException as exc:
            raise OllamaApiError(
                f"Ollama のストリーミング中にエラーが発生しました: {exc}"
            ) from exc

    @staticmethod
    def _extract_stream_chunk(body: dict) -> str:
        """ストリーミングの1チャンク（JSONオブジェクト）からテキストを抽出する。

        Ollama のストリーミング応答の各行は {"message": {"content": "..."}}
        という構造を持つ。content が存在しない場合は空文字を返す。
        """
        try:
            return body["message"]["content"]
        except (KeyError, TypeError):
            return ""

    @staticmethod
    def _extract_content(body: dict) -> str:
        """非ストリーミング応答からテキストを抽出し、思考タグを一括除去する。

        非ストリーミングの場合は応答全体が1つのJSONとして返るため、
        正規表現で思考タグを一括除去できる。
        """
        try:
            content = body["message"]["content"]
        except (KeyError, TypeError) as exc:
            raise OllamaApiError(f"Ollama の応答形式が不正です: {body}") from exc
        content = _THINK_TAG_PATTERN.sub("", content).strip()
        logger.debug("Ollama から受信 (%d文字)", len(content))
        return content

    # --- サブクラスが実装するプロパティ ---

    @property
    def _base_url(self) -> str:
        """Ollama サーバーのベースURL（例: http://127.0.0.1:11434）。"""
        raise NotImplementedError

    @property
    def _model(self) -> str:
        """使用するモデル名（例: qwen3:8b, minicpm-v:8b）。"""
        raise NotImplementedError

    @property
    def _timeout_seconds(self) -> int:
        """リクエストのタイムアウト秒数。"""
        raise NotImplementedError
