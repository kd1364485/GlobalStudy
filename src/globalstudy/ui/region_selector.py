"""範囲選択オーバーレイ。

全画面の半透明ウィジェットを表示し、ドラッグで矩形範囲を選択する。
選択確定時に region_selected シグナルを発行する。Esc でキャンセル。
"""

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication, QKeyEvent, QMouseEvent, QPainter
from PySide6.QtWidgets import QWidget

from globalstudy.models.region import CaptureRegion
from globalstudy.utils.logger import get_logger

logger = get_logger(__name__)

_OVERLAY_ALPHA = 100
_BORDER_COLOR = QColor(0, 160, 255)
_BORDER_WIDTH = 2


class RegionSelectorOverlay(QWidget):
    """ドラッグによる画面範囲選択を行う全画面オーバーレイ。"""

    region_selected = Signal(CaptureRegion)
    selection_cancelled = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._origin = QPoint()
        self._current = QPoint()
        self._selecting = False
        self._setup_window()

    def _setup_window(self) -> None:
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setGeometry(self._virtual_screen_rect())

    @staticmethod
    def _virtual_screen_rect() -> QRect:
        """全モニタを含む仮想スクリーン全体の矩形を返す。"""
        rect = QRect()
        for screen in QGuiApplication.screens():
            rect = rect.united(screen.geometry())
        return rect

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt命名規則)
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, _OVERLAY_ALPHA))

        if self._selecting:
            selection = QRect(self._origin, self._current).normalized()
            painter.setCompositionMode(
                QPainter.CompositionMode.CompositionMode_Clear
            )
            painter.fillRect(selection, Qt.GlobalColor.transparent)
            painter.setCompositionMode(
                QPainter.CompositionMode.CompositionMode_SourceOver
            )
            pen = painter.pen()
            pen.setColor(_BORDER_COLOR)
            pen.setWidth(_BORDER_WIDTH)
            painter.setPen(pen)
            painter.drawRect(selection)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._origin = event.position().toPoint()
            self._current = self._origin
            self._selecting = True
            self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._selecting:
            self._current = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton or not self._selecting:
            return
        self._selecting = False
        selection = QRect(self._origin, self._current).normalized()
        region = self._to_capture_region(selection)
        self.close()

        if region.is_valid():
            logger.debug("範囲選択確定: %s", region)
            self.region_selected.emit(region)
        else:
            logger.debug("範囲選択キャンセル（サイズゼロ）")
            self.selection_cancelled.emit()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            logger.debug("範囲選択キャンセル（Esc）")
            self.close()
            self.selection_cancelled.emit()

    def _to_capture_region(self, selection: QRect) -> CaptureRegion:
        """ウィジェット座標をスクリーンの物理ピクセル座標へ変換する。"""
        top_left_global = self.mapToGlobal(selection.topLeft())
        screen = QGuiApplication.screenAt(top_left_global) or QGuiApplication.primaryScreen()
        scale = screen.devicePixelRatio()
        return CaptureRegion(
            left=round(top_left_global.x() * scale),
            top=round(top_left_global.y() * scale),
            width=round(selection.width() * scale),
            height=round(selection.height() * scale),
        )
