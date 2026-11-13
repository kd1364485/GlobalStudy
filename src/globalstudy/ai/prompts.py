"""LLM プロンプトの組立て。

プロンプト改善はこのモジュールのみを変更する。
翻訳用プロンプトとVLM解析用プロンプトの2種類を定義する。
"""

# --- 翻訳用プロンプト ---
# OCRで抽出した英文を自然な日本語に翻訳するためのテンプレート。
# {text} 部分にOCRテキストが埋め込まれる。
# 分野の自動判定・OCR誤字補正・定訳使用を指示している。
_TRANSLATION_PROMPT_TEMPLATE = """\
あなたはあらゆる分野に精通した優秀な翻訳者です。
{source_language}の動画を視聴している{target_language}話者の学習者を支援します。

以下はスクリーンキャプチャからOCRで抽出した{source_language}のテキストです。
まず本文の分野（例: AI、プログラミング、哲学、生物学、歴史、経済など）を自分で判断し、
その分野の専門家として自然な{target_language}に翻訳してください。

注意事項:
- OCR由来の誤字・脱字・行の分断は文脈から補正して解釈すること
- 直訳ではなく、その分野で通用する自然な{target_language}にすること
- 分野特有の定訳・慣用表現がある場合はそれを使うこと（例: attention → アテンション、
  categorical imperative → 定言命法、natural selection → 自然選択）
- 推測で内容を追加しないこと。本文にある情報のみを扱うこと
- 出力は{target_language}の訳文のみ。見出しや解説は一切付けないこと

原文:
{text}
"""


def build_translation_prompt(
    text: str, source_language: str = "english", target_language: str = "japanese"
) -> str:
    """OCR で抽出したテキストから翻訳用プロンプトを組み立てる。

    Args:
        text: OCRで抽出したテキスト。
        source_language: 翻訳元言語の表示名。
        target_language: 翻訳先言語の表示名。

    Returns:
        テンプレートにテキストと言語が埋め込まれた完成プロンプト。
    """
    return _TRANSLATION_PROMPT_TEMPLATE.format(
        text=text, source_language=source_language, target_language=target_language
    )


# --- VLM解析用プロンプト ---
# VLM（視覚言語モデル）に画像を送信する際のプロンプト。
# OCR翻訳では分からない視覚情報（図・グラフ・イラスト）の
# 補足説明を求める。簡潔さと重複回避を明示的に指示している。
_VLM_ANALYSIS_PROMPT_TEMPLATE = """\
この画像は{source_language}の技術講義スライドです。
OCR翻訳では分からない視覚情報を中心に、{target_language}で簡潔に説明してください。

出力内容（各項目2〜3文程度で簡潔に）:
1. スライド全体の目的
2. 図・グラフ・イラストの意味
3. 強調されている箇所
4. OCR翻訳だけでは補えない補足
5. 学習者が理解すべきポイント

禁止:
- 画像内にない内容を断定しない
- OCRで読めない細かい文字を無理に推測しない
- 長すぎる説明にしない
- 同じ内容を繰り返さない。一度述べたことは再度言及しない
- 項目間で内容が重複しないよう、各項目で異なる観点を述べる
"""


def build_vlm_prompt(
    source_language: str = "english", target_language: str = "japanese"
) -> str:
    """VLM 解析用プロンプトを組み立てる。

    Args:
        source_language: 翻訳元言語の表示名。
        target_language: 翻訳先言語の表示名。

    Returns:
        VLMへ送信する解析指示プロンプト。
    """
    return _VLM_ANALYSIS_PROMPT_TEMPLATE.format(
        source_language=source_language, target_language=target_language
    )


# --- オーバーレイ翻訳用（行単位バッチ翻訳）プロンプト ---
# 画面オーバーレイで元テキストの位置に翻訳を重ねるため、
# 行との1対1対応を保ったまま翻訳する必要がある。
# 番号付きで送信し、同じ番号付きで返すよう厳密に指示する。
_LINE_TRANSLATION_PROMPT_TEMPLATE = """\
あなたは優秀な翻訳者です。
以下は講義スライドからOCRで抽出した{source_language}のテキストの各行です。
各行を自然な{target_language}に翻訳してください。

厳守するルール:
- 各行は「番号: テキスト」形式である。必ず同じ番号を付けて「番号: {target_language}訳」形式で出力すること
- 行の統合・分割・並べ替えは禁止。入力と同じ行数で出力すること
- 行単位で意味が不完全でも、その行の内容だけを翻訳すること
- 固有名詞・数式・コード・記号はそのまま残すこと
- 出力は翻訳行のみ。解説や見出しは一切付けないこと

原文:
{lines}
"""


def build_line_translation_prompt(
    lines: list[str],
    source_language: str = "english",
    target_language: str = "japanese",
) -> str:
    """行単位バッチ翻訳用プロンプトを組み立てる。

    オーバーレイ翻訳で行と訳文の対応を保つため、
    各行に番号を付けて送信する。

    Args:
        lines: OCRで抽出したテキストの行リスト。
        source_language: 翻訳元言語の表示名。
        target_language: 翻訳先言語の表示名。

    Returns:
        番号付き行が埋め込まれた完成プロンプト。
    """
    numbered = "\n".join(f"{i + 1}: {line}" for i, line in enumerate(lines))
    return _LINE_TRANSLATION_PROMPT_TEMPLATE.format(
        lines=numbered, source_language=source_language, target_language=target_language
    )
