"""バックグラウンドワーカーの共通基底クラス。

AnalysisWorker と VlmWorker の共通処理（_safe_emit）を抽出する。
QRunnable を継承し、QThreadPool 上で実行される。
"""

from PySide6.QtCore import QObject, QRunnable, Signal

from globalstudy.utils.logger import get_logger

logger = get_logger(__name__)


class BaseWorkerSignals(QObject):
    """ワーカー共通の通知シグナル。

    全ワーカーで共通して使用する失敗シグナルのみ定義。
    各ワーカー専用のシグナルはサブクラス側で別途定義する。
    """

    failed = Signal(str)


class BaseWorker(QRunnable):
    """QRunnable の共通基底。_safe_emit を提供する。

    Qtシグナル送信時、受信側QWidgetが既に削除されていると
    RuntimeError が発生する。これを安全に回避するための
    ヘルパーメソッドを提供する。
    """

    def __init__(self) -> None:
        super().__init__()
        # ワーカー完了後もインスタンスを保持するため自動削除を無効化
        self.setAutoDelete(False)

    @staticmethod
    def _safe_emit(signal, *args) -> None:
        """シグナル送信時に受信側 QObject が削除されている場合の RuntimeError を回避する。"""
        try:
            signal.emit(*args)
        except RuntimeError:
            logger.warning("シグナル送信先が削除済みのため送信をスキップしました")
