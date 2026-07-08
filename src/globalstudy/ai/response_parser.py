"""LLM 応答のセクションパーサー。

【見出し】形式の応答を AiAnalysis へ変換する。
形式が崩れていた場合は全文を translation へ入れるフォールバックを行う。
"""

import re

from globalstudy.models.ai_analysis import AiAnalysis
from globalstudy.utils.logger import get_logger

logger = get_logger(__name__)

_SECTION_PATTERN = re.compile(r"【(?P<name>[^】]+)】\s*(?P<body>.*?)(?=【[^】]+】|\Z)", re.DOTALL)

_TRANSLATION_KEYS = ("日本語訳", "翻訳")
_KEY_POINTS_KEYS = ("重要ポイント", "要点", "ポイント")
_TERMS_KEYS = ("専門用語", "用語")
_BEGINNER_KEYS = ("初心者", "解説", "説明")
_BACKGROUND_KEYS = ("背景", "前提")
_RELATED_KEYS = ("関連",)


def parse_analysis_response(response: str) -> AiAnalysis:
    """LLM 応答をセクション別に分解する。"""
    sections = {
        match.group("name").strip(): match.group("body").strip()
        for match in _SECTION_PATTERN.finditer(response)
    }

    if not sections:
        logger.warning("応答にセクション見出しが見つかりません。全文を訳として扱います")
        return AiAnalysis(
            translation=response.strip(),
            key_points="",
            terms="",
            beginner_explanation="",
            background="",
            related_concepts="",
            raw=response,
        )

    return AiAnalysis(
        translation=_find_section(sections, _TRANSLATION_KEYS),
        key_points=_find_section(sections, _KEY_POINTS_KEYS),
        terms=_find_section(sections, _TERMS_KEYS),
        beginner_explanation=_find_section(sections, _BEGINNER_KEYS),
        background=_find_section(sections, _BACKGROUND_KEYS),
        related_concepts=_find_section(sections, _RELATED_KEYS),
        raw=response,
    )


def _find_section(sections: dict[str, str], keys: tuple[str, ...]) -> str:
    """見出し名の候補リストからセクション本文を取得する（部分一致）。"""
    for name, body in sections.items():
        if any(key in name for key in keys):
            return body
    return ""
