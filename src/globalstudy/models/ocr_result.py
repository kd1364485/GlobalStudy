"""OCR 結果のデータモデル。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class OcrLine:
    """OCR で認識された1行分のテキストとその位置。

    Attributes:
        text: 認識テキスト。
        confidence: 信頼度（0.0〜1.0）。
        left: バウンディングボックス左端（画像ピクセル座標）。
        top: バウンディングボックス上端（画像ピクセル座標）。
        width: バウンディングボックスの幅（ピクセル）。
        height: バウンディングボックスの高さ（ピクセル）。
    """

    text: str
    confidence: float
    left: int
    top: int
    width: int
    height: int


@dataclass(frozen=True)
class OcrResult:
    """OCR による文字認識結果。

    Attributes:
        text: 認識テキスト全体（行を改行で連結）。
        confidence: 全行の平均信頼度（0.0〜1.0）。行が無い場合は 0.0。
        lines: 座標付きの行情報（オーバーレイ翻訳用）。
            座標を返さないエンジンでは空タプルとなる。
    """

    text: str
    confidence: float
    lines: tuple[OcrLine, ...] = ()

    def is_empty(self) -> bool:
        """テキストが検出されなかったかを返す。"""
        return not self.text.strip()
