"""メインウィンドウ。

UI 構築とユーザー操作の受付のみを担当し、
処理は services へ委譲する。
"""

from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from globalstudy.capture.hotkey_listener import HotkeyListener
from globalstudy.config import Config
from globalstudy.models.region import CaptureRegion
from globalstudy.services.analysis_service import AnalysisService
from globalstudy.services.capture_service import CaptureService
from globalstudy.ui.analysis_worker import AnalysisWorker
from globalstudy.ui.region_selector import RegionSelectorOverlay
from globalstudy.utils.logger import get_logger

logger = get_logger(__name__)


class MainWindow(QMainWindow):
    """アプリのメイン画面。UI 構築のみを担当し、処理は services へ委譲する。"""

    def __init__(
        self,
        config: Config,
        capture_service: CaptureService,
        analysis_service: AnalysisService,
    ) -> None:
        super().__init__()
        self._config = config
        self._capture_service = capture_service
        self._analysis_service = analysis_service
        self._thread_pool = QThreadPool.globalInstance()
        self._analyzing = False
        self._worker: AnalysisWorker | None = None
        self._region_selector: RegionSelectorOverlay | None = None
        self._setup_window()
        self._setup_widgets()
        self._setup_hotkey()
        logger.info("メインウィンドウを初期化しました")

    def _setup_window(self) -> None:
        ui = self._config.ui
        self.setWindowTitle(ui.window_title)
        self.resize(ui.window_width, ui.window_height)

    def _setup_widgets(self) -> None:
        central = QWidget()
        layout = QVBoxLayout(central)

        layout.addLayout(self._create_button_bar())
        layout.addWidget(self._create_result_area(), stretch=1)

        self.setCentralWidget(central)
        self.statusBar().showMessage(
            f"準備完了（ホットキー: {self._config.capture.hotkey}）"
        )

    def _setup_hotkey(self) -> None:
        self._hotkey_listener = HotkeyListener(self._config.capture.hotkey)
        self._hotkey_listener.triggered.connect(self._on_analyze)
        self._hotkey_listener.start()

    def _create_button_bar(self) -> QHBoxLayout:
        bar = QHBoxLayout()

        self.select_region_button = QPushButton("範囲選択")
        self.select_region_button.clicked.connect(self._on_select_region)
        bar.addWidget(self.select_region_button)

        self.analyze_button = QPushButton("キャプチャ＆翻訳")
        self.analyze_button.clicked.connect(self._on_analyze)
        bar.addWidget(self.analyze_button)

        bar.addStretch()
        return bar

    def _create_result_area(self) -> QSplitter:
        splitter = QSplitter(Qt.Orientation.Vertical)

        splitter.addWidget(
            self._create_labeled_text_area("元の英文", "source_text")
        )
        splitter.addWidget(
            self._create_labeled_text_area("日本語訳", "translation_text")
        )
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        return splitter

    def _create_text_area(self, attr_name: str, placeholder: str) -> QTextEdit:
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setPlaceholderText(f"{placeholder}がここに表示されます")
        setattr(self, attr_name, text_edit)
        return text_edit

    def _create_labeled_text_area(self, title: str, attr_name: str) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(QLabel(title))
        layout.addWidget(self._create_text_area(attr_name, title))

        return container

    def _on_select_region(self) -> None:
        self._region_selector = RegionSelectorOverlay()
        self._region_selector.region_selected.connect(self._on_region_selected)
        self._region_selector.selection_cancelled.connect(self._on_selection_cancelled)
        self._region_selector.show()

    def _on_region_selected(self, region: CaptureRegion) -> None:
        self._capture_service.set_region(region)
        self.statusBar().showMessage(
            f"範囲設定完了: {region.width}x{region.height} "
            f"(左上: {region.left}, {region.top})"
        )

    def _on_selection_cancelled(self) -> None:
        self.statusBar().showMessage("範囲選択をキャンセルしました")

    def _on_analyze(self) -> None:
        if self._analyzing:
            self.statusBar().showMessage("解析中です。完了をお待ちください")
            return
        if not self._capture_service.has_region():
            self.statusBar().showMessage("先に範囲選択してください")
            return

        self._set_analyzing(True)
        self.translation_text.clear()
        worker = AnalysisWorker(self._analysis_service)
        worker.signals.ocr_text.connect(self._on_ocr_text)
        worker.signals.partial.connect(self._on_partial)
        worker.signals.finished.connect(self._on_translation_finished)
        worker.signals.failed.connect(self._on_analysis_failed)
        self._worker = worker
        self._thread_pool.start(worker)

    def _set_analyzing(self, analyzing: bool) -> None:
        self._analyzing = analyzing
        self.analyze_button.setEnabled(not analyzing)
        if analyzing:
            self.statusBar().showMessage("翻訳中...（キャプチャ → OCR → AI）")

    def _on_ocr_text(self, text: str) -> None:
        self.source_text.setPlainText(text)
        self.statusBar().showMessage("OCR完了。翻訳中...")

    def _on_partial(self, chunk: str) -> None:
        cursor = self.translation_text.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(chunk)
        self.translation_text.setTextCursor(cursor)

    def _on_translation_finished(self, full_text: str) -> None:
        self._worker = None
        self._set_analyzing(False)
        self.translation_text.setPlainText(full_text)
        self.statusBar().showMessage("翻訳完了")

    def _on_analysis_failed(self, message: str) -> None:
        self._worker = None
        self._set_analyzing(False)
        self.statusBar().showMessage(f"解析失敗: {message}")

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt命名規則)
        self._hotkey_listener.stop()
        if self._worker is not None:
            logger.info("ワーカーの完了を待機中...")
            self._thread_pool.waitForDone()
            self._worker = None
        super().closeEvent(event)
