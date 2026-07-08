"""RapidOCR（PaddleOCR モデルの ONNX 版）によるエンジン実装。"""

from pathlib import Path

from rapidocr import RapidOCR

from globalstudy.models.ocr_result import OcrResult
from globalstudy.ocr.base import OcrEngine, OcrError
from globalstudy.utils.logger import get_logger

logger = get_logger(__name__)


class RapidOcrEngine(OcrEngine):
    """RapidOCR を用いた OCR エンジン。初回利用時にモデルをロードする。"""

    def __init__(self) -> None:
        self._engine: RapidOCR | None = None

    def _load_engine(self) -> RapidOCR:
        """エンジンを遅延初期化する（モデルロードが重いため）。"""
        if self._engine is None:
            logger.info("RapidOCR エンジンを初期化中...")
            self._engine = RapidOCR()
            logger.info("RapidOCR エンジン初期化完了")
        return self._engine

    def recognize(self, image_path: Path) -> OcrResult:
        if not image_path.exists():
            raise OcrError(f"画像が見つかりません: {image_path}")

        engine = self._load_engine()
        try:
            output = engine(str(image_path))
        except Exception as exc:
            raise OcrError(f"OCR 処理に失敗しました: {exc}") from exc

        return self._to_result(output)

    @staticmethod
    def _to_result(output) -> OcrResult:
        """RapidOCR の出力を OcrResult へ変換する。"""
        if output is None or output.txts is None or len(output.txts) == 0:
            logger.info("テキストは検出されませんでした")
            return OcrResult(text="", confidence=0.0)

        lines = list(output.txts)
        scores = list(output.scores) if output.scores is not None else []
        confidence = sum(scores) / len(scores) if scores else 0.0

        text = "\n".join(lines)
        logger.info("OCR 完了: %d 行, 平均信頼度 %.2f", len(lines), confidence)
        return OcrResult(text=text, confidence=confidence)
