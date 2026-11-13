"""アプリケーション全体の設定値を集約するモジュール。

設定値の追加・変更は必ずこのファイルで行う。
他モジュールでのハードコードは禁止。
全てのデータクラスは frozen=True で不変性を保証する。
"""

from dataclasses import dataclass, field
from pathlib import Path

# プロジェクトルート（src/globalstudy/config/settings.py から3階層上）
PROJECT_ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class PathConfig:
    """実行時に生成されるファイル・ディレクトリのパス設定。

    Attributes:
        data_dir: データディレクトリのルート。
        log_dir: ログファイルの出力先。
        capture_dir: キャプチャ画像の保存先。
        db_path: SQLiteデータベースのパス（将来拡張用）。
        region_file: キャプチャ範囲の保存先（起動時に復元）。
    """

    data_dir: Path = PROJECT_ROOT / "data"
    log_dir: Path = PROJECT_ROOT / "data" / "logs"
    capture_dir: Path = PROJECT_ROOT / "data" / "captures"
    db_path: Path = PROJECT_ROOT / "data" / "globalstudy.db"
    region_file: Path = PROJECT_ROOT / "data" / "region.json"


@dataclass(frozen=True)
class LogConfig:
    """ロギング設定。

    Attributes:
        level: ファイル出力のログレベル。
        console_level: コンソール出力のログレベル。
        file_name: ログファイル名。
        max_bytes: ログファイルの最大サイズ（バイト）。超過時にローテーション。
        backup_count: ローテーション時に保持する過去ログファイル数。
        format: ログメッセージのフォーマット文字列。
    """

    level: str = "DEBUG"
    console_level: str = "INFO"
    file_name: str = "globalstudy.log"
    max_bytes: int = 5 * 1024 * 1024
    backup_count: int = 3
    format: str = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


@dataclass(frozen=True)
class CaptureConfig:
    """画面キャプチャ設定。

    Attributes:
        hotkey: グローバルホットキー（pynput形式）。
        image_format: キャプチャ画像の保存形式（png/jpeg）。
        auto_interval_ms: スライド変化監視の間隔（ミリ秒）。
        auto_hash_threshold: スライド変化と判定するdHashのハミング距離閾値。
            64bitハッシュのうち何bit異なれば変化とみなすか（小さいほど敏感）。
    """

    hotkey: str = "ctrl+shift+q"
    image_format: str = "png"
    auto_interval_ms: int = 1500
    auto_hash_threshold: int = 10


@dataclass(frozen=True)
class OcrConfig:
    """OCR 設定。

    Attributes:
        engine: OCRエンジン名（"rapidocr" or "paddleocr"）。
        language: OCRの認識言語。RapidOCR・PaddleOCR両方で使用。
    """

    engine: str = "rapidocr"  # "paddleocr" or "rapidocr"
    language: str = "en"


@dataclass(frozen=True)
class TranslationConfig:
    """翻訳言語設定。

    Attributes:
        source_language: 翻訳元言語（プロンプトに埋め込む表示名）。
        target_language: 翻訳先言語（プロンプトに埋め込む表示名）。
    """

    source_language: str = "english"
    target_language: str = "japanese"


# ソース言語→OCR言語コードのマッピング
_LANGUAGE_TO_OCR_CODE: dict[str, str] = {
    "english": "en",
    "chinese": "ch",
    "japanese": "japan",
    "korean": "korean",
    "french": "french",
    "german": "german",
    "spanish": "es",
}


def source_language_to_ocr_code(source_language: str) -> str:
    """翻訳元言語の表示名からOCR言語コードを取得する。

    未定義の言語場合は "en" を返す（フォールバック）。
    """
    return _LANGUAGE_TO_OCR_CODE.get(source_language.lower(), "en")


@dataclass(frozen=True)
class LlmConfig:
    """LLM（Ollama）設定。

    Attributes:
        base_url: Ollama サーバーのURL。
        model: 使用するLLMモデル名。
        timeout_seconds: リクエストタイムアウト秒数。
        keep_alive: モデルをVRAMに保持する時間。リロード遅延を防ぐ。
        enable_thinking: qwen3系の思考モード有無。応答速度優先のため無効化。
    """

    # "localhost" だと Windows では IPv6 (::1) を先に試し、IPv4 だけで待ち受ける
    # Ollama への接続が拒否されるまで約 2 秒待つ（tools/bench_pipeline.py で計測）。
    # そのため IPv4 のアドレスを直接指定する
    base_url: str = "http://127.0.0.1:11434"
    model: str = "qwen3:8b"
    timeout_seconds: int = 300
    # モデルをVRAMに保持する時間。リロードによる遅延を防ぐ
    keep_alive: str = "60m"
    # qwen3 系の思考モード。応答速度優先のため無効化
    enable_thinking: bool = False


@dataclass(frozen=True)
class VlmConfig:
    """VLM（視覚言語モデル）設定。

    Attributes:
        base_url: Ollama サーバーのURL（LLMと共有）。
        model: 使用するVLMモデル名。
        timeout_seconds: リクエストタイムアウト秒数。
        keep_alive: モデルをVRAMに保持する時間。
    """

    # "localhost" だと Windows では IPv6 (::1) を先に試し、IPv4 だけで待ち受ける
    # Ollama への接続が拒否されるまで約 2 秒待つ（tools/bench_pipeline.py で計測）。
    # そのため IPv4 のアドレスを直接指定する
    base_url: str = "http://127.0.0.1:11434"
    model: str = "minicpm-v:8b"
    timeout_seconds: int = 300
    keep_alive: str = "60m"


@dataclass(frozen=True)
class UiConfig:
    """GUI 設定。

    Attributes:
        window_title: メインウィンドウのタイトル。
        window_width: ウィンドウの初期幅（ピクセル）。
        window_height: ウィンドウの初期高さ（ピクセル）。
    """

    window_title: str = "GlobalStudy"
    window_width: int = 900
    window_height: int = 700


@dataclass(frozen=True)
class Config:
    """全設定への単一アクセスポイント。

    各設定データクラスをフィールドとして集約し、
    アプリケーション全体で単一の Config インスタンスを
    共有して使用する。
    """

    paths: PathConfig = field(default_factory=PathConfig)
    log: LogConfig = field(default_factory=LogConfig)
    capture: CaptureConfig = field(default_factory=CaptureConfig)
    ocr: OcrConfig = field(default_factory=OcrConfig)
    translation: TranslationConfig = field(default_factory=TranslationConfig)
    llm: LlmConfig = field(default_factory=LlmConfig)
    # オーバーレイ翻訳のモデル設定（キャプチャ＆翻訳とは別に変えられる）。
    # 以前は速さ優先で qwen3:1.7b だったが、デモ用スライド 5 枚のうち 1 枚が
    # 中国語で返り、コードまで訳したため 8b にした（1 枚 0.6〜1.0 秒 → 0.9〜1.8 秒、
    # RTX 5070 Ti。2026/11/06）。GPU のメモリが少ない PC では "qwen3:1.7b" に戻す
    overlay_llm: LlmConfig = field(
        default_factory=lambda: LlmConfig(model="qwen3:8b")
    )
    vlm: VlmConfig = field(default_factory=VlmConfig)
    ui: UiConfig = field(default_factory=UiConfig)

    def ensure_directories(self) -> None:
        """実行時に必要なディレクトリを一括作成する。

        data_dir, log_dir, capture_dir が存在しない場合は作成する。
        アプリ起動時に main.py から呼び出される。
        """
        for directory in (
            self.paths.data_dir,
            self.paths.log_dir,
            self.paths.capture_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)
