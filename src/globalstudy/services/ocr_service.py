"""OCR ユースケース。

エンジンの生成と実行を担当する。UI からはこのサービスのみを利用する。
"""

from pathlib import Path

from globalstudy.config import Config
from globalstudy.config.settings import OcrConfig
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
        return RapidOcrEngine(lang=lang)
    logger.info("OCR エンジン: PaddleOCR (lang=%s)", lang)
    return PaddleOcrEngine(lang=lang)


class OcrService:
    """画像から英語テキストを抽出するサービス。

    設定に基づいて適切なOCRエンジンを生成し、
    UI層へはこのサービスのみを公開する。
    """

    def __init__(self, config: Config | None = None, engine: OcrEngine | None = None) -> None:
        # 外部からエンジンを注入可能（テスト用）。未指定時は設定から生成。
        self._config = config or Config()
        self._engine = engine or _create_engine(self._config)

    def set_language(self, language: str) -> None:
        """OCR言語を切り替え、エンジンを再生成する。

        ソース言語変更時に呼び出される。エンジンの遅延初期化状態もリセットされ、
        次回 recognize() 時に新しい言語モデルがロードされる。
        """
        if self._config.ocr.language == language:
            return
        logger.info("OCR言語を切り替え: %s → %s", self._config.ocr.language, language)
        self._config = Config(
            ocr=OcrConfig(engine=self._config.ocr.engine, language=language),
            paths=self._config.paths,
            log=self._config.log,
            capture=self._config.capture,
            translation=self._config.translation,
            llm=self._config.llm,
            overlay_llm=self._config.overlay_llm,
            vlm=self._config.vlm,
            ui=self._config.ui,
        )
        self._engine = _create_engine(self._config)

    def extract_text(self, image_path: Path) -> OcrResult:
        """画像からテキストを抽出する。

        Raises:
            OcrError: OCR 処理に失敗した場合。
        """
        logger.debug("OCR 実行: %s", image_path)
        return self._engine.recognize(image_path)
