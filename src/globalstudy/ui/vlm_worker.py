"""VLM 解析のバックグラウンド実行ワーカー。

VLM（視覚言語モデル）への画像送信は数十秒かかるため、
QThreadPool 上で実行してGUIのフリーズを防ぐ。
"""

from pathlib import Path

from PySide6.QtCore import QObject, Signal

from globalstudy.services.vlm_analysis_service import VlmAnalysisService
from globalstudy.ui.base_worker import BaseWorker
from globalstudy.utils.logger import get_logger

logger = get_logger(__name__)


class VlmWorkerSignals(QObject):
    """VLM ワーカーからメインスレッドへの通知シグナル。

    Attributes:
        partial: VLM解析の部分文字列（ストリーミング中）。
        finished: VLM解析完了時の最終全文。
        failed: エラー発生時のメッセージ。
    """

    partial = Signal(str)
    finished = Signal(str)
    failed = Signal(str)


class VlmWorker(BaseWorker):
    """VlmAnalysisService.analyze_stream をバックグラウンドで実行する。

    VLMからのストリーミングチャンクを partial シグナルで
    メインスレッドへ順次通知し、完了時に finished シグナルを送る。
    """

    def __init__(
        self,
        vlm_service: VlmAnalysisService,
        image_path: Path,
        source_language: str = "english",
        target_language: str = "japanese",
    ) -> None:
        super().__init__()
        self._service = vlm_service
        self._image_path = image_path
        self._source_language = source_language
        self._target_language = target_language
        self.signals = VlmWorkerSignals()

    def run(self) -> None:
        """QThreadPool 上で実行されるエントリポイント。"""
        try:
            full_text = ""
            # ストリーミングチャンクを順次UIへ通知
            for chunk in self._service.analyze_stream(
                self._image_path,
                source_language=self._source_language,
                target_language=self._target_language,
            ):
                full_text += chunk
                self._safe_emit(self.signals.partial, chunk)
            self._safe_emit(self.signals.finished, full_text)
        except Exception as exc:
            logger.error("VLM 解析失敗: %s", exc)
            self._safe_emit(self.signals.failed, str(exc))
