"""プロンプト品質の手動検証スクリプト（Ollama 起動が必要）。

実行: .venv\\Scripts\\python.exe -X utf8 tests\\manual_prompt_check.py
"""

from globalstudy.ai.prompts import build_analysis_prompt
from globalstudy.ai.response_parser import parse_analysis_response
from globalstudy.config import Config
from globalstudy.services.ai_service import AiService
from globalstudy.utils.logger import setup_logging

SAMPLES = {
    "AI": (
        "The attention mechanism allows the model to focus on relevant parts "
        "of the input sequence when generating each output token."
    ),
    "哲学": (
        "Kant argues that the categorical imperative requires us to act only "
        "according to maxims that could become universal laws."
    ),
    "生物学": (
        "Mitochondria generate ATP through oxidative phosphorylation, "
        "a process driven by the electron transport chain."
    ),
}


def main() -> None:
    config = Config()
    setup_logging(config)
    service = AiService(config)

    for domain, text in SAMPLES.items():
        print(f"\n{'=' * 60}\n[{domain}] {text}\n{'-' * 60}")
        response = service.ask(build_analysis_prompt(text))
        analysis = parse_analysis_response(response)
        print(f"【日本語訳】\n{analysis.translation}\n")
        print(f"【重要ポイント】\n{analysis.key_points}\n")
        print(f"【専門用語】\n{analysis.terms}\n")
        print(f"【初心者向け説明】\n{analysis.beginner_explanation}")


if __name__ == "__main__":
    main()
