"""アプリ全体の QSS スタイル定義。"""

APP_STYLESHEET = """
QMainWindow {
    background-color: #1e1e2e;
}
QLabel {
    color: #cdd6f4;
    font-size: 13px;
    font-weight: bold;
    padding: 2px;
}
QPushButton {
    background-color: #89b4fa;
    color: #1e1e2e;
    font-size: 13px;
    font-weight: bold;
    border: none;
    border-radius: 6px;
    padding: 8px 20px;
}
QPushButton:hover {
    background-color: #b4befe;
}
QPushButton:disabled {
    background-color: #45475a;
    color: #7f849c;
}
QTextEdit {
    background-color: #181825;
    color: #cdd6f4;
    font-size: 14px;
    border: 1px solid #313244;
    border-radius: 6px;
    padding: 8px;
}
QTabWidget::pane {
    border: 1px solid #313244;
    border-radius: 6px;
    background-color: #181825;
}
QTabBar::tab {
    background-color: #313244;
    color: #cdd6f4;
    font-size: 13px;
    padding: 8px 24px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 2px;
}
QTabBar::tab:selected {
    background-color: #89b4fa;
    color: #1e1e2e;
    font-weight: bold;
}
QStatusBar {
    background-color: #11111b;
    color: #a6adc8;
    font-size: 12px;
}
QSplitter::handle {
    background-color: #313244;
}
"""
