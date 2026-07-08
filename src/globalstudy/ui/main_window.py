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
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from globalstudy.capture.hotkey_listener import HotkeyListener
from globalstudy.config import Config
from globalstudy.models.analysis_result import AnalysisResult
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

        self.analyze_button = QPushButton("キャプチャ＆解析")
        self.analyze_button.clicked.connect(self._on_analyze)
        bar.addWidget(self.analyze_button)

        bar.addStretch()
        return bar

    def _create_result_area(self) -> QSplitter:
        splitter = QSplitter(Qt.Orientation.Vertical)

        splitter.addWidget(
            self._create_labeled_text_area("元の英文", "source_text")
        )
        splitter.addWidget(self._create_analysis_tabs())
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        return splitter

    def _create_analysis_tabs(self) -> QTabWidget:
        tabs = QTabWidget()
        tabs.addTab(self._create_text_area("translation_text", "日本語訳"), "日本語訳")
        tabs.addTab(self._create_text_area("key_points_text", "重要ポイント"), "重要ポイント")
        tabs.addTab(self._create_text_area("terms_text", "専門用語の解説"), "専門用語")
        tabs.addTab(
            self._create_text_area("beginner_text", "初心者向け説明"), "初心者向け説明"
        )
        tabs.addTab(self._create_text_area("background_text", "背景知識"), "背景知識")
        tabs.addTab(self._create_text_area("related_text", "関連概念"), "関連概念")
        self.analysis_tabs = tabs
        return tabs

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
        worker = AnalysisWorker(self._analysis_service)
        worker.signals.finished.connect(self._on_analysis_finished)
        worker.signals.failed.connect(self._on_analysis_failed)
        self._worker = worker
        self._thread_pool.start(worker)

    def _set_analyzing(self, analyzing: bool) -> None:
        self._analyzing = analyzing
        self.analyze_button.setEnabled(not analyzing)
        if analyzing:
            self.statusBar().showMessage("解析中...（キャプチャ → OCR → AI）")

    def _on_analysis_finished(self, result: AnalysisResult) -> None:
        self._worker = None
        self._set_analyzing(False)
        analysis = result.analysis
        self.source_text.setPlainText(result.ocr.text)
        self.translation_text.setPlainText(analysis.translation)
        self.key_points_text.setPlainText(analysis.key_points)
        self.terms_text.setPlainText(analysis.terms or "専門用語はありません")
        self.beginner_text.setPlainText(analysis.beginner_explanation)
        self.background_text.setPlainText(analysis.background or "背景知識はありません")
        self.related_text.setPlainText(analysis.related_concepts or "関連概念はありません")
        self.analysis_tabs.setCurrentIndex(0)
        self.statusBar().showMessage(
            f"解析完了（OCR信頼度: {result.ocr.confidence:.2f}）"
        )

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
