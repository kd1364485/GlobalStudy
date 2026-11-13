"""グローバルホットキー監視。

pynput のリスナースレッドで検知し、Qt シグナルで
メインスレッドへ安全に通知する。
"""

from pynput import keyboard
from PySide6.QtCore import QObject, Signal

from globalstudy.utils.logger import get_logger

logger = get_logger(__name__)


class HotkeyListener(QObject):
    """グローバルホットキーを監視し、検知時に triggered シグナルを発行する。

    pynput のリスナースレッドでキー入力を検知し、
    Qt シグナル経由でメインスレッドへ安全に通知する。
    """

    triggered = Signal()

    def __init__(self, hotkey: str) -> None:
        super().__init__()
        # 'ctrl+shift+q' → '<ctrl>+<shift>+q' へ変換
        self._hotkey_spec = self._to_pynput_format(hotkey)
        self._listener: keyboard.GlobalHotKeys | None = None

    def start(self) -> None:
        """監視を開始する。二重起動は無視する。"""
        if self._listener is not None:
            logger.warning("ホットキーリスナーは既に起動しています")
            return
        self._listener = keyboard.GlobalHotKeys(
            {self._hotkey_spec: self._on_hotkey}
        )
        self._listener.start()
        logger.info("ホットキー監視開始: %s", self._hotkey_spec)

    def stop(self) -> None:
        """監視を停止する。"""
        if self._listener is None:
            return
        self._listener.stop()
        self._listener = None
        logger.info("ホットキー監視停止")

    def _on_hotkey(self) -> None:
        """ホットキー検知時に pynput スレッドから呼ばれるコールバック。"""
        logger.debug("ホットキー検知")
        self.triggered.emit()

    @staticmethod
    def _to_pynput_format(hotkey: str) -> str:
        """'ctrl+shift+q' 形式を pynput の '<ctrl>+<shift>+q' 形式へ変換する。"""
        modifiers = {"ctrl", "shift", "alt", "cmd"}
        parts = [
            f"<{part}>" if part in modifiers else part
            for part in hotkey.lower().split("+")
        ]
        return "+".join(parts)
