"""オーバーレイ翻訳のバックグラウンド実行ワーカー。

キャプチャ → OCR → 行バッチ翻訳は数秒〜数十秒かかるため、
QThreadPool 上で実行してGUIのフリーズを防ぐ。
"""

from PySide6.QtCore import QObject, Signal

from globalstudy.services.overlay_translation_service import (
    OverlayTranslationService,
)
from globalstudy.ui.base_worker import BaseWorker
from globalstudy.utils.logger import get_logger

logger = get_logger(__name__)


class OverlayWorkerSignals(QObject):
    """オーバーレイワーカーからメインスレッドへの通知シグナル。

    Attributes:
        prepared: キャプチャ範囲と画像パスが確定した時に発火。
            (region, image_path) を渡す。オーバーレイ位置確定に使用。
        patch_ready: 1パッチの翻訳が完了した時に発火。OverlayPatch を渡す。
        finished: 全パッチ生成完了時の OverlayPatch リスト。
        failed: エラー発生時のメッセージ。
    """

    prepared = Signal(object, object)
    patch_ready = Signal(object)
    finished = Signal(list)
    failed = Signal(str)


class OverlayWorker(BaseWorker):
    """OverlayTranslationService.prepare_and_stream をバックグラウンドで実行する。

    ストリーミング対応: キャプチャ範囲確定時に prepared シグナル、
    1行の翻訳完了ごとに patch_ready シグナルを発火し、
    最後に finished シグナルで全パッチを通知する。
    """

    def __init__(
        self,
        service: OverlayTranslationService,
        source_language: str = "english",
        target_language: str = "japanese",
    ) -> None:
        super().__init__()
        self._service = service
        self._source_language = source_language
        self._target_language = target_language
        self.signals = OverlayWorkerSignals()

    def run(self) -> None:
        """QThreadPool 上で実行されるエントリポイント。"""
        try:
            region, image_path, gen = self._service.prepare_and_stream(
                source_language=self._source_language,
                target_language=self._target_language,
            )
            self._safe_emit(self.signals.prepared, region, image_path)

            patches: list = []
            for patch in gen:
                patches.append(patch)
                self._safe_emit(self.signals.patch_ready, patch)

            self._safe_emit(self.signals.finished, patches)
        except Exception as exc:
            logger.error("オーバーレイ翻訳失敗: %s", exc)
            self._safe_emit(self.signals.failed, str(exc))
