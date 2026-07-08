"""AI 解析結果（構造化済み）のデータモデル。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class AiAnalysis:
    """LLM 応答をセクション別に構造化した結果。

    Attributes:
        translation: 自然な日本語訳。
        key_points: 重要ポイントの箇条書き。
        terms: 専門用語の解説。
        beginner_explanation: 初心者向けの説明。
        background: この内容を理解するための背景知識。
        related_concepts: 関連する概念やトピック。
        raw: パース前の応答全文（フォールバック表示・デバッグ用）。
    """

    translation: str
    key_points: str
    terms: str
    beginner_explanation: str
    background: str
    related_concepts: str
    raw: str
