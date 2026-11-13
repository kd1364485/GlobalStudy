"""翻訳パッチを画面上に重ねて表示するオーバーレイウィンドウ。

キャプチャ範囲と同じ位置に透明ウィンドウを配置し、
翻訳パッチ部分だけを不透明に描画する。
クリック透過（WindowTransparentForInput）のため、
下の動画・アプリの操作を妨げない。
"""

from PySide6.QtCore import QRect, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPainter, QTextOption
from PySide6.QtWidgets import QWidget

from globalstudy.models.overlay import OverlayPatch
from globalstudy.models.region import CaptureRegion

# パッチ描画時のフォントサイズ探索範囲（論理ピクセル）
_MIN_FONT_PX = 16
_FONT_HEIGHT_RATIO = 0.72  # パッチ高さに対する初期フォントサイズの比率
# テキスト幅がボックス幅の何倍を超えると折り返し表示に切り替えるか
_WRAP_THRESHOLD = 1.3
# 折り返し表示で試す最大行数
_MAX_WRAP_LINES = 4


class OverlayWindow(QWidget):
    """翻訳パッチをキャプチャ範囲上に重ねて描画するウィンドウ。

    フレームなし・常時最前面・クリック透過で動作するため、
    表示中も下のアプリを通常どおり操作できる。
    パッチはキャプチャ範囲基準の物理ピクセル座標で受け取り、
    描画時に論理ピクセルへ変換する。
    """

    def __init__(self) -> None:
        super().__init__()
        # 表示中のパッチ（論理ピクセル座標へ変換済み）
        self._patches: list[tuple[QRect, OverlayPatch]] = []
        # 物理→論理ピクセル変換用のスケール（prepare_region で確定）
        self._scale: float = 1.0
        self._setup_window()

    def _setup_window(self) -> None:
        """透明・最前面・クリック透過のウィンドウ属性を設定する。"""
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            # マウス入力を下のウィンドウへ透過させる
            | Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        # フォーカスを奪わない（下のアプリの操作を邪魔しない）
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

    def prepare_region(self, region: CaptureRegion) -> None:
        """キャプチャ範囲にウィンドウを配置し、パッチを空で表示開始する。

        ストリーミング表示の事前準備: ウィンドウ位置を確定し、
        add_patch で順次パッチを追加できるようにする。
        """
        self._scale = self._scale_for_region(region)
        self.setGeometry(self._to_logical_rect(
            region.left, region.top, region.width, region.height
        ))
        self._patches = []
        self.show()
        self.update()

    def add_patch(self, patch: OverlayPatch) -> None:
        """パッチを1つ追加して再描画する（ストリーミング逐次表示用）。"""
        rect = self._to_logical_rect(
            patch.left, patch.top, patch.width, patch.height
        )
        self._patches.append((rect, patch))
        self.update()

    def clear_patches(self) -> None:
        """パッチを消してウィンドウを隠す。"""
        self._patches = []
        self.hide()

    def _to_logical_rect(
        self, left: int, top: int, width: int, height: int
    ) -> QRect:
        """物理ピクセル座標を論理ピクセルの QRect へ変換する。"""
        return QRect(
            round(left / self._scale),
            round(top / self._scale),
            round(width / self._scale),
            round(height / self._scale),
        )

    @staticmethod
    def _scale_for_region(region: CaptureRegion) -> float:
        """範囲が属するスクリーンの devicePixelRatio を返す。

        RegionSelectorOverlay の論理→物理変換と対になる逆変換用。
        """
        # 物理座標を仮の論理座標（primary の scale）で割って画面を探す
        primary = QGuiApplication.primaryScreen()
        scale = primary.devicePixelRatio() if primary else 1.0
        for screen in QGuiApplication.screens():
            geo = screen.geometry()
            dpr = screen.devicePixelRatio()
            # スクリーンの物理ピクセル矩形に範囲の左上が含まれるか判定
            phys = QRect(
                round(geo.left() * dpr),
                round(geo.top() * dpr),
                round(geo.width() * dpr),
                round(geo.height() * dpr),
            )
            if phys.contains(region.left, region.top):
                return dpr
        return scale

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt命名規則)
        """全パッチを2パスで描画する（背景 → テキスト）。

        パス1で全パッチの背景を塗りつぶして元の英文を隠し、
        パス2で全パッチの日本語テキストを描画する。
        パッチごとに背景→テキストを繰り返すと、後のパッチの背景が
        先に描いたテキストを隠してしまうため、必ず2パスに分ける。

        各行のフォントサイズは元テキストのボックス高さ基準で決定し、
        元の英文と同じサイズ感を維持する。日本語訳が幅に収まらない
        場合はフォントを縮小せず折り返し表示で対応する。
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        # 各パッチの描画情報を事前計算（実際のテキスト範囲に背景を合わせる）
        draw_items: list[tuple[QRectF, QFont, bool, OverlayPatch]] = []
        for rect, patch in self._patches:
            font, need_wrap = self._fit_font(painter, rect, patch.text)
            painter.setFont(font)
            metrics = painter.fontMetrics()
            draw_rect = QRectF(rect)
            if not need_wrap:
                # 単行ではみ出す場合、背景を右方向へ拡張
                text_width = metrics.horizontalAdvance(patch.text)
                if text_width > draw_rect.width():
                    draw_rect.setWidth(text_width)
            draw_items.append((draw_rect, font, need_wrap, patch))

        # パス1: 全パッチの背景を塗りつぶし（元の英文を隠す）
        for draw_rect, _font, _wrap, patch in draw_items:
            painter.fillRect(draw_rect, QColor(*patch.bg_rgb))

        # パス2: 全パッチの日本語テキストを描画（背景に隠されない）
        for draw_rect, font, need_wrap, patch in draw_items:
            painter.setFont(font)
            painter.setPen(QColor(*patch.fg_rgb))
            if need_wrap:
                # 折り返し表示: QTextOption でワードラップを有効化
                option = QTextOption()
                option.setWrapMode(QTextOption.WrapMode.WrapAnywhere)
                option.setAlignment(
                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
                )
                painter.drawText(draw_rect, patch.text, option)
            else:
                painter.drawText(
                    draw_rect,
                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                    patch.text,
                )

    @staticmethod
    def _fit_font(painter: QPainter, rect: QRect, text: str) -> tuple[QFont, bool]:
        """元テキストのボックス高さ基準のフォントサイズを求める。

        フォントサイズはボックス高さから決定し（元テキストと同じサイズ感）、
        幅に収まらない場合は折り返し表示に切り替える。
        折り返し時は行数に応じてフォントを縮小し、元のボックス高さ内に
        収める（下方向へはみ出して他の行と重なるのを防ぐため）。

        Returns:
            (font, need_wrap) のタプル。need_wrap が True の場合は
            折り返し描画を行うべきことを示す。
        """
        font = QFont()
        initial_size = max(int(rect.height() * _FONT_HEIGHT_RATIO), _MIN_FONT_PX)
        font.setPixelSize(initial_size)
        painter.setFont(font)
        width = painter.fontMetrics().horizontalAdvance(text)

        if width <= rect.width():
            # ボックス幅に収まる → そのまま単行表示
            return font, False

        if width <= rect.width() * _WRAP_THRESHOLD:
            # わずかなはみ出し → 単行表示のまま（見た目の違和感が少ない）
            return font, False

        # 大幅にはみ出す → 折り返し表示。
        # n行に折り返した時にボックス高さへ収まる最大サイズを探す
        # （フォントをn分の1に縮小すれば高さn行分がボックス内に収まる）
        for n_lines in range(2, _MAX_WRAP_LINES + 1):
            size = max(int(rect.height() * _FONT_HEIGHT_RATIO / n_lines), _MIN_FONT_PX)
            font.setPixelSize(size)
            painter.setFont(font)
            width = painter.fontMetrics().horizontalAdvance(text)
            line_height = painter.fontMetrics().lineSpacing()
            # このサイズでn行に折り返した場合、幅と高さの両方に収まるか
            if width <= rect.width() * n_lines and line_height * n_lines <= rect.height():
                return font, True
            if size == _MIN_FONT_PX:
                break

        # 下限サイズでも収まらない場合は下限サイズで折り返し表示
        # （多少はみ出すが可読性を優先）
        font.setPixelSize(_MIN_FONT_PX)
        return font, True
