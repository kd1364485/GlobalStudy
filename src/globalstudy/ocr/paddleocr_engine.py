"""PaddleOCR によるエンジン実装。

RapidOCR より高精度だが、PaddlePaddle 依存によりインストールが重い。
"""

from pathlib import Path

from paddleocr import PaddleOCR

from globalstudy.models.ocr_result import OcrLine, OcrResult
from globalstudy.ocr.base import OcrEngine, OcrError
from globalstudy.utils.logger import get_logger

logger = get_logger(__name__)


class PaddleOcrEngine(OcrEngine):
    """PaddleOCR を用いた OCR エンジン。

    RapidOCR より高精度だが、PaddlePaddle 依存によりインストールが重い。
    初回利用時にモデルをロードする（遅延初期化）。
    """

    def __init__(self, lang: str = "en") -> None:
        self._lang = lang
        # 初回 recognize() 時までエンジンをロードしない
        self._engine: PaddleOCR | None = None

    def _load_engine(self) -> PaddleOCR:
        """エンジンを遅延初期化する（モデルロードが重いため）。"""
        if self._engine is None:
            logger.info("PaddleOCR エンジンを初期化中... (lang=%s)", self._lang)
            self._engine = PaddleOCR(
                # 講義スライド前提のため、ドキュメント向き補正は無効化
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
                lang=self._lang,
                enable_mkldnn=False,
            )
            logger.info("PaddleOCR エンジン初期化完了")
        return self._engine

    def recognize(self, image_path: Path) -> OcrResult:
        """画像からテキストを認識し、OcrResult を返す。"""
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
        各 OCRResult は dict ライクで rec_texts / rec_scores / rec_polys を持つ。
        rec_polys（4頂点座標）は外接矩形に変換して OcrLine の座標とする。
        """
        if not results:
            logger.info("テキストは検出されませんでした")
            return OcrResult(text="", confidence=0.0)

        lines: list[str] = []
        scores: list[float] = []
        ocr_lines: list[OcrLine] = []

        for page in results:
            if page is None:
                continue
            texts = page.get("rec_texts", [])
            page_scores = page.get("rec_scores", [])
            polys = page.get("rec_polys", [])
            for i, (text, score) in enumerate(zip(texts, page_scores)):
                lines.append(text)
                scores.append(float(score))
                # 座標（quad）があれば外接矩形に変換して保持
                if i < len(polys):
                    xs = [float(p[0]) for p in polys[i]]
                    ys = [float(p[1]) for p in polys[i]]
                    left, top = int(min(xs)), int(min(ys))
                    ocr_lines.append(
                        OcrLine(
                            text=text,
                            confidence=float(score),
                            left=left,
                            top=top,
                            width=int(max(xs)) - left,
                            height=int(max(ys)) - top,
                        )
                    )

        if not lines:
            logger.info("テキストは検出されませんでした")
            return OcrResult(text="", confidence=0.0)

        text = "\n".join(lines)
        confidence = sum(scores) / len(scores)
        logger.info("OCR 完了: %d 行, 平均信頼度 %.2f", len(lines), confidence)
        return OcrResult(text=text, confidence=confidence, lines=tuple(ocr_lines))
