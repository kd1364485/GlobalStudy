"""メインウィンドウ。

UI 構築とユーザー操作の受付のみを担当し、
処理は services へ委譲する。
ボタン操作・ホットキー・スレッド管理を統括する。
"""

from pathlib import Path

from PySide6.QtCore import Qt, QThreadPool, QTimer
from PySide6.QtWidgets import (
    QComboBox,
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
from globalstudy.capture.slide_monitor import (
    SlideMonitor,
    compute_image_hash,
    compute_region_hash,
    hash_distance,
)
from globalstudy.config import Config
from globalstudy.config.settings import source_language_to_ocr_code
from globalstudy.models.region import CaptureRegion
from globalstudy.models.overlay import OverlayPatch
from globalstudy.models.slide_analysis import SlideVisualAnalysis, SlideVisualType
from globalstudy.services.analysis_service import AnalysisService
from globalstudy.services.capture_service import CaptureService
from globalstudy.services.ocr_service import OcrService
from globalstudy.services.overlay_translation_service import (
    OverlayTranslationService,
)
from globalstudy.services.vlm_analysis_service import VlmAnalysisService
from globalstudy.ui.analysis_worker import AnalysisWorker
from globalstudy.ui.overlay_window import OverlayWindow
from globalstudy.ui.overlay_worker import OverlayWorker
from globalstudy.ui.region_selector import RegionSelectorOverlay
from globalstudy.ui.vlm_worker import VlmWorker
from globalstudy.utils.logger import get_logger

logger = get_logger(__name__)

# オーバーレイ翻訳完了後の自動再翻訳の連続上限
# （動画再生中など常に変化する画面での無限ループを防ぐ）
_MAX_OVERLAY_RETRANSLATES = 3

# 言語選択ドロップダウンの選択肢
_SOURCE_LANGUAGES = [
    "english",
    "chinese",
    "japanese",
    "korean",
    "french",
    "german",
    "spanish",
]
_TARGET_LANGUAGES = [
    "japanese",
    "english",
    "chinese",
    "korean",
    "french",
    "german",
    "spanish",
]


class MainWindow(QMainWindow):
    """アプリのメイン画面。

    UI構築のみを担当し、解析処理は AnalysisService / VlmAnalysisService へ
    委譲する。バックグラウンド実行は QThreadPool + Worker パターンで行う。
    """

    def __init__(
        self,
        config: Config,
        capture_service: CaptureService,
        analysis_service: AnalysisService,
        vlm_analysis_service: VlmAnalysisService | None = None,
        overlay_service: OverlayTranslationService | None = None,
        ocr_service: OcrService | None = None,
    ) -> None:
        super().__init__()
        self._config = config
        self._capture_service = capture_service
        self._analysis_service = analysis_service
        self._vlm_analysis_service = vlm_analysis_service
        self._overlay_service = overlay_service
        self._ocr_service = ocr_service
        # 現在の翻訳言語ペア（UIドロップダウンで切り替え可能）
        self._source_language = config.translation.source_language
        self._target_language = config.translation.target_language
        # バックグラウンドワーカー実行用のスレッドプール
        self._thread_pool = QThreadPool.globalInstance()
        # 解析中フラグ（ボタンの二重押下を防止）
        self._analyzing = False
        self._vlm_analyzing = False
        self._overlay_analyzing = False
        # 実行中のワーカー参照（クローズ時に待機するため保持）
        self._worker: AnalysisWorker | None = None
        self._vlm_worker: VlmWorker | None = None
        self._overlay_worker: OverlayWorker | None = None
        self._region_selector: RegionSelectorOverlay | None = None
        # 最後にキャプチャした画像パス（VLM解析で再利用）
        self._last_image_path: Path | None = None
        # 最後のスライド判定結果（VLMボタンの有効/無効判定に使用）
        self._last_visual: SlideVisualAnalysis | None = None
        # スライド変化の自動検知モニター（自動翻訳用）
        self._slide_monitor = SlideMonitor(
            config, region_provider=lambda: capture_service.region
        )
        self._slide_monitor.slide_changed.connect(self._on_slide_changed)
        # 翻訳パッチを画面上に重ねるオーバーレイウィンドウ
        self._overlay_window = OverlayWindow()
        # 自動オーバーレイモード（スライド変化時にオーバーレイ翻訳を自動実行）
        self._auto_overlay = False
        # ストリーミング表示中のパッチ数
        self._streaming_patch_count = 0
        # 翻訳完了後の自動再翻訳の連続回数（無限ループ防止）
        self._overlay_retranslate_count = 0
        self._setup_window()
        self._setup_widgets()
        self._setup_hotkey()
        # 前回の範囲が復元されていればステータスバーに表示
        self._show_restored_region()
        logger.info("メインウィンドウを初期化しました")

    def _setup_window(self) -> None:
        ui = self._config.ui
        self.setWindowTitle(ui.window_title)
        self.resize(ui.window_width, ui.window_height)

    def _setup_widgets(self) -> None:
        central = QWidget()
        layout = QVBoxLayout(central)

        layout.addLayout(self._create_button_bar())
        layout.addWidget(self._create_visual_info_area())
        layout.addWidget(self._create_result_area(), stretch=1)

        self.setCentralWidget(central)
        self._update_tab_labels()
        self.statusBar().showMessage(
            f"準備完了（ホットキー: {self._config.capture.hotkey}）"
        )

    def _setup_hotkey(self) -> None:
        """グローバルホットキーリスナーを起動する。"""
        self._hotkey_listener = HotkeyListener(self._config.capture.hotkey)
        self._hotkey_listener.triggered.connect(self._on_analyze)
        self._hotkey_listener.start()

    def _create_button_bar(self) -> QHBoxLayout:
        """上部ボタンバー（範囲選択・キャプチャ＆翻訳・画像も解析）を構築する。"""
        bar = QHBoxLayout()

        self.select_region_button = QPushButton("範囲選択")
        self.select_region_button.clicked.connect(self._on_select_region)
        bar.addWidget(self.select_region_button)

        self.analyze_button = QPushButton("キャプチャ＆翻訳")
        self.analyze_button.clicked.connect(self._on_analyze)
        bar.addWidget(self.analyze_button)

        self.vlm_button = QPushButton("画像も解析")
        self.vlm_button.clicked.connect(self._on_vlm_analyze)
        self.vlm_button.setEnabled(False)
        bar.addWidget(self.vlm_button)

        # 自動翻訳トグル（スライド変化を検知して自動で翻訳実行）
        self.auto_button = QPushButton("自動翻訳: OFF")
        self.auto_button.setCheckable(True)
        self.auto_button.toggled.connect(self._on_auto_toggled)
        bar.addWidget(self.auto_button)

        # 自動オーバーレイトグル（スライド変化時にオーバーレイを自動更新）
        self.auto_overlay_button = QPushButton("自動オーバーレイ: OFF")
        self.auto_overlay_button.setCheckable(True)
        self.auto_overlay_button.toggled.connect(self._on_auto_overlay_toggled)
        bar.addWidget(self.auto_overlay_button)

        # オーバーレイ翻訳（元のテキストの上に訳文を重ねて表示）
        self.overlay_button = QPushButton("オーバーレイ翻訳")
        self.overlay_button.clicked.connect(self._on_overlay_translate)
        bar.addWidget(self.overlay_button)

        # オーバーレイの消去
        self.overlay_clear_button = QPushButton("オーバーレイ消去")
        self.overlay_clear_button.clicked.connect(self._on_overlay_clear)
        bar.addWidget(self.overlay_clear_button)

        bar.addStretch()

        # 言語選択ドロップダウン
        bar.addWidget(QLabel("元言語:"))
        self.source_lang_combo = QComboBox()
        self.source_lang_combo.addItems(_SOURCE_LANGUAGES)
        self.source_lang_combo.setCurrentText(self._source_language)
        self.source_lang_combo.currentTextChanged.connect(self._on_source_language_changed)
        bar.addWidget(self.source_lang_combo)

        bar.addWidget(QLabel("→"))
        self.target_lang_combo = QComboBox()
        self.target_lang_combo.addItems(_TARGET_LANGUAGES)
        self.target_lang_combo.setCurrentText(self._target_language)
        self.target_lang_combo.currentTextChanged.connect(self._on_target_language_changed)
        bar.addWidget(self.target_lang_combo)

        return bar

    def _create_visual_info_area(self) -> QWidget:
        """スライド判定結果表示エリアを構築する。"""
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)

        self.visual_type_label = QLabel("Visual Type: ---")
        self.recommendation_label = QLabel("Recommendation: ---")
        self.recommendation_label.setWordWrap(True)

        layout.addWidget(self.visual_type_label)
        layout.addWidget(self.recommendation_label, stretch=1)
        return container

    def _create_result_area(self) -> QTabWidget:
        """翻訳タブ・VLM解析タブを含む結果表示エリアを構築する。"""
        tabs = QTabWidget()

        tabs.addTab(self._create_translation_tab(), "翻訳")
        tabs.addTab(self._create_vlm_tab(), "VLM解析")

        return tabs

    def _create_translation_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(
            self._create_labeled_text_area("元のテキスト", "source_text")
        )
        splitter.addWidget(
            self._create_labeled_text_area("訳文", "translation_text")
        )
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter)
        return tab

    def _create_vlm_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(QLabel("VLM解析結果（視覚情報の補助解析）"))
        self.vlm_result_text = QTextEdit()
        self.vlm_result_text.setReadOnly(True)
        self.vlm_result_text.setPlaceholderText(
            "「画像も解析」ボタンを押すと、VLMによる視覚情報の解析結果がここに表示されます"
        )
        layout.addWidget(self.vlm_result_text, stretch=1)
        return tab

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
        """範囲選択オーバーレイを表示する。"""
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

    def _on_source_language_changed(self, language: str) -> None:
        """元言語の変更を処理する。

        OCRエンジンの言語を切り替え、オーバーレイ翻訳キャッシュをクリアする。
        """
        self._source_language = language
        if self._ocr_service is not None:
            ocr_code = source_language_to_ocr_code(language)
            self._ocr_service.set_language(ocr_code)
        if self._overlay_service is not None:
            self._overlay_service.clear_cache()
        self._update_tab_labels()
        self.statusBar().showMessage(f"元言語を {language} に切り替えました")

    def _on_target_language_changed(self, language: str) -> None:
        """翻訳先言語の変更を処理する。"""
        self._target_language = language
        if self._overlay_service is not None:
            self._overlay_service.clear_cache()
        self._update_tab_labels()
        self.statusBar().showMessage(f"翻訳先言語を {language} に切り替えました")

    def _update_tab_labels(self) -> None:
        """現在の言語ペアに合わせてタブラベルを更新する。"""
        tabs = self.findChild(QTabWidget)
        if tabs is not None and tabs.count() >= 2:
            tabs.setTabText(0, f"{self._source_language} → {self._target_language}")
            tabs.setTabText(1, "VLM解析")

    def _show_restored_region(self) -> None:
        """起動時に復元された範囲があればステータスバーへ表示する。"""
        region = self._capture_service.region
        if region is not None:
            self.statusBar().showMessage(
                f"前回の範囲を復元しました: {region.width}x{region.height} "
                f"(左上: {region.left}, {region.top})"
            )

    def _on_auto_toggled(self, checked: bool) -> None:
        """自動翻訳トグルの ON/OFF を切り替える。

        ON: 範囲設定済みなら監視を開始。未設定ならトグルを戻す。
        OFF: 監視を停止する。
        """
        if checked:
            if not self._capture_service.has_region():
                self.statusBar().showMessage("先に範囲選択してください")
                self.auto_button.setChecked(False)
                return
            self.auto_button.setText("自動翻訳: ON")
            self._slide_monitor.start()
            self.statusBar().showMessage("自動翻訳を開始しました（スライド変化を監視中）")
        else:
            self.auto_button.setText("自動翻訳: OFF")
            self._slide_monitor.stop()
            self.statusBar().showMessage("自動翻訳を停止しました")

    def _on_auto_overlay_toggled(self, checked: bool) -> None:
        """自動オーバーレイトグルの ON/OFF を切り替える。

        ON: スライド変化検知時にオーバーレイ翻訳を自動実行する。
        OFF: 自動オーバーレイを停止する。
        自動翻訳トグルと独立して動作し、両方ON時はオーバーレイが優先。
        """
        if checked:
            if not self._capture_service.has_region():
                self.statusBar().showMessage("先に範囲選択してください")
                self.auto_overlay_button.setChecked(False)
                return
            self.auto_overlay_button.setText("自動オーバーレイ: ON")
            self._auto_overlay = True
            # 自動翻訳トグルがONの場合はOFFにする（オーバーレイが優先）
            if self.auto_button.isChecked():
                self.auto_button.setChecked(False)
            self._slide_monitor.start()
            self.statusBar().showMessage("自動オーバーレイを開始しました（スライド変化で自動更新）")
        else:
            self.auto_overlay_button.setText("自動オーバーレイ: OFF")
            self._auto_overlay = False
            # 監視は自動翻訳側が管理するため、こちらでは停止しない
            # ただし自動翻訳もOFFなら監視を停止
            if not self.auto_button.isChecked():
                self._slide_monitor.stop()
            self.statusBar().showMessage("自動オーバーレイを停止しました")

    def _on_slide_changed(self) -> None:
        """スライド変化検知時のコールバック。

        古いオーバーレイが残らないよう即座に消去してから、
        自動オーバーレイモードがONならオーバーレイ翻訳を自動実行。
        そうでなければ従来通りテキスト翻訳を自動実行。
        """
        self._overlay_window.clear_patches()
        if self._auto_overlay:
            self._on_overlay_translate()
        else:
            self._on_analyze()

    def _on_analyze(self) -> None:
        """キャプチャ＆翻訳を開始する。

        AnalysisWorker を QThreadPool で起動し、
        シグナルを各ハンドラへ接続する。
        解析中はボタンを無効化して二重実行を防ぐ。
        オーバーレイ表示中は先に隠してからキャプチャする
        （パッチが写り込むのを防ぐため）。
        """
        if self._analyzing:
            self.statusBar().showMessage("解析中です。完了をお待ちください")
            return
        if not self._capture_service.has_region():
            self.statusBar().showMessage("先に範囲選択してください")
            return

        # オーバーレイが見えている場合は隠してから実行
        self._run_after_overlay_hidden(self._start_analysis)

    def _start_analysis(self) -> None:
        """翻訳ワーカーを実際に起動する（オーバーレイ非表示確認後）。"""
        self._set_analyzing(True)
        self.translation_text.clear()
        self.visual_type_label.setText("Visual Type: ---")
        self.recommendation_label.setText("Recommendation: ---")
        self.vlm_button.setEnabled(False)
        worker = AnalysisWorker(
            self._analysis_service,
            source_language=self._source_language,
            target_language=self._target_language,
        )
        worker.signals.ocr_text.connect(self._on_ocr_text)
        worker.signals.partial.connect(self._on_partial)
        worker.signals.finished.connect(self._on_translation_finished)
        worker.signals.visual.connect(self._on_visual_result)
        worker.signals.failed.connect(self._on_analysis_failed)
        self._worker = worker
        self._thread_pool.start(worker)

    def _set_analyzing(self, analyzing: bool) -> None:
        """解析中状態を切り替え、監視の一時停止/再開も行う。"""
        self._analyzing = analyzing
        self.analyze_button.setEnabled(not analyzing)
        # 解析中は監視を一時停止し、多重実行を防ぐ
        if analyzing:
            if self._slide_monitor.is_active:
                self._slide_monitor.pause()
            self.statusBar().showMessage("翻訳中...（キャプチャ → OCR → AI）")
        elif self.auto_button.isChecked():
            self._slide_monitor.resume()

    def _on_ocr_text(self, text: str) -> None:
        self.source_text.setPlainText(text)
        self.statusBar().showMessage("OCR完了。翻訳中...")

    def _on_partial(self, chunk: str) -> None:
        """ストリーミング翻訳の部分チャンクを翻訳欄に追記する。"""
        cursor = self.translation_text.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(chunk)
        self.translation_text.setTextCursor(cursor)

    def _on_translation_finished(self, full_text: str) -> None:
        """翻訳完了時に最終全文を表示し、VLMボタンの有効/無効を判定する。"""
        self._worker = None
        self._set_analyzing(False)
        self.translation_text.setPlainText(full_text)
        self._last_image_path = self._analysis_service.last_image_path
        self.statusBar().showMessage("翻訳完了")

    def _on_visual_result(self, visual: SlideVisualAnalysis) -> None:
        """スライド判定結果を表示し、VLMボタンの有効/無効を切り替える。

        TEXT_ONLY の場合はVLM解析が不要なためボタンを無効化し、
        MIXED_SLIDE / VISUAL_HEAVY の場合は有効化する。
        """
        self._last_visual = visual
        self.visual_type_label.setText(
            f"Visual Type: {visual.visual_type.value}"
        )
        self.recommendation_label.setText(
            f"Recommendation: {visual.recommendation}"
        )
        logger.info(
            "スライド判定結果: type=%s, text_ratio=%.2f, color_ratio=%.2f, lines=%d",
            visual.visual_type.value,
            visual.text_area_ratio,
            visual.color_region_ratio,
            visual.line_count,
        )

        if visual.visual_type == SlideVisualType.TEXT_ONLY:
            self.vlm_button.setEnabled(False)
        else:
            self.vlm_button.setEnabled(True)

    def _on_analysis_failed(self, message: str) -> None:
        self._worker = None
        self._set_analyzing(False)
        self.statusBar().showMessage(f"解析失敗: {message}")

    def _on_vlm_analyze(self) -> None:
        """VLM画像解析を開始する。

        VlmWorker を QThreadPool で起動し、
        シグナルを各ハンドラへ接続する。
        VLMモデル未インストール時はステータスバーで警告する。
        """
        if self._vlm_analyzing:
            self.statusBar().showMessage("VLM解析中です。完了をお待ちください")
            return
        if self._vlm_analysis_service is None:
            self.statusBar().showMessage("VLM解析サービスが設定されていません")
            return
        if not self._vlm_analysis_service.is_available():
            self.statusBar().showMessage(
                f"VLMモデルが利用できません。Ollamaで {self._config.vlm.model} をpullしてください"
            )
            return
        if self._last_image_path is None:
            self.statusBar().showMessage("先にキャプチャ＆翻訳を実行してください")
            return

        self._start_vlm_worker()

    def _start_vlm_worker(self) -> None:
        """VLM解析ワーカーを起動する（前提条件は呼び出し側で検証済み）。"""
        self._set_vlm_analyzing(True)
        self.vlm_result_text.clear()
        worker = VlmWorker(
            self._vlm_analysis_service,
            self._last_image_path,
            source_language=self._source_language,
            target_language=self._target_language,
        )
        worker.signals.partial.connect(self._on_vlm_partial)
        worker.signals.finished.connect(self._on_vlm_finished)
        worker.signals.failed.connect(self._on_vlm_failed)
        self._vlm_worker = worker
        self._thread_pool.start(worker)

    def _set_vlm_analyzing(self, analyzing: bool) -> None:
        self._vlm_analyzing = analyzing
        can_enable = (
            not analyzing
            and self._last_visual is not None
            and self._last_visual.visual_type != SlideVisualType.TEXT_ONLY
        )
        self.vlm_button.setEnabled(can_enable)
        if analyzing:
            self.statusBar().showMessage("VLM解析中...")

    def _on_vlm_partial(self, chunk: str) -> None:
        """ストリーミングVLM解析の部分チャンクをVLM結果欄に追記する。"""
        cursor = self.vlm_result_text.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(chunk)
        self.vlm_result_text.setTextCursor(cursor)

    def _on_vlm_finished(self, full_text: str) -> None:
        self._vlm_worker = None
        self._set_vlm_analyzing(False)
        self.vlm_result_text.setPlainText(full_text)
        self.statusBar().showMessage("VLM解析完了")

    def _on_vlm_failed(self, message: str) -> None:
        self._vlm_worker = None
        self._set_vlm_analyzing(False)
        self.statusBar().showMessage(f"VLM解析失敗: {message}")

    def _run_after_overlay_hidden(self, callback) -> None:
        """オーバーレイを隠してからコールバックを実行する。

        オーバーレイ表示中にキャプチャすると翻訳パッチ自体が
        写り込むため、隠した後に少し待って（画面合成の反映待ち）
        から実行する。非表示なら即実行。
        """
        if self._overlay_window.isVisible():
            self._overlay_window.hide()
            QTimer.singleShot(200, callback)
        else:
            callback()

    def _on_overlay_translate(self) -> None:
        """オーバーレイ翻訳を開始する。

        キャプチャ → OCR（座標付き）→ 行バッチ翻訳をバックグラウンドで
        実行し、完了後に翻訳パッチを元の映像の上に重ねて表示する。
        """
        if self._overlay_analyzing:
            self.statusBar().showMessage("オーバーレイ翻訳中です。完了をお待ちください")
            return
        if self._overlay_service is None:
            self.statusBar().showMessage("オーバーレイ翻訳サービスが設定されていません")
            return
        if not self._capture_service.has_region():
            self.statusBar().showMessage("先に範囲選択してください")
            return

        # ユーザー操作・スライド変化による開始なので再翻訳カウンタをリセット
        self._overlay_retranslate_count = 0
        # 既存のオーバーレイを隠してからキャプチャする
        self._run_after_overlay_hidden(self._start_overlay_translation)

    def _start_overlay_translation(self) -> None:
        """オーバーレイ翻訳ワーカーを実際に起動する（ストリーミング対応）。"""
        self._overlay_analyzing = True
        self.overlay_button.setEnabled(False)
        self._streaming_patch_count = 0
        # オーバーレイ翻訳中はスライド監視を一時停止
        if self._slide_monitor.is_active:
            self._slide_monitor.pause()
        self.statusBar().showMessage("オーバーレイ翻訳中...（キャプチャ → OCR → 翻訳）")

        worker = OverlayWorker(
            self._overlay_service,
            source_language=self._source_language,
            target_language=self._target_language,
        )
        worker.signals.prepared.connect(self._on_overlay_prepared)
        worker.signals.patch_ready.connect(self._on_overlay_patch_ready)
        worker.signals.finished.connect(self._on_overlay_finished)
        worker.signals.failed.connect(self._on_overlay_failed)
        self._overlay_worker = worker
        self._thread_pool.start(worker)

    def _on_overlay_prepared(self, region, image_path) -> None:
        """キャプチャ範囲が確定したらオーバーレイウィンドウを準備する。

        ストリーミング表示の事前準備: ウィンドウ位置を確定し、
        パッチが追加されるたびに即座に描画できるようにする。
        また、VLM解析を非同期で開始する。
        """
        self._overlay_window.prepare_region(region)
        self._last_image_path = image_path
        # VLM解析サービスが利用可能なら自動で補足説明を開始
        self._maybe_start_vlm_for_overlay()

    def _on_overlay_patch_ready(self, patch: OverlayPatch) -> None:
        """1パッチの翻訳が完了したら即座にオーバーレイに追加表示する。"""
        self._overlay_window.add_patch(patch)
        self._streaming_patch_count += 1
        self.statusBar().showMessage(
            f"オーバーレイ翻訳中...（{self._streaming_patch_count} 箇所表示）"
        )

    def _maybe_start_vlm_for_overlay(self) -> None:
        """オーバーレイ表示中にVLM解析を自動で開始する。

        VLM解析サービスが利用可能で、VLMモデルがインストールされており、
        かつVLM解析中でない場合に実行する。
        結果はVLM解析タブに表示され、ユーザーが図・グラフの補足説明を確認できる。
        """
        if self._vlm_analysis_service is None:
            return
        if self._vlm_analyzing:
            return
        if not self._vlm_analysis_service.is_available():
            return
        if self._last_image_path is None:
            return

        self._start_vlm_worker()
        logger.info("オーバーレイ表示中にVLM解析を自動開始")

    def _finish_overlay_run(self) -> None:
        """オーバーレイ翻訳の完了・失敗に共通の後処理。

        ワーカー参照の解放、ボタンの再有効化、スライド監視の再開を行う。
        """
        self._overlay_worker = None
        self._overlay_analyzing = False
        self.overlay_button.setEnabled(True)
        if self.auto_button.isChecked() or self._auto_overlay:
            self._slide_monitor.resume()

    def _on_overlay_finished(self, patches: list[OverlayPatch]) -> None:
        """全パッチ生成完了時の処理。

        ストリーミング表示済みのため再描画はせず、ステータスのみ更新する。
        翻訳中に画面が変わっていた可能性があるため、
        再キャプチャして必要なら自動で再翻訳する。
        """
        self._finish_overlay_run()
        if not patches:
            self.statusBar().showMessage("表示できる翻訳パッチがありません")
        else:
            self.statusBar().showMessage(f"オーバーレイ表示中（{len(patches)} 箇所）")
        # 翻訳中の画面変化を確認し、必要なら再翻訳
        self._check_overlay_retranslate()

    def _check_overlay_retranslate(self) -> None:
        """翻訳完了後に画面が変わっていないか確認し、必要なら再翻訳する。

        翻訳に使ったキャプチャ画像と現在の画面の dHash を比較する。
        オーバーレイ自身が写り込むと必ず「変化あり」になるため、
        一瞬隠してから比較する。連続再翻訳は上限で打ち切る。
        """
        if self._overlay_retranslate_count >= _MAX_OVERLAY_RETRANSLATES:
            logger.info("再翻訳の連続上限に達したためチェックをスキップ")
            return
        if self._last_image_path is None:
            return
        if not self._capture_service.has_region():
            return

        # オーバーレイが写り込まないよう隠してから比較する
        self._run_after_overlay_hidden(self._do_overlay_retranslate_check)

    def _do_overlay_retranslate_check(self) -> None:
        """現在の画面と翻訳元画像を比較し、変化があれば再翻訳を開始する。"""
        region = self._capture_service.region
        last_hash = (
            compute_image_hash(self._last_image_path)
            if self._last_image_path is not None
            else None
        )
        current_hash = compute_region_hash(region) if region is not None else None

        if last_hash is None or current_hash is None:
            # 比較不能 → オーバーレイを再表示して終了
            self._overlay_window.show()
            return

        threshold = self._config.capture.auto_hash_threshold
        if hash_distance(last_hash, current_hash) <= threshold:
            # 画面は変わっていない → オーバーレイを再表示
            self._overlay_window.show()
            return

        # 画面が変わっていた → 古いパッチを消して再翻訳
        logger.info("翻訳中に画面変化を検出。再翻訳を開始します")
        self._overlay_retranslate_count += 1
        self._overlay_window.clear_patches()
        self.statusBar().showMessage("画面変化を検出。再翻訳します...")
        self._start_overlay_translation()

    def _on_overlay_failed(self, message: str) -> None:
        """オーバーレイ翻訳失敗時の後処理。"""
        self._finish_overlay_run()
        self.statusBar().showMessage(f"オーバーレイ翻訳失敗: {message}")

    def _on_overlay_clear(self) -> None:
        """オーバーレイ表示を消す。"""
        self._overlay_window.clear_patches()
        self.statusBar().showMessage("オーバーレイを消去しました")

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt命名規則)
        """ウィンドウクローズ時に監視・ホットキー・オーバーレイを停止し、ワーカーの完了を待機する。"""
        self._slide_monitor.stop()
        self._hotkey_listener.stop()
        self._overlay_window.close()
        if (
            self._worker is not None
            or self._vlm_worker is not None
            or self._overlay_worker is not None
        ):
            logger.info("ワーカーの完了を待機中...")
            self._thread_pool.waitForDone()
            self._worker = None
            self._vlm_worker = None
            self._overlay_worker = None
        super().closeEvent(event)
