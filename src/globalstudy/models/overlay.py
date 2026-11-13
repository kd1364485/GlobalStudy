"""オーバーレイ翻訳のデータモデル。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class OverlayPatch:
    """元テキストの上に重ねる翻訳パッチ1枚分の情報。

    座標はキャプチャ範囲の左上を原点とした物理ピクセル座標。
    表示時に論理ピクセル（Qt座標）へ変換される。

    Attributes:
        left: パッチ左端（範囲内の物理ピクセル座標）。
        top: パッチ上端（範囲内の物理ピクセル座標）。
        width: パッチの幅（物理ピクセル）。
        height: パッチの高さ（物理ピクセル）。
        text: 表示する日本語訳。
        bg_rgb: 背景色（元スライドの周辺色をサンプリングした RGB タプル）。
        fg_rgb: 文字色（背景とのコントラストで白/黒を自動選択した RGB タプル）。
    """

    left: int
    top: int
    width: int
    height: int
    text: str
    bg_rgb: tuple[int, int, int]
    fg_rgb: tuple[int, int, int]
