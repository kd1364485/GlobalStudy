"""アプリケーションのエントリポイント。起動処理のみを担当する。"""

import sys

from PySide6.QtWidgets import QApplication

from globalstudy import __version__
from globalstudy.config import Config
from globalstudy.services.ai_service import AiService
from globalstudy.services.analysis_service import AnalysisService
from globalstudy.services.capture_service import CaptureService
from globalstudy.services.ocr_service import OcrService
from globalstudy.ui.main_window import MainWindow
from globalstudy.ui.styles import APP_STYLESHEET
from globalstudy.utils.logger import get_logger, setup_logging


def main() -> None:
    config = Config()
    setup_logging(config)
    logger = get_logger(__name__)
    logger.info("GlobalStudy v%s 起動", __version__)

    app = QApplication(sys.argv)
    app.setStyleSheet(APP_STYLESHEET)

    capture_service = CaptureService(config)
    ai_service = AiService(config)
    analysis_service = AnalysisService(
        capture_service=capture_service,
        ocr_service=OcrService(),
        ai_service=ai_service,
    )
    if not ai_service.is_available():
        logger.warning("Ollama へ接続できません。解析実行前に起動してください。")

    window = MainWindow(config, capture_service, analysis_service)
    window.show()

    exit_code = app.exec()
    logger.info("GlobalStudy 終了 (code=%d)", exit_code)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
