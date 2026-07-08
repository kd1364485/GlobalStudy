"""OCR 結果のデータモデル。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class OcrResult:
    """OCR による文字認識結果。

    Attributes:
        text: 認識テキスト全体（行を改行で連結）。
        confidence: 全行の平均信頼度（0.0〜1.0）。行が無い場合は 0.0。
    """

    text: str
    confidence: float

    def is_empty(self) -> bool:
        """テキストが検出されなかったかを返す。"""
        return not self.text.strip()
