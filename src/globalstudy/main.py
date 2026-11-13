"""アプリケーションのエントリポイント。

Config初期化→ロギング設定→サービス生成→MainWindow表示→
Ollama接続確認の順で起動する。起動処理のみを担当し、
ビジネスロジックは含まない。
"""

import sys

from PySide6.QtWidgets import QApplication

from globalstudy import __version__
from globalstudy.ai.ollama_client import OllamaClient
from globalstudy.config import Config
from globalstudy.services.ai_service import AiService
from globalstudy.services.analysis_service import AnalysisService
from globalstudy.services.capture_service import CaptureService
from globalstudy.services.ocr_service import OcrService
from globalstudy.services.overlay_translation_service import (
    OverlayTranslationService,
)
from globalstudy.services.vlm_analysis_service import VlmAnalysisService
from globalstudy.services.visual_analysis_service import VisualAnalysisService
from globalstudy.ui.main_window import MainWindow
from globalstudy.ui.styles import APP_STYLESHEET
from globalstudy.utils.logger import get_logger, setup_logging


def main() -> None:
    """アプリケーションを起動し、Qtイベントループに入る。"""
    # 設定初期化とロギング設定
    config = Config()
    setup_logging(config)
    logger = get_logger(__name__)
    logger.info("GlobalStudy v%s 起動", __version__)

    # Qtアプリケーション生成とスタイル適用
    app = QApplication(sys.argv)
    app.setStyleSheet(APP_STYLESHEET)

    # サービス層の生成（依存関係を注入）
    capture_service = CaptureService(config)
    ai_service = AiService(config)
    ocr_service = OcrService(config)
    visual_analysis_service = VisualAnalysisService()
    vlm_analysis_service = VlmAnalysisService(config)
    analysis_service = AnalysisService(
        capture_service=capture_service,
        ocr_service=ocr_service,
        ai_service=ai_service,
        visual_analysis_service=visual_analysis_service,
    )
    # オーバーレイ翻訳（元のテキストの上に訳文を重ねて表示）。
    # モデルは config.overlay_llm で、キャプチャ＆翻訳とは別に変えられる
    overlay_ai_service = AiService(
        config, client=OllamaClient(config, llm_config=config.overlay_llm)
    )
    overlay_service = OverlayTranslationService(
        capture_service=capture_service,
        ocr_service=ocr_service,
        ai_service=overlay_ai_service,
    )
    # OllamaサーバーとVLMモデルの可用性を確認（起動時の早期警告）
    if not ai_service.is_available():
        logger.warning("Ollama へ接続できません。解析実行前に起動してください。")
    if not vlm_analysis_service.is_available():
        logger.warning(
            "VLMモデル %s が利用できません。VLM解析前に ollama pull してください。",
            config.vlm.model,
        )
    if not overlay_ai_service.is_available():
        logger.warning(
            "オーバーレイ翻訳用モデル %s が利用できません。"
            "使用前に ollama pull してください。",
            config.overlay_llm.model,
        )

    window = MainWindow(
        config,
        capture_service,
        analysis_service,
        vlm_analysis_service=vlm_analysis_service,
        overlay_service=overlay_service,
        ocr_service=ocr_service,
    )
    window.show()

    exit_code = app.exec()
    logger.info("GlobalStudy 終了 (code=%d)", exit_code)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
