"""画面キャプチャ範囲のデータモデル。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class CaptureRegion:
    """スクリーン上の矩形範囲（物理ピクセル座標）。"""

    left: int
    top: int
    width: int
    height: int

    def is_valid(self) -> bool:
        """幅・高さが正の値であるかを検証する。"""
        return self.width > 0 and self.height > 0
