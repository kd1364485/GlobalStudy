# GlobalStudy アーキテクチャ

最終更新: Phase 7 完了時点

## モジュール依存図

```mermaid
graph TD
    main[main.py] --> config[config]
    main --> utils[utils/logger]
    main --> ui[ui]
    main --> services[services]
    ui --> config
    ui --> utils
    ui --> services
    ui --> models[models]
    ui --> hotkey[capture/HotkeyListener]
    services --> capture[capture/ScreenCapturer]
    services --> models
    capture --> models
    utils --> config

    services --> ocr[ocr]
    ocr --> models
    services --> ai[ai]
    ai --> config

    subgraph 未実装["Phase 8 以降で実装"]
        services --> storage[storage]
        storage --> models
    end
```

依存ルール:

- `ui` は `services` のみを呼ぶ（capture/ocr/ai を直接呼ばない）
- `config` と `utils` は全レイヤーから利用可
- `models` はどのレイヤーにも依存しない

## 処理フロー（解析パイプライン）

```mermaid
sequenceDiagram
    participant U as ユーザー
    participant MW as MainWindow
    participant W as AnalysisWorker(別スレッド)
    participant AS as AnalysisService
    participant CS as CaptureService
    participant OS as OcrService
    participant AI as AiService

    U->>MW: 解析ボタン / Ctrl+Shift+Q
    MW->>W: QThreadPool.start
    W->>AS: analyze_screen()
    AS->>CS: capture()
    CS-->>AS: 画像パス
    AS->>OS: extract_text()
    OS-->>AS: OcrResult(英文)
    AS->>AI: ask(プロンプト)
    AI-->>AS: 日本語解説
    AS-->>W: AnalysisResult
    W-->>MW: finished シグナル
    MW->>U: 英文 + 日本語を表示
```

## クラス図（Phase 7 時点）

```mermaid
classDiagram
    class Config {
        +paths: PathConfig
        +log: LogConfig
        +capture: CaptureConfig
        +ocr: OcrConfig
        +llm: LlmConfig
        +ui: UiConfig
        +ensure_directories() None
    }

    class PathConfig {
        +data_dir: Path
        +log_dir: Path
        +capture_dir: Path
        +db_path: Path
    }

    class LogConfig {
        +level: str
        +console_level: str
        +file_name: str
        +max_bytes: int
        +backup_count: int
        +format: str
    }

    class logger {
        <<module>>
        +setup_logging(config) None
        +get_logger(name) Logger
    }

    class MainWindow {
        -_config: Config
        -_capture_service: CaptureService
        -_hotkey_listener: HotkeyListener
        -_on_select_region() None
        -_on_region_selected(region) None
        -_on_analyze() None
    }

    class CaptureRegion {
        +left: int
        +top: int
        +width: int
        +height: int
        +is_valid() bool
    }

    class ScreenCapturer {
        -_config: Config
        +capture(region) Path
    }

    class HotkeyListener {
        +triggered: Signal
        +start() None
        +stop() None
    }

    class CaptureService {
        -_capturer: ScreenCapturer
        -_region: CaptureRegion
        +set_region(region) None
        +has_region() bool
        +capture() Path
    }

    class RegionSelectorOverlay {
        +region_selected: Signal~CaptureRegion~
        +selection_cancelled: Signal
    }

    class OcrResult {
        +text: str
        +confidence: float
        +is_empty() bool
    }

    class OcrEngine {
        <<abstract>>
        +recognize(image_path) OcrResult
    }

    class RapidOcrEngine {
        -_engine: RapidOCR
        +recognize(image_path) OcrResult
    }

    class OcrService {
        -_engine: OcrEngine
        +extract_text(image_path) OcrResult
    }

    class LlmClient {
        <<abstract>>
        +is_available() bool
        +generate(prompt) str
    }

    class OllamaClient {
        -_config: LlmConfig
        +is_available() bool
        +generate(prompt) str
    }

    class AiService {
        -_client: LlmClient
        +is_available() bool
        +ask(prompt) str
    }

    class AiAnalysis {
        +translation: str
        +key_points: str
        +terms: str
        +beginner_explanation: str
        +raw: str
    }

    class AnalysisResult {
        +image_path: Path
        +ocr: OcrResult
        +analysis: AiAnalysis
    }

    class response_parser {
        <<module>>
        +parse_analysis_response(response) AiAnalysis
    }

    class AnalysisService {
        -_capture: CaptureService
        -_ocr: OcrService
        -_ai: AiService
        +analyze_screen() AnalysisResult
    }

    class AnalysisWorker {
        +signals: AnalysisWorkerSignals
        +run() None
    }

    QMainWindow <|-- MainWindow
    MainWindow ..> Config : 使用
    MainWindow --> CaptureService
    MainWindow --> HotkeyListener
    MainWindow ..> RegionSelectorOverlay : 生成
    CaptureService --> ScreenCapturer
    CaptureService --> CaptureRegion
    ScreenCapturer ..> CaptureRegion
    RegionSelectorOverlay ..> CaptureRegion : 発行
    OcrEngine <|-- RapidOcrEngine
    OcrService --> OcrEngine
    OcrEngine ..> OcrResult : 返却
    LlmClient <|-- OllamaClient
    AiService --> LlmClient
    OllamaClient ..> Config : 使用
    AnalysisService --> CaptureService
    AnalysisService --> OcrService
    AnalysisService --> AiService
    AnalysisService ..> AnalysisResult : 返却
    AnalysisService ..> response_parser : 使用
    response_parser ..> AiAnalysis : 返却
    AnalysisResult *-- AiAnalysis
    MainWindow ..> AnalysisWorker : 生成
    AnalysisWorker --> AnalysisService
    Config *-- PathConfig
    Config *-- LogConfig
    Config *-- CaptureConfig
    Config *-- OcrConfig
    Config *-- LlmConfig
    Config *-- UiConfig
    logger ..> Config : 使用
```

## フェーズ履歴

| Phase | 内容 | 状態 |
| --- | --- | --- |
| 0 | 環境構築（Config / Logger / 骨格） | 完了 |
| 1 | GUI 骨格 | 完了 |
| 2 | 画面キャプチャ | 完了 |
| 3 | OCR（RapidOCR 採用） | 完了 |
| 4 | LLM 接続（Ollama / qwen3:8b） | 完了 |
| 5 | OCR→LLM 統合（一連フロー完成） | 完了 |
| 6 | GUI 改善（タブ表示・テーマ適用） | 完了 |
| 7 | AI 品質改善（分野非依存プロンプト・4セクション） | 完了 |
