"""ロガー生成モジュール。

コンソール出力とローテーション付きファイル出力を提供する。
各モジュールは get_logger(__name__) でロガーを取得する。
"""

import logging
from logging.handlers import RotatingFileHandler

from globalstudy.config.settings import Config

_ROOT_LOGGER_NAME = "globalstudy"
_initialized = False


def setup_logging(config: Config) -> None:
    """ルートロガーを初期化する。アプリ起動時に一度だけ呼ぶ。

    コンソール出力（INFO以上）とローテーション付きファイル出力（DEBUG以上）
    の2つのハンドラを設定する。二重初期化は _initialized フラグで防止する。
    """
    global _initialized
    if _initialized:
        return

    config.ensure_directories()

    root = logging.getLogger(_ROOT_LOGGER_NAME)
    root.setLevel(config.log.level)
    formatter = logging.Formatter(config.log.format)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(config.log.console_level)
    console_handler.setFormatter(formatter)
    root.addHandler(console_handler)

    file_handler = RotatingFileHandler(
        config.paths.log_dir / config.log.file_name,
        maxBytes=config.log.max_bytes,
        backupCount=config.log.backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(config.log.level)
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    _initialized = True


def get_logger(name: str) -> logging.Logger:
    """モジュール用ロガーを取得する。

    全てのロガーは "globalstudy" ルートロガー配下にぶら下がる。
    これにより setup_logging() で設定したハンドラが全モジュールに適用される。

    Args:
        name: 通常は __name__ を渡す。

    Returns:
        "globalstudy" 配下の Logger インスタンス。
    """
    if name.startswith(_ROOT_LOGGER_NAME):
        return logging.getLogger(name)
    return logging.getLogger(f"{_ROOT_LOGGER_NAME}.{name}")
