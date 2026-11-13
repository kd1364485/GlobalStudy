"""オーバーレイ翻訳ユースケース。

キャプチャ → OCR（座標付き） → 行バッチ翻訳（ストリーミング） →
翻訳パッチ生成のパイプラインを提供する。生成されたパッチは
OverlayWindow が元の映像の上に重ねて描画する。
"""

import re
from collections.abc import Iterator
from pathlib import Path

import cv2
import numpy as np

from globalstudy.ai.prompts import build_line_translation_prompt
from globalstudy.models.ocr_result import OcrLine
from globalstudy.models.overlay import OverlayPatch
from globalstudy.models.region import CaptureRegion
from globalstudy.services.ai_service import AiService
from globalstudy.services.capture_service import CaptureService
from globalstudy.services.ocr_service import OcrService
from globalstudy.utils.logger import get_logger

logger = get_logger(__name__)

# 「番号: 訳文」形式の応答行をパースする正規表現
_NUMBERED_LINE_RE = re.compile(r"^\s*(\d+)\s*[:：]\s*(.*)$")

# 翻訳対象と判定する条件: 2文字以上のUnicode文字を含むこと
# （数字・記号・単一文字のみの行は翻訳不要）
# \W は非単語文字、\d は数字、_ はアンダースコアを除外し、
# 残りは任意のUnicode文字（Latin・CJK・Korean・Arabic等すべて対応）
_TRANSLATABLE_RE = re.compile(r"[^\W\d_]{2,}", re.UNICODE)

# URL・ファイルパスなど翻訳すべきでない行の先頭パターン
_SKIP_PREFIX_RE = re.compile(r"^\s*(https?://|www\.|file://)", re.IGNORECASE)


class OverlayTranslationError(Exception):
    """オーバーレイ翻訳パイプラインで発生するエラー。"""


class OverlayTranslationService:
    """画面上のテキストを日本語パッチに変換するサービス。

    キャプチャ画像から OCR で行ごとの座標を取得し、
    LLM で行単位のバッチ翻訳を行い、元テキストの位置に
    重ねるための OverlayPatch のリストを生成する。
    """

    def __init__(
        self,
        capture_service: CaptureService,
        ocr_service: OcrService,
        ai_service: AiService,
    ) -> None:
        self._capture_service = capture_service
        self._ocr_service = ocr_service
        self._ai_service = ai_service
        # 翻訳キャッシュ（原文 → 訳文）。同じ行の再翻訳をスキップし、
        # スライドの再訪・共通ヘッダーなどを高速化する
        self._cache: dict[str, str] = {}

    def clear_cache(self) -> None:
        """翻訳キャッシュをクリアする（言語切り替え時に呼び出される）。"""
        self._cache.clear()
        logger.info("オーバーレイ翻訳キャッシュをクリアしました")

    def prepare_and_stream(
        self, source_language: str = "english", target_language: str = "japanese"
    ) -> tuple[CaptureRegion, Path, Iterator[OverlayPatch]]:
        """キャプチャ → OCR → ストリーミング翻訳のパイプラインを準備する。

        LLM応答をストリーミングで受信し、翻訳が確定した行から順に
        OverlayPatch を yield する。これにより最初のパッチが表示される
        までの時間を短縮できる。

        Args:
            source_language: 翻訳元言語の表示名。
            target_language: 翻訳先言語の表示名。

        Returns:
            (region, image_path, generator) のタプル。
            generator は OverlayPatch を1つずつ yield する。
            キャッシュ済みの行のパッチが先に yield される。

        Raises:
            OverlayTranslationError: テキスト未検出・座標情報なし・範囲未設定の場合。
            CaptureError: キャプチャに失敗した場合。
            OcrError: OCR に失敗した場合。
        """
        image_path = self._capture_service.capture()
        ocr_result = self._ocr_service.extract_text(image_path)

        if ocr_result.is_empty():
            raise OverlayTranslationError("テキストが検出されませんでした")
        if not ocr_result.lines:
            raise OverlayTranslationError(
                "OCRエンジンが座標情報を返しませんでした"
            )

        region = self._capture_service.region
        if region is None:
            raise OverlayTranslationError("キャプチャ範囲が未設定です")

        ocr_lines = ocr_result.lines
        to_translate = self._collect_untranslated(ocr_lines)

        # 背景色を事前計算（ストリーミング中にパッチを即座に生成できるよう）
        image = cv2.imread(str(image_path))
        bg_colors: dict[str, tuple[int, int, int]] = {
            line.text.strip(): self._sample_background(image, line)
            for line in ocr_lines
        }

        def patch_generator() -> Iterator[OverlayPatch]:
            # 1. キャッシュ済みの行のパッチを先に yield
            for line in ocr_lines:
                key = line.text.strip()
                translated = self._cache.get(key, "")
                if translated:
                    yield self._build_patch(line, translated, bg_colors)

            # 2. 未キャッシュ行がなければ終了
            if not to_translate:
                logger.info("全行がキャッシュ済みまたは翻訳不要のため LLM 呼び出しをスキップ")
                return

            # 3. ストリーミング翻訳: 行が確定するたびにパッチを yield
            prompt = build_line_translation_prompt(
                to_translate, source_language=source_language, target_language=target_language
            )
            accumulated = ""
            translated_keys: set[str] = set()

            for chunk in self._ai_service.ask_stream(prompt):
                accumulated += chunk
                # 完全な行（改行で区切られた）があれば処理
                while "\n" in accumulated:
                    line_str, accumulated = accumulated.split("\n", 1)
                    yield from self._emit_stream_patches(
                        line_str, to_translate, ocr_lines,
                        bg_colors, translated_keys,
                    )

            # 残りのバッファを処理
            if accumulated.strip():
                yield from self._emit_stream_patches(
                    accumulated, to_translate, ocr_lines,
                    bg_colors, translated_keys,
                )

            logger.info(
                "ストリーミング翻訳完了: 新規翻訳 %d/%d 行",
                len(translated_keys),
                len(to_translate),
            )

        return region, image_path, patch_generator()

    def _collect_untranslated(self, ocr_lines: list[OcrLine]) -> list[str]:
        """キャッシュ未登録かつ翻訳が必要な行を重複なしで抽出する。"""
        to_translate: list[str] = []
        for line in ocr_lines:
            key = line.text.strip()
            if key in self._cache:
                continue
            if not self._should_translate(key):
                continue
            if key not in to_translate:
                to_translate.append(key)
        return to_translate

    def _build_patch(
        self,
        line: OcrLine,
        translated: str,
        bg_colors: dict[str, tuple[int, int, int]],
    ) -> OverlayPatch:
        """OCR行と訳文から描画用の OverlayPatch を生成する。"""
        bg_rgb = bg_colors.get(line.text.strip(), (255, 255, 255))
        return OverlayPatch(
            left=line.left,
            top=line.top,
            width=line.width,
            height=line.height,
            text=translated,
            bg_rgb=bg_rgb,
            fg_rgb=self._contrast_color(bg_rgb),
        )

    def _emit_stream_patches(
        self,
        line_str: str,
        to_translate: list[str],
        ocr_lines: list[OcrLine],
        bg_colors: dict[str, tuple[int, int, int]],
        translated_keys: set[str],
    ) -> Iterator[OverlayPatch]:
        """ストリーミング応答の1行をパースし、対応する全パッチを yield する。

        "番号: 訳文" 形式の行をパースしてキャッシュに保存し、
        同じ原文を持つ全OCR行のパッチを生成する。
        パース不能・範囲外・処理済みの行は何も yield しない。
        """
        match = _NUMBERED_LINE_RE.match(line_str)
        if match is None:
            return
        index = int(match.group(1)) - 1
        if not (0 <= index < len(to_translate)):
            return
        source = to_translate[index]
        if source in translated_keys:
            return
        translated = match.group(2).strip()
        if not translated:
            return

        self._cache[source] = translated
        translated_keys.add(source)

        # 同じ原文を持つ全てのOCR行にパッチを生成
        for ocr_line in ocr_lines:
            if ocr_line.text.strip() == source:
                yield self._build_patch(ocr_line, translated, bg_colors)

    @staticmethod
    def _should_translate(text: str) -> bool:
        """翻訳すべき行かを判定する。

        数字・記号のみの行や URL は翻訳不要としてスキップし、
        LLM への送信量を減らす（原文がそのまま見える）。
        """
        if not text:
            return False
        if _SKIP_PREFIX_RE.match(text):
            return False
        return _TRANSLATABLE_RE.search(text) is not None

    @staticmethod
    def _sample_background(
        image: np.ndarray | None, line: OcrLine
    ) -> tuple[int, int, int]:
        """テキストボックス周辺の背景色をサンプリングする。

        ボックスを少し外側に膨らませた輪郭上のピクセルの中央値を
        背景色とする（テキスト自身の色の影響を避けるため）。
        画像が読めない場合は白を返す。
        """
        if image is None:
            return (255, 255, 255)

        img_h, img_w = image.shape[:2]
        margin = 4
        left = max(line.left - margin, 0)
        top = max(line.top - margin, 0)
        right = min(line.left + line.width + margin, img_w)
        bottom = min(line.top + line.height + margin, img_h)
        if right <= left or bottom <= top:
            return (255, 255, 255)

        # 膨らませた矩形の外周1px分のピクセルを集める
        edge_pixels = np.concatenate(
            [
                image[top, left:right].reshape(-1, 3),
                image[bottom - 1, left:right].reshape(-1, 3),
                image[top:bottom, left].reshape(-1, 3),
                image[top:bottom, right - 1].reshape(-1, 3),
            ]
        )
        # BGR → RGB に変換して中央値を返す
        median_bgr = np.median(edge_pixels, axis=0)
        return (int(median_bgr[2]), int(median_bgr[1]), int(median_bgr[0]))

    @staticmethod
    def _contrast_color(bg_rgb: tuple[int, int, int]) -> tuple[int, int, int]:
        """背景色に対して可読性の高い文字色（白 or 黒）を返す。

        ITU-R BT.601 の輝度近似式で背景の明るさを判定する。
        """
        r, g, b = bg_rgb
        luminance = 0.299 * r + 0.587 * g + 0.114 * b
        return (0, 0, 0) if luminance > 128 else (255, 255, 255)
