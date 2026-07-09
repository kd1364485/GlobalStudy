"""解析パイプラインのバックグラウンド実行ワーカー。

OCR・LLM は数十秒かかるため、QThreadPool 上で実行して
GUI のフリーズを防ぐ。結果はシグナルでメインスレッドへ通知する。
"""

from PySide6.QtCore import QObject, QRunnable, Signal

from globalstudy.services.analysis_service import AnalysisService
from globalstudy.utils.logger import get_logger

logger = get_logger(__name__)


class AnalysisWorkerSignals(QObject):
    """ワーカーからメインスレッドへの通知シグナル。"""

    partial = Signal(str)
    ocr_text = Signal(str)
    finished = Signal(str)
    failed = Signal(str)


class AnalysisWorker(QRunnable):
    """AnalysisService.analyze_screen をバックグラウンドで実行する。"""

    def __init__(self, analysis_service: AnalysisService) -> None:
        super().__init__()
        self.setAutoDelete(False)
        self._service = analysis_service
        self.signals = AnalysisWorkerSignals()

    def run(self) -> None:
        try:
            for event, text in self._service.translate_stream():
                if event == "ocr":
                    self._safe_emit(self.signals.ocr_text, text)
                elif event == "partial":
                    self._safe_emit(self.signals.partial, text)
                elif event == "done":
                    self._safe_emit(self.signals.finished, text)
        except Exception as exc:
            logger.error("翻訳失敗: %s", exc)
            self._safe_emit(self.signals.failed, str(exc))

    @staticmethod
    def _safe_emit(signal, *args) -> None:
        """シグナル送信時に受信側 QObject が削除されている場合の RuntimeError を回避する。"""
        try:
            signal.emit(*args)
        except RuntimeError:
            logger.warning("シグナル送信先が削除済みのため送信をスキップしました")
