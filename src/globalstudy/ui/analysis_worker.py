"""解析パイプラインのバックグラウンド実行ワーカー。

OCR・LLM は数十秒かかるため、QThreadPool 上で実行して
GUI のフリーズを防ぐ。結果はシグナルでメインスレッドへ通知する。
"""

from PySide6.QtCore import QObject, Signal

from globalstudy.services.analysis_service import AnalysisService
from globalstudy.ui.base_worker import BaseWorker
from globalstudy.utils.logger import get_logger

logger = get_logger(__name__)


class AnalysisWorkerSignals(QObject):
    """ワーカーからメインスレッドへの通知シグナル。

    Attributes:
        partial: 翻訳の部分文字列（ストリーミング中）。
        ocr_text: OCR完了時の全文。
        finished: 翻訳完了時の最終全文。
        visual: スライド判定結果（SlideVisualAnalysis）。
        failed: エラー発生時のメッセージ。
    """

    partial = Signal(str)
    ocr_text = Signal(str)
    finished = Signal(str)
    visual = Signal(object)
    failed = Signal(str)


class AnalysisWorker(BaseWorker):
    """AnalysisService.translate_stream をバックグラウンドで実行する。

    AnalysisService が yield するイベントをQtシグナルに変換し、
    メインスレッドのUIへ安全に通知する。
    """

    def __init__(
        self,
        analysis_service: AnalysisService,
        source_language: str = "english",
        target_language: str = "japanese",
    ) -> None:
        super().__init__()
        self._service = analysis_service
        self._source_language = source_language
        self._target_language = target_language
        self.signals = AnalysisWorkerSignals()

    def run(self) -> None:
        """QThreadPool 上で実行されるエントリポイント。

        translate_stream() のイベントをシグナルへ変換する。
        例外発生時は failed シグナルでメインスレッドへ通知する。
        """
        try:
            for event, data in self._service.translate_stream(
                source_language=self._source_language,
                target_language=self._target_language,
            ):
                if event == "ocr":
                    self._safe_emit(self.signals.ocr_text, data)
                elif event == "partial":
                    self._safe_emit(self.signals.partial, data)
                elif event == "done":
                    self._safe_emit(self.signals.finished, data)
                elif event == "visual":
                    self._safe_emit(self.signals.visual, data)
        except Exception as exc:
            logger.error("翻訳失敗: %s", exc)
            self._safe_emit(self.signals.failed, str(exc))
