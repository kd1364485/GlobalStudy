"""アプリケーション全体の設定値を集約するモジュール。

設定値の追加・変更は必ずこのファイルで行う。
他モジュールでのハードコードは禁止。
"""

from dataclasses import dataclass, field
from pathlib import Path

# プロジェクトルート（src/globalstudy/config/settings.py から3階層上）
PROJECT_ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class PathConfig:
    """実行時に生成されるファイル・ディレクトリのパス設定。"""

    data_dir: Path = PROJECT_ROOT / "data"
    log_dir: Path = PROJECT_ROOT / "data" / "logs"
    capture_dir: Path = PROJECT_ROOT / "data" / "captures"
    db_path: Path = PROJECT_ROOT / "data" / "globalstudy.db"


@dataclass(frozen=True)
class LogConfig:
    """ロギング設定。"""

    level: str = "DEBUG"
    console_level: str = "INFO"
    file_name: str = "globalstudy.log"
    max_bytes: int = 5 * 1024 * 1024
    backup_count: int = 3
    format: str = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


@dataclass(frozen=True)
class CaptureConfig:
    """画面キャプチャ設定（Phase 2 で使用）。"""

    hotkey: str = "ctrl+shift+q"
    image_format: str = "png"


@dataclass(frozen=True)
class OcrConfig:
    """OCR 設定（Phase 3 で使用）。"""

    engine: str = "paddleocr"  # "paddleocr" or "rapidocr"
    language: str = "en"


@dataclass(frozen=True)
class LlmConfig:
    """LLM（Ollama）設定（Phase 4 で使用）。"""

    base_url: str = "http://localhost:11434"
    model: str = "qwen3:8b"
    timeout_seconds: int = 300
    # qwen3 系の思考モード。応答速度優先のため無効化
    enable_thinking: bool = False


@dataclass(frozen=True)
class UiConfig:
    """GUI 設定（Phase 1 で使用）。"""

    window_title: str = "GlobalStudy"
    window_width: int = 900
    window_height: int = 700


@dataclass(frozen=True)
class Config:
    """全設定への単一アクセスポイント。"""

    paths: PathConfig = field(default_factory=PathConfig)
    log: LogConfig = field(default_factory=LogConfig)
    capture: CaptureConfig = field(default_factory=CaptureConfig)
    ocr: OcrConfig = field(default_factory=OcrConfig)
    llm: LlmConfig = field(default_factory=LlmConfig)
    ui: UiConfig = field(default_factory=UiConfig)

    def ensure_directories(self) -> None:
        """実行時に必要なディレクトリを作成する。"""
        for directory in (
            self.paths.data_dir,
            self.paths.log_dir,
            self.paths.capture_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)
