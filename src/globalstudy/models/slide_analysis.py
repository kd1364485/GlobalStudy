"""スライド画像の視覚的特徴量と種別判定のデータモデル。"""

from dataclasses import dataclass
from enum import Enum


class SlideVisualType(Enum):
    """スライドの視覚的分類。"""

    TEXT_ONLY = "text_only"
    MIXED_SLIDE = "mixed_slide"
    VISUAL_HEAVY = "visual_heavy"


@dataclass(frozen=True)
class SlideVisualAnalysis:
    """OpenCV によるスライド画像判定の結果。

    Attributes:
        visual_type: 判定されたスライド種別。
        text_area_ratio: テキスト領域の面積比率（0.0〜1.0）。
        non_text_area_ratio: 非テキスト領域の面積比率（0.0〜1.0）。
        line_count: 検出された直線の総数。
        horizontal_line_count: 水平線の数。
        vertical_line_count: 垂直線の数。
        color_region_ratio: 色付き領域の比率（0.0〜1.0）。
        edge_density: エッジ密度（0.0〜1.0）。
        ocr_line_count: OCRで検出されたテキスト行数。
        ocr_confidence: OCRの平均信頼度（0.0〜1.0）。
        recommendation: UI表示用の推奨メッセージ。
        debug_info: デバッグ用の追加情報。
    """

    visual_type: SlideVisualType
    text_area_ratio: float
    non_text_area_ratio: float
    line_count: int
    horizontal_line_count: int
    vertical_line_count: int
    color_region_ratio: float
    edge_density: float
    ocr_line_count: int
    ocr_confidence: float
    recommendation: str
    debug_info: dict[str, float | int]
