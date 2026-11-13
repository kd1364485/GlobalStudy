"""視覚解析ユースケース。

OpenCV ベースのスライド画像判定を実行するサービス。
UI からはこのサービスのみを利用する。
"""

from pathlib import Path

from globalstudy.models.ocr_result import OcrResult
from globalstudy.models.slide_analysis import SlideVisualAnalysis
from globalstudy.utils.logger import get_logger
from globalstudy.visual.slide_analyzer import SlideAnalyzer

logger = get_logger(__name__)


class VisualAnalysisService:
    """スライド画像の視覚的特徴量を分析するサービス。"""

    def __init__(self, analyzer: SlideAnalyzer | None = None) -> None:
        self._analyzer = analyzer or SlideAnalyzer()

    def analyze(
        self,
        image_path: Path,
        ocr_result: OcrResult,
    ) -> SlideVisualAnalysis:
        """キャプチャ画像とOCR結果からスライド種別を判定する。

        Args:
            image_path: キャプチャ画像のパス。
            ocr_result: OCRエンジンの抽出結果。

        Returns:
            スライド判定結果。
        """
        logger.info("視覚解析開始: %s", image_path)
        result = self._analyzer.analyze(image_path, ocr_result)
        logger.info(
            "視覚解析完了: type=%s, recommendation=%s",
            result.visual_type.value,
            result.recommendation,
        )
        return result
