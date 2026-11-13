"""解析パイプラインの統括サービス。

キャプチャ → OCR → LLM ストリーミング翻訳 → スライド画像判定を順に実行する。
"""

from collections.abc import Iterator
from pathlib import Path

from globalstudy.ai.prompts import build_translation_prompt
from globalstudy.services.ai_service import AiService
from globalstudy.services.capture_service import CaptureService
from globalstudy.services.ocr_service import OcrService
from globalstudy.services.visual_analysis_service import VisualAnalysisService
from globalstudy.utils.logger import get_logger

logger = get_logger(__name__)


class AnalysisError(Exception):
    """解析パイプライン失敗時に送出される例外（ユーザー向けメッセージを保持）。"""


class AnalysisService:
    """キャプチャ→OCR→LLM の一連の解析を実行する。

    このクラスはパイプラインの統括者であり、各サービス
    （CaptureService, OcrService, AiService, VisualAnalysisService）
    を順に呼び出し、結果をイベントとして yield する。
    UI層の Worker がこのクラスの translate_stream() を実行する。
    """

    def __init__(
        self,
        capture_service: CaptureService,
        ocr_service: OcrService,
        ai_service: AiService,
        visual_analysis_service: VisualAnalysisService | None = None,
    ) -> None:
        self._capture = capture_service
        self._ocr = ocr_service
        self._ai = ai_service
        self._visual = visual_analysis_service or VisualAnalysisService()
        # 最後にキャプチャした画像のパス（VLM解析で再利用される）
        self.last_image_path: Path | None = None

    def translate_stream(
        self, source_language: str = "english", target_language: str = "japanese"
    ) -> Iterator[tuple[str, str]]:
        """キャプチャ→OCR→ストリーミング翻訳→スライド判定を実行する。

        Args:
            source_language: 翻訳元言語の表示名。
            target_language: 翻訳先言語の表示名。

        Yields:
            ("partial", チャンク文字列) — 翻訳の部分文字列
            ("ocr", OCRテキスト) — OCR完了時の全文
            ("done", 最終翻訳全文) — 完了時
            ("visual", スライド判定情報) — スライド種別と推奨

        Raises:
            AnalysisError: 範囲未設定・テキスト未検出・各処理の失敗時。
        """
        if not self._capture.has_region():
            raise AnalysisError("キャプチャ範囲が未設定です。先に範囲選択してください。")

        logger.info("翻訳開始: キャプチャ実行")
        image_path = self._capture.capture()
        self.last_image_path = image_path

        logger.info("翻訳中: OCR 実行")
        ocr_result = self._ocr.extract_text(image_path)
        if ocr_result.is_empty():
            raise AnalysisError("テキストが検出されませんでした。範囲を確認してください。")

        yield ("ocr", ocr_result.text)

        logger.info("翻訳中: LLM ストリーミング問い合わせ")
        prompt = build_translation_prompt(
            ocr_result.text, source_language=source_language, target_language=target_language
        )
        full_text = ""
        for chunk in self._ai.ask_stream(prompt):
            full_text += chunk
            yield ("partial", chunk)

        logger.info("翻訳完了")
        yield ("done", full_text)

        logger.info("スライド画像判定実行")
        visual_result = self._visual.analyze(image_path, ocr_result)
        yield ("visual", visual_result)
