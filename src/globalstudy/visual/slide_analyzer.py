"""OpenCV ベースのスライド画像解析。

キャプチャ画像から視覚的特徴量を抽出し、スライド種別を判定する。
判定閾値は暫定値であり、実際のスライドで調整することを想定する。
"""

from pathlib import Path

import cv2
import numpy as np

from globalstudy.models.ocr_result import OcrResult
from globalstudy.models.slide_analysis import (
    SlideVisualAnalysis,
    SlideVisualType,
)
from globalstudy.utils.logger import get_logger

logger = get_logger(__name__)

# 判定閾値（暫定・調整対象）
_TEXT_AREA_RATIO_THRESHOLD = 0.15
_COLOR_REGION_RATIO_THRESHOLD = 0.08
_LINE_COUNT_THRESHOLD = 20
_VISUAL_HEAVY_COLOR_THRESHOLD = 0.20
_VISUAL_HEAVY_TEXT_THRESHOLD = 0.05


class SlideAnalyzer:
    """OpenCV を用いてスライド画像の視覚的特徴量を抽出する。

    以下の特徴量を計算し、スライド種別（TEXT_ONLY / MIXED_SLIDE / VISUAL_HEAVY）を判定する:
    - テキスト領域の面積比率（モルフォロジー変換ベース）
    - 色付き領域の比率（彩度ベース）
    - 直線検出数（Hough変換ベース）
    - エッジ密度（Cannyベース）
    - OCRテキスト行数・信頼度
    """

    def analyze(
        self,
        image_path: Path,
        ocr_result: OcrResult,
    ) -> SlideVisualAnalysis:
        """画像とOCR結果からスライド種別を判定する。

        Args:
            image_path: キャプチャ画像のパス。
            ocr_result: OCRエンジンの抽出結果。

        Returns:
            スライド判定結果。
        """
        image = cv2.imread(str(image_path))
        if image is None:
            logger.warning("画像を読み込めませんでした: %s", image_path)
            return self._fallback(ocr_result)

        # グレースケール変換（特徴量計算の基準）
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape[:2]
        total_area = float(h * w)

        # 各特徴量を計算
        text_area_ratio = self._estimate_text_area(gray, total_area)
        line_count, h_lines, v_lines = self._detect_lines(gray)
        color_region_ratio = self._color_region_ratio(image, total_area)
        edge_density = self._edge_density(gray)
        non_text_area_ratio = max(0.0, 1.0 - text_area_ratio)

        # OCR結果からテキスト行数を算出
        ocr_line_count = ocr_result.text.count("\n") + 1 if ocr_result.text.strip() else 0
        ocr_confidence = ocr_result.confidence

        # 特徴量からスライド種別を判定
        visual_type = self._classify(
            text_area_ratio=text_area_ratio,
            color_region_ratio=color_region_ratio,
            line_count=line_count,
            ocr_line_count=ocr_line_count,
        )
        recommendation = self._recommendation(visual_type)

        debug_info = {
            "image_width": w,
            "image_height": h,
            "text_area_ratio": round(text_area_ratio, 4),
            "non_text_area_ratio": round(non_text_area_ratio, 4),
            "line_count": line_count,
            "horizontal_line_count": h_lines,
            "vertical_line_count": v_lines,
            "color_region_ratio": round(color_region_ratio, 4),
            "edge_density": round(edge_density, 4),
            "ocr_line_count": ocr_line_count,
            "ocr_confidence": round(ocr_confidence, 4),
        }
        logger.info(
            "スライド判定: %s (text=%.2f, color=%.2f, lines=%d, ocr_lines=%d)",
            visual_type.value,
            text_area_ratio,
            color_region_ratio,
            line_count,
            ocr_line_count,
        )
        logger.debug("判定詳細: %s", debug_info)

        return SlideVisualAnalysis(
            visual_type=visual_type,
            text_area_ratio=text_area_ratio,
            non_text_area_ratio=non_text_area_ratio,
            line_count=line_count,
            horizontal_line_count=h_lines,
            vertical_line_count=v_lines,
            color_region_ratio=color_region_ratio,
            edge_density=edge_density,
            ocr_line_count=ocr_line_count,
            ocr_confidence=ocr_confidence,
            recommendation=recommendation,
            debug_info=debug_info,
        )

    @staticmethod
    def _estimate_text_area(gray: np.ndarray, total_area: float) -> float:
        """テキスト領域の面積比率を推定する。

        モルフォロジー変換でテキストらしき領域を抽出し、
        輪郭面積の合計を画像全体で割る。
        """
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 5))
        dilated = cv2.dilate(binary, kernel, iterations=2)
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        text_area = sum(cv2.contourArea(c) for c in contours)
        return min(text_area / total_area, 1.0) if total_area > 0 else 0.0

    @staticmethod
    def _detect_lines(gray: np.ndarray) -> tuple[int, int, int]:
        """直線を検出し、総数・水平線数・垂直線数を返す。"""
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        lines = cv2.HoughLinesP(
            edges,
            rho=1,
            theta=np.pi / 180,
            threshold=80,
            minLineLength=max(50, gray.shape[1] // 10),
            maxLineGap=20,
        )
        if lines is None:
            return 0, 0, 0

        total = 0
        h_count = 0
        v_count = 0
        for line in lines:
            x1, y1, x2, y2 = line[0]
            angle = abs(np.arctan2(y2 - y1, x2 - x1) * 180.0 / np.pi)
            total += 1
            if angle < 15 or angle > 165:
                h_count += 1
            elif 75 < angle < 105:
                v_count += 1
        return total, h_count, v_count

    @staticmethod
    def _color_region_ratio(image: np.ndarray, total_area: float) -> float:
        """色付き領域（白・黒・グレー以外）の比率を計算する。"""
        b, g, r = cv2.split(image)
        max_ch = np.maximum(np.maximum(r, g), b).astype(np.int16)
        min_ch = np.minimum(np.minimum(r, g), b).astype(np.int16)
        saturation = max_ch - min_ch
        color_mask = saturation > 30
        color_area = float(np.count_nonzero(color_mask))
        return min(color_area / total_area, 1.0) if total_area > 0 else 0.0

    @staticmethod
    def _edge_density(gray: np.ndarray) -> float:
        """エッジ密度（エッジ画素数 / 総画素数）を計算する。"""
        edges = cv2.Canny(gray, 50, 150)
        return float(np.count_nonzero(edges)) / float(gray.size)

    @staticmethod
    def _classify(
        text_area_ratio: float,
        color_region_ratio: float,
        line_count: int,
        ocr_line_count: int,
    ) -> SlideVisualType:
        """特徴量からスライド種別を判定する。

        判定ロジック（暫定閾値）:
        1. 色領域が多く(>=20%)テキストが少ない(<=5%) → VISUAL_HEAVY
        2. 色領域 or 直線が多く、テキストが少ない → VISUAL_HEAVY
        3. 色領域 or 直線が多い → MIXED_SLIDE
        4. 上記以外 → TEXT_ONLY
        """
        if (
            color_region_ratio >= _VISUAL_HEAVY_COLOR_THRESHOLD
            and text_area_ratio <= _VISUAL_HEAVY_TEXT_THRESHOLD
        ):
            return SlideVisualType.VISUAL_HEAVY
        if (
            color_region_ratio >= _COLOR_REGION_RATIO_THRESHOLD
            or line_count >= _LINE_COUNT_THRESHOLD
        ) and text_area_ratio < _TEXT_AREA_RATIO_THRESHOLD:
            return SlideVisualType.VISUAL_HEAVY
        if (
            color_region_ratio >= _COLOR_REGION_RATIO_THRESHOLD
            or line_count >= _LINE_COUNT_THRESHOLD
        ):
            return SlideVisualType.MIXED_SLIDE
        return SlideVisualType.TEXT_ONLY

    @staticmethod
    def _recommendation(visual_type: SlideVisualType) -> str:
        """スライド種別に応じたUI表示用メッセージを返す。"""
        if visual_type == SlideVisualType.TEXT_ONLY:
            return "テキスト中心のスライドです。OCR翻訳で十分です。"
        if visual_type == SlideVisualType.MIXED_SLIDE:
            return "図やグラフが含まれている可能性があります。VLM解析を推奨します。"
        return "画像・グラフ中心のスライドです。VLM解析を強く推奨します。"

    @staticmethod
    def _fallback(ocr_result: OcrResult) -> SlideVisualAnalysis:
        """画像読み込み失敗時のフォールバック。"""
        ocr_line_count = ocr_result.text.count("\n") + 1 if ocr_result.text.strip() else 0
        return SlideVisualAnalysis(
            visual_type=SlideVisualType.TEXT_ONLY,
            text_area_ratio=0.0,
            non_text_area_ratio=1.0,
            line_count=0,
            horizontal_line_count=0,
            vertical_line_count=0,
            color_region_ratio=0.0,
            edge_density=0.0,
            ocr_line_count=ocr_line_count,
            ocr_confidence=ocr_result.confidence,
            recommendation="画像解析をスキップしました（画像読み込み失敗）。",
            debug_info={"error": 1.0},
        )
