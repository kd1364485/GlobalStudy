"""RapidOCR（PaddleOCR モデルの ONNX 版）によるエンジン実装。"""

from pathlib import Path

from rapidocr import RapidOCR

from globalstudy.models.ocr_result import OcrLine, OcrResult
from globalstudy.ocr.base import OcrEngine, OcrError
from globalstudy.utils.logger import get_logger

logger = get_logger(__name__)


class RapidOcrEngine(OcrEngine):
    """RapidOCR を用いた OCR エンジン。

    PaddleOCR モデルを ONNX 形式で推論する軽量実装。
    初回利用時にモデルをロードする（遅延初期化）。
    """

    def __init__(self, lang: str = "en") -> None:
        self._lang = lang
        # 初回 recognize() 時までエンジンをロードしない
        self._engine: RapidOCR | None = None

    def _load_engine(self) -> RapidOCR:
        """エンジンを遅延初期化する（モデルロードが重いため）。"""
        if self._engine is None:
            logger.info("RapidOCR エンジンを初期化中...")
            self._engine = RapidOCR()
            logger.info("RapidOCR エンジン初期化完了")
        return self._engine

    def recognize(self, image_path: Path) -> OcrResult:
        """画像からテキストを認識し、OcrResult を返す。"""
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
        """RapidOCR の出力を OcrResult へ変換する。

        output.boxes は各行の4頂点座標（quad）を持つため、
        外接矩形に変換して OcrLine の座標とする。
        """
        if output is None or output.txts is None or len(output.txts) == 0:
            logger.info("テキストは検出されませんでした")
            return OcrResult(text="", confidence=0.0)

        texts = list(output.txts)
        scores = list(output.scores) if output.scores is not None else []
        boxes = list(output.boxes) if output.boxes is not None else []
        confidence = sum(scores) / len(scores) if scores else 0.0

        # 座標付き行情報を構築（ボックスが無い行は座標なしのため除外）
        ocr_lines: list[OcrLine] = []
        for i, line_text in enumerate(texts):
            if i >= len(boxes):
                break
            # quad（4頂点）→ 外接矩形へ変換
            xs = [float(p[0]) for p in boxes[i]]
            ys = [float(p[1]) for p in boxes[i]]
            left, top = int(min(xs)), int(min(ys))
            width, height = int(max(xs)) - left, int(max(ys)) - top
            ocr_lines.append(
                OcrLine(
                    text=line_text,
                    confidence=float(scores[i]) if i < len(scores) else 0.0,
                    left=left,
                    top=top,
                    width=width,
                    height=height,
                )
            )

        text = "\n".join(texts)
        logger.info("OCR 完了: %d 行, 平均信頼度 %.2f", len(texts), confidence)
        return OcrResult(text=text, confidence=confidence, lines=tuple(ocr_lines))
