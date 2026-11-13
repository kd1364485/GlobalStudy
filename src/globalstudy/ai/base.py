"""LLM クライアントの抽象インターフェース。

バックエンド（Ollama / 他のローカルLLM等）を差し替え可能にするための境界。
このモジュールは「LLMとどう通信するか」の契約のみを定義し、
具体的な実装（HTTP通信など）はサブクラスに委ねる。
"""

from collections.abc import Iterator
from abc import ABC, abstractmethod


class LlmError(Exception):
    """LLM との通信・生成失敗時に送出される例外。

    接続エラー・タイムアウト・不正な応答形式など、
    LLMバックエンドに関する全てのエラーをこの例外で包む。
    """


class LlmClient(ABC):
    """LLM クライアントの共通インターフェース。

    具体的な実装（OllamaClient など）はこのクラスを継承し、
    3つの抽象メソッドを実装する。UI層やサービス層はこの
    インターフェースに依存することで、バックエンドを
    意識せずにLLMを利用できる。
    """

    @abstractmethod
    def is_available(self) -> bool:
        """バックエンドへ接続可能かを返す。

        Returns:
            True: 接続可能、False: 接続不可（サーバー未起動など）。
        """

    @abstractmethod
    def generate(self, prompt: str) -> str:
        """プロンプトを送信し、生成テキストを一括で返す。

        Args:
            prompt: LLMへ送信するプロンプト文字列。

        Returns:
            LLMが生成したテキスト。

        Raises:
            LlmError: 接続失敗・タイムアウト・不正応答の場合。
        """

    @abstractmethod
    def generate_stream(self, prompt: str) -> Iterator[str]:
        """プロンプトを送信し、生成テキストをチャンク単位で逐次返す。

        ストリーミングにより、生成完了を待たずに部分的な結果を
        UIに表示できる。リアルタイム性が重要な翻訳などで使用する。

        Args:
            prompt: LLMへ送信するプロンプト文字列。

        Yields:
            生成されたテキストの部分文字列（チャンク）。

        Raises:
            LlmError: 接続失敗・タイムアウト・不正応答の場合。
        """
