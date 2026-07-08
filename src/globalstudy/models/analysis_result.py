"""解析パイプラインの統合結果モデル。"""

from dataclasses import dataclass
from pathlib import Path

from globalstudy.models.ai_analysis import AiAnalysis
from globalstudy.models.ocr_result import OcrResult


@dataclass(frozen=True)
class AnalysisResult:
    """キャプチャ→OCR→LLM の一連の解析結果。

    Attributes:
        image_path: キャプチャ画像の保存先。
        ocr: OCR 結果（元の英文）。
        analysis: LLM 応答を構造化した解析結果。
    """

    image_path: Path
    ocr: OcrResult
    analysis: AiAnalysis
