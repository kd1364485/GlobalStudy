"""OCR ユースケース。

エンジンの生成と実行を担当する。UI からはこのサービスのみを利用する。
"""

from pathlib import Path

from globalstudy.config.settings import Config
from globalstudy.models.ocr_result import OcrResult
from globalstudy.ocr.base import OcrEngine
from globalstudy.ocr.paddleocr_engine import PaddleOcrEngine
from globalstudy.ocr.rapidocr_engine import RapidOcrEngine
from globalstudy.utils.logger import get_logger

logger = get_logger(__name__)


def _create_engine(config: Config) -> OcrEngine:
    """設定に基づいて OCR エンジンを生成する。"""
    engine_name = config.ocr.engine.lower()
    lang = config.ocr.language
    if engine_name == "rapidocr":
        logger.info("OCR エンジン: RapidOCR (lang=%s)", lang)
        return RapidOcrEngine()
    logger.info("OCR エンジン: PaddleOCR (lang=%s)", lang)
    return PaddleOcrEngine(lang=lang)


class OcrService:
    """画像から英語テキストを抽出するサービス。"""

    def __init__(self, config: Config | None = None, engine: OcrEngine | None = None) -> None:
        self._engine = engine or _create_engine(config or Config())

    def extract_text(self, image_path: Path) -> OcrResult:
        """画像からテキストを抽出する。

        Raises:
            OcrError: OCR 処理に失敗した場合。
        """
        logger.debug("OCR 実行: %s", image_path)
        return self._engine.recognize(image_path)
