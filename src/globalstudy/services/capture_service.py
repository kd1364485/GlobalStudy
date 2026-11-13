"""キャプチャユースケース。

選択範囲の保持と、範囲キャプチャの実行を担当する。
範囲はJSONファイルに永続化され、次回起動時に自動復元される。
UI からはこのサービスのみを利用する。
"""

import json
from dataclasses import asdict
from pathlib import Path

from globalstudy.capture.screen_capturer import ScreenCapturer
from globalstudy.config import Config
from globalstudy.models.region import CaptureRegion
from globalstudy.utils.logger import get_logger

logger = get_logger(__name__)


class CaptureService:
    """範囲選択の状態管理とキャプチャ実行を提供する。

    UI層からはこのサービスのみを利用する。ScreenCapturer への
    委譲と、キャプチャ範囲の保持を担当する。
    """

    def __init__(self, config: Config) -> None:
        self._capturer = ScreenCapturer(config)
        self._region_file = config.paths.region_file
        # 現在設定されているキャプチャ範囲（前回保存分があれば復元）
        self._region: CaptureRegion | None = self._load_saved_region()

    @property
    def region(self) -> CaptureRegion | None:
        """現在設定されているキャプチャ範囲を返す（未設定時は None）。"""
        return self._region

    def set_region(self, region: CaptureRegion) -> None:
        """キャプチャ対象範囲を設定し、ファイルに保存する。"""
        self._region = region
        self._save_region(region)
        logger.info("キャプチャ範囲設定: %s", region)

    def has_region(self) -> bool:
        """キャプチャ範囲が設定済みかを返す。"""
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

    def _save_region(self, region: CaptureRegion) -> None:
        """範囲をJSONファイルに保存する（失敗しても動作は継続）。"""
        try:
            self._region_file.parent.mkdir(parents=True, exist_ok=True)
            self._region_file.write_text(
                json.dumps(asdict(region)), encoding="utf-8"
            )
        except OSError as exc:
            logger.warning("範囲の保存に失敗しました: %s", exc)

    def _load_saved_region(self) -> CaptureRegion | None:
        """保存済みの範囲を読み込む（なければ None）。"""
        if not self._region_file.exists():
            return None
        try:
            data = json.loads(self._region_file.read_text(encoding="utf-8"))
            region = CaptureRegion(
                left=int(data["left"]),
                top=int(data["top"]),
                width=int(data["width"]),
                height=int(data["height"]),
            )
        except (OSError, ValueError, KeyError, TypeError) as exc:
            logger.warning("保存済み範囲の読み込みに失敗しました: %s", exc)
            return None
        if not region.is_valid():
            return None
        logger.info("保存済みのキャプチャ範囲を復元: %s", region)
        return region
