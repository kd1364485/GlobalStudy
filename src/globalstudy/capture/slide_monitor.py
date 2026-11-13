"""スライド変化の自動検知モニター。

キャプチャ範囲を一定間隔で軽量監視し、dHash（差分ハッシュ）の
ハミング距離でスライドの切り替わりを検知する。
変化が2回連続で安定して観測されたとき slide_changed シグナルを発行する
（スライドのアニメーション遷移中の誤検知を防ぐため）。
"""

from collections.abc import Callable

import cv2
import mss
import numpy as np
from PySide6.QtCore import QObject, QTimer, Signal

from globalstudy.config import Config
from globalstudy.models.region import CaptureRegion
from globalstudy.utils.logger import get_logger

logger = get_logger(__name__)

# dHash の縮小サイズ（9x8 → 横方向の隣接差分で 64bit ハッシュ）
_HASH_WIDTH = 9
_HASH_HEIGHT = 8


def compute_region_hash(region: CaptureRegion) -> np.ndarray | None:
    """画面範囲をキャプチャし、dHash（64bit 真偽値配列）を計算する。

    ファイル保存を行わないインメモリ処理のため軽量。
    失敗時は None を返す。
    """
    try:
        with mss.mss() as sct:
            shot = sct.grab(
                {
                    "left": region.left,
                    "top": region.top,
                    "width": region.width,
                    "height": region.height,
                }
            )
        image = np.frombuffer(shot.bgra, dtype=np.uint8).reshape(
            shot.height, shot.width, 4
        )
        gray = cv2.cvtColor(image, cv2.COLOR_BGRA2GRAY)
        return _dhash_from_gray(gray)
    except Exception as exc:
        logger.debug("監視キャプチャに失敗: %s", exc)
        return None


def compute_image_hash(image_path) -> np.ndarray | None:
    """画像ファイルの dHash（64bit 真偽値配列）を計算する。

    読み込み失敗時は None を返す。
    """
    image = cv2.imread(str(image_path))
    if image is None:
        return None
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return _dhash_from_gray(gray)


def hash_distance(hash_a: np.ndarray, hash_b: np.ndarray) -> int:
    """2つのハッシュ間のハミング距離（異なるbit数）を返す。"""
    return int(np.count_nonzero(hash_a != hash_b))


def _dhash_from_gray(gray: np.ndarray) -> np.ndarray:
    """グレースケール画像から dHash を計算する。"""
    small = cv2.resize(
        gray, (_HASH_WIDTH, _HASH_HEIGHT), interpolation=cv2.INTER_AREA
    )
    # 横方向の隣接ピクセル比較で 8x8=64bit のハッシュを生成
    return (small[:, 1:] > small[:, :-1]).flatten()


class SlideMonitor(QObject):
    """スライド変化を監視し、検知時に slide_changed シグナルを発行する。

    QTimer でメインスレッド上で動作する。1回の監視処理は
    小範囲のキャプチャとハッシュ計算のみで数ミリ秒程度のため、
    GUI をブロックしない。
    """

    slide_changed = Signal()

    def __init__(
        self,
        config: Config,
        region_provider: Callable[[], CaptureRegion | None],
    ) -> None:
        """モニターを初期化する。

        Args:
            config: アプリ設定（監視間隔・閾値を参照）。
            region_provider: 監視対象範囲を返すコールバック
                （未設定時は None を返す）。
        """
        super().__init__()
        self._region_provider = region_provider
        self._threshold = config.capture.auto_hash_threshold
        self._timer = QTimer(self)
        self._timer.setInterval(config.capture.auto_interval_ms)
        self._timer.timeout.connect(self._on_tick)
        # 確定済みスライドのハッシュ
        self._last_hash: np.ndarray | None = None
        # 変化候補のハッシュ（次のティックで安定していれば確定）
        self._pending_hash: np.ndarray | None = None

    @property
    def is_active(self) -> bool:
        """監視が動作中かを返す。"""
        return self._timer.isActive()

    def start(self) -> None:
        """監視を開始する。ハッシュ状態はリセットされる。"""
        self._last_hash = None
        self._pending_hash = None
        self._timer.start()
        logger.info("スライド監視開始（間隔: %dms）", self._timer.interval())

    def stop(self) -> None:
        """監視を停止する。"""
        self._timer.stop()
        logger.info("スライド監視停止")

    def pause(self) -> None:
        """監視を一時停止する（ハッシュ状態は保持）。

        解析実行中に呼び出し、多重解析を防ぐ。
        """
        self._timer.stop()

    def resume(self) -> None:
        """一時停止した監視を再開する。

        pause 中にスライドが変わっていれば、再開後の最初の
        ティックで変化候補として検知される。
        """
        self._timer.start()

    def _on_tick(self) -> None:
        """監視間隔ごとに呼ばれ、変化を判定する。"""
        region = self._region_provider()
        if region is None:
            return
        current = compute_region_hash(region)
        if current is None:
            return

        # 初回は基準ハッシュとして記録するだけ
        if self._last_hash is None:
            self._last_hash = current
            return

        # 前回確定スライドと同じ → 変化なし
        if hash_distance(current, self._last_hash) <= self._threshold:
            self._pending_hash = None
            return

        # 変化候補と一致 → 新スライドが安定したとみなし確定・通知
        if (
            self._pending_hash is not None
            and hash_distance(current, self._pending_hash) <= self._threshold
        ):
            self._last_hash = current
            self._pending_hash = None
            logger.info("スライド変化を検知")
            self.slide_changed.emit()
        else:
            # 初回の変化観測。次のティックで安定確認する
            self._pending_hash = current
