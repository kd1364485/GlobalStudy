"""OCR エンジンの抽象インターフェース。

エンジン（RapidOCR / PaddleOCR 等）を差し替え可能にするための境界。
"""

from abc import ABC, abstractmethod
from pathlib import Path

from globalstudy.models.ocr_result import OcrResult


class OcrError(Exception):
    """OCR 処理失敗時に送出される例外。"""


class OcrEngine(ABC):
    """OCR エンジンの共通インターフェース。

    具体的な実装（RapidOcrEngine / PaddleOcrEngine）はこのクラスを
    継承し、recognize() メソッドを実装する。サービス層はこの
    インターフェースに依存することでエンジンを意識せずにOCRを利用できる。
    """

    @abstractmethod
    def recognize(self, image_path: Path) -> OcrResult:
        """画像からテキストを認識する。

        Args:
            image_path: 入力画像のパス。

        Returns:
            認識結果。テキスト未検出の場合も OcrResult を返す（例外にしない）。

        Raises:
            OcrError: 画像が読めない、またはエンジン内部エラーの場合。
        """
