"""画面キャプチャ機能。

mss によるワンショットキャプチャを提供する。
将来リアルタイム化する場合は dxcam 実装へ差し替え可能なよう、
capture(region) -> Path のインターフェースを維持する。
"""

from datetime import datetime
from pathlib import Path

import mss
import mss.tools

from globalstudy.config import Config
from globalstudy.models.region import CaptureRegion
from globalstudy.utils.logger import get_logger

logger = get_logger(__name__)

_FILENAME_TIMESTAMP_FORMAT = "%Y%m%d_%H%M%S_%f"


class CaptureError(Exception):
    """キャプチャ失敗時に送出される例外。"""


class ScreenCapturer:
    """指定範囲のスクリーンショットを取得し、画像ファイルとして保存する。"""

    def __init__(self, config: Config) -> None:
        self._config = config

    def capture(self, region: CaptureRegion) -> Path:
        """指定範囲をキャプチャして保存し、保存先パスを返す。

        Raises:
            CaptureError: 範囲が不正、またはキャプチャに失敗した場合。
        """
        if not region.is_valid():
            raise CaptureError(f"キャプチャ範囲が不正です: {region}")

        output_path = self._build_output_path()
        try:
            with mss.mss() as screen:
                shot = screen.grab(
                    {
                        "left": region.left,
                        "top": region.top,
                        "width": region.width,
                        "height": region.height,
                    }
                )
                mss.tools.to_png(shot.rgb, shot.size, output=str(output_path))
        except Exception as exc:
            raise CaptureError(f"キャプチャに失敗しました: {exc}") from exc

        logger.info("キャプチャ保存: %s (%dx%d)", output_path, region.width, region.height)
        return output_path

    def _build_output_path(self) -> Path:
        timestamp = datetime.now().strftime(_FILENAME_TIMESTAMP_FORMAT)
        extension = self._config.capture.image_format
        return self._config.paths.capture_dir / f"capture_{timestamp}.{extension}"
