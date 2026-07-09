"""LLM プロンプトの組立て。

プロンプト改善（Phase 7）はこのモジュールのみを変更する。
"""

_TRANSLATION_PROMPT_TEMPLATE = """\
あなたはあらゆる分野に精通した優秀な翻訳者です。
英語の動画を視聴している日本人学習者を支援します。

以下はスクリーンキャプチャからOCRで抽出した英文です。
まず本文の分野（例: AI、プログラミング、哲学、生物学、歴史、経済など）を自分で判断し、
その分野の専門家として自然な日本語に翻訳してください。

注意事項:
- OCR由来の誤字・脱字・行の分断は文脈から補正して解釈すること
- 直訳ではなく、その分野で通用する自然な日本語にすること
- 分野特有の定訳・慣用表現がある場合はそれを使うこと（例: attention → アテンション、
  categorical imperative → 定言命法、natural selection → 自然選択）
- 推測で内容を追加しないこと。本文にある情報のみを扱うこと
- 出力は日本語訳のみ。見出しや解説は一切付けないこと

英文:
{text}
"""


def build_translation_prompt(english_text: str) -> str:
    """OCR で抽出した英文から翻訳用プロンプトを組み立てる。"""
    return _TRANSLATION_PROMPT_TEMPLATE.format(text=english_text)


def build_analysis_prompt(english_text: str) -> str:
    """OCR で抽出した英文から解析用プロンプトを組み立てる。（旧仕様・互換用）"""
    return _TRANSLATION_PROMPT_TEMPLATE.format(text=english_text)
