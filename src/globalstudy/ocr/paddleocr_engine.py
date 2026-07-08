"""PaddleOCR によるエンジン実装。

RapidOCR より高精度だが、PaddlePaddle 依存によりインストールが重い。
"""

from pathlib import Path

from paddleocr import PaddleOCR

from globalstudy.models.ocr_result import OcrResult
from globalstudy.ocr.base import OcrEngine, OcrError
from globalstudy.utils.logger import get_logger

logger = get_logger(__name__)


class PaddleOcrEngine(OcrEngine):
    """PaddleOCR を用いた OCR エンジン。初回利用時にモデルをロードする。"""

    def __init__(self, lang: str = "en") -> None:
        self._lang = lang
        self._engine: PaddleOCR | None = None

    def _load_engine(self) -> PaddleOCR:
        """エンジンを遅延初期化する（モデルロードが重いため）。"""
        if self._engine is None:
            logger.info("PaddleOCR エンジンを初期化中... (lang=%s)", self._lang)
            self._engine = PaddleOCR(
                use_textline_orientation=True,
                lang=self._lang,
                enable_mkldnn=False,
            )
            logger.info("PaddleOCR エンジン初期化完了")
        return self._engine

    def recognize(self, image_path: Path) -> OcrResult:
        if not image_path.exists():
            raise OcrError(f"画像が見つかりません: {image_path}")

        engine = self._load_engine()
        try:
            results = list(engine.predict(str(image_path)))
        except Exception as exc:
            raise OcrError(f"OCR 処理に失敗しました: {exc}") from exc

        return self._to_result(results)

    @staticmethod
    def _to_result(results) -> OcrResult:
        """PaddleOCR 3.x の出力を OcrResult へ変換する。

        PaddleOCR 3.x の predict() は OCRResult のリストを返す。
        各 OCRResult は dict ライクで rec_texts / rec_scores を持つ。
        """
        if not results:
            logger.info("テキストは検出されませんでした")
            return OcrResult(text="", confidence=0.0)

        lines: list[str] = []
        scores: list[float] = []

        for page in results:
            if page is None:
                continue
            texts = page.get("rec_texts", [])
            page_scores = page.get("rec_scores", [])
            for text, score in zip(texts, page_scores):
                lines.append(text)
                scores.append(float(score))

        if not lines:
            logger.info("テキストは検出されませんでした")
            return OcrResult(text="", confidence=0.0)

        text = "\n".join(lines)
        confidence = sum(scores) / len(scores)
        logger.info("OCR 完了: %d 行, 平均信頼度 %.2f", len(lines), confidence)
        return OcrResult(text=text, confidence=confidence)
