"""解析パイプラインの統括サービス。

キャプチャ → OCR → LLM を順に実行し、統合結果を返す。
ストリーミング翻訳にも対応。
"""

from collections.abc import Iterator
from pathlib import Path

from globalstudy.ai.prompts import build_translation_prompt
from globalstudy.ai.response_parser import parse_analysis_response
from globalstudy.models.analysis_result import AnalysisResult
from globalstudy.services.ai_service import AiService
from globalstudy.services.capture_service import CaptureService
from globalstudy.services.ocr_service import OcrService
from globalstudy.utils.logger import get_logger

logger = get_logger(__name__)


class AnalysisError(Exception):
    """解析パイプライン失敗時に送出される例外（ユーザー向けメッセージを保持）。"""


class AnalysisService:
    """キャプチャ→OCR→LLM の一連の解析を実行する。"""

    def __init__(
        self,
        capture_service: CaptureService,
        ocr_service: OcrService,
        ai_service: AiService,
    ) -> None:
        self._capture = capture_service
        self._ocr = ocr_service
        self._ai = ai_service

    def analyze_screen(self) -> AnalysisResult:
        """設定済み範囲をキャプチャして解析する。

        Raises:
            AnalysisError: 範囲未設定・テキスト未検出・各処理の失敗時。
        """
        if not self._capture.has_region():
            raise AnalysisError("キャプチャ範囲が未設定です。先に範囲選択してください。")

        logger.info("解析開始: キャプチャ実行")
        image_path = self._capture.capture()

        logger.info("解析中: OCR 実行")
        ocr_result = self._ocr.extract_text(image_path)
        if ocr_result.is_empty():
            raise AnalysisError("テキストが検出されませんでした。範囲を確認してください。")

        logger.info("解析中: LLM 問い合わせ")
        prompt = build_translation_prompt(ocr_result.text)
        ai_response = self._ai.ask(prompt)
        analysis = parse_analysis_response(ai_response)

        logger.info("解析完了")
        return AnalysisResult(
            image_path=image_path,
            ocr=ocr_result,
            analysis=analysis,
        )

    def translate_stream(self) -> Iterator[tuple[str, str]]:
        """キャプチャ→OCR→ストリーミング翻訳を実行する。

        Yields:
            ("partial", チャンク文字列) — 翻訳の部分文字列
            ("ocr", OCRテキスト) — OCR完了時の全文
            ("done", 最終翻訳全文) — 完了時

        Raises:
            AnalysisError: 範囲未設定・テキスト未検出・各処理の失敗時。
        """
        if not self._capture.has_region():
            raise AnalysisError("キャプチャ範囲が未設定です。先に範囲選択してください。")

        logger.info("翻訳開始: キャプチャ実行")
        image_path = self._capture.capture()

        logger.info("翻訳中: OCR 実行")
        ocr_result = self._ocr.extract_text(image_path)
        if ocr_result.is_empty():
            raise AnalysisError("テキストが検出されませんでした。範囲を確認してください。")

        yield ("ocr", ocr_result.text)

        logger.info("翻訳中: LLM ストリーミング問い合わせ")
        prompt = build_translation_prompt(ocr_result.text)
        full_text = ""
        for chunk in self._ai.ask_stream(prompt):
            full_text += chunk
            yield ("partial", chunk)

        logger.info("翻訳完了")
        yield ("done", full_text)
