"""キャプチャユースケース。

選択範囲の保持と、範囲キャプチャの実行を担当する。
UI からはこのサービスのみを利用する。
"""

from pathlib import Path

from globalstudy.capture.screen_capturer import ScreenCapturer
from globalstudy.config import Config
from globalstudy.models.region import CaptureRegion
from globalstudy.utils.logger import get_logger

logger = get_logger(__name__)


class CaptureService:
    """範囲選択の状態管理とキャプチャ実行を提供する。"""

    def __init__(self, config: Config) -> None:
        self._capturer = ScreenCapturer(config)
        self._region: CaptureRegion | None = None

    @property
    def region(self) -> CaptureRegion | None:
        return self._region

    def set_region(self, region: CaptureRegion) -> None:
        """キャプチャ対象範囲を設定する。"""
        self._region = region
        logger.info("キャプチャ範囲設定: %s", region)

    def has_region(self) -> bool:
        return self._region is not None

    def capture(self) -> Path:
        """設定済み範囲をキャプチャし、保存先パスを返す。

        Raises:
            RuntimeError: 範囲が未設定の場合。
            CaptureError: キャプチャに失敗した場合。
        """
        if self._region is None:
            raise RuntimeError("キャプチャ範囲が未設定です。先に範囲選択してください。")
        return self._capturer.capture(self._region)
