"""処理パイプラインの段階別の時間と、OCR の読み取り精度を測るスクリプト。

GUI は使わず、アプリと同じサービス（CaptureService 以外）を直接呼ぶ。
入力は、このスクリプトが描画するテスト用スライド画像（正解の文字列が分かっている）。

測るもの:
  1. 画面キャプチャ（mss、1280x720、PNG 保存まで）
  2. OCR（RapidOCR）: 初回（モデル読み込み込み）と 2 回目以降
  3. 翻訳（qwen3:8b、ストリーミング）: 最初の文字が出るまで / 全文
  4. オーバーレイ翻訳（qwen3:1.7b、行単位）: 最初のパッチ / 全パッチ
  LLM は「モデルが VRAM にない状態（cold）」と「読み込み済み（warm）」の両方を測る。

実行（Ollama を起動しておく）:
  .venv\\Scripts\\python.exe -X utf8 tools\\bench_pipeline.py [warm の回数(既定 5)]
"""

import statistics
import sys
import tempfile
import time
from difflib import SequenceMatcher
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont

from globalstudy.ai.ollama_client import OllamaClient
from globalstudy.ai.prompts import build_translation_prompt
from globalstudy.capture.screen_capturer import ScreenCapturer
from globalstudy.config import Config
from globalstudy.models.region import CaptureRegion
from globalstudy.ocr.rapidocr_engine import RapidOcrEngine
from globalstudy.services.ai_service import AiService
from globalstudy.services.ocr_service import OcrService
from globalstudy.services.overlay_translation_service import (
    OverlayTranslationService,
)

# テスト用スライドの本文（自作の文章。正解として OCR 精度の計算に使う）
SLIDE_LINES = [
    "Why batching helps GPU inference",
    "A single request uses only a small part of the GPU.",
    "Batching groups several requests into one kernel launch,",
    "so the fixed cost per launch is shared.",
    "The trade-off: each request waits a little longer",
    "until the batch is full or a timeout expires.",
]


def render_slide(path: Path) -> None:
    """白背景に黒文字のスライド画像（1280x720）を描画する。"""
    image = Image.new("RGB", (1280, 720), "white")
    draw = ImageDraw.Draw(image)
    title_font = ImageFont.truetype("arial.ttf", 48)
    body_font = ImageFont.truetype("arial.ttf", 32)
    draw.text((80, 70), SLIDE_LINES[0], fill="black", font=title_font)
    for i, line in enumerate(SLIDE_LINES[1:]):
        draw.text((80, 190 + i * 70), line, fill="black", font=body_font)
    image.save(path)


def unload_model(config: Config, model: str) -> None:
    """Ollama にモデルを VRAM から外させる（cold の測定用）。"""
    requests.post(
        f"{config.llm.base_url}/api/generate",
        json={"model": model, "keep_alive": 0},
        timeout=60,
    ).raise_for_status()
    time.sleep(2)


def time_stream(chunks) -> tuple[float, float, str]:
    """ストリームを最後まで読み、(最初のチャンクまで, 全体, 全文) を秒で返す。"""
    start = time.perf_counter()
    first = None
    text = ""
    for chunk in chunks:
        if first is None:
            first = time.perf_counter() - start
        text += chunk
    total = time.perf_counter() - start
    return (first if first is not None else total), total, text


def summarize(label: str, values: list[float], unit: str = "ms") -> str:
    scale = 1000 if unit == "ms" else 1
    vals = sorted(v * scale for v in values)
    med = statistics.median(vals)
    return (
        f"{label:<34} n={len(vals)}  median {med:8.1f} {unit}"
        f"  min {vals[0]:8.1f}  max {vals[-1]:8.1f}"
    )


class _FixedImageCapture:
    """オーバーレイ翻訳サービスに、固定のスライド画像を渡すための差し替え。"""

    def __init__(self, image_path: Path) -> None:
        self._image_path = image_path
        self.region = CaptureRegion(left=0, top=0, width=1280, height=720)

    def capture(self) -> Path:
        return self._image_path


def main() -> None:
    runs = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    config = Config()
    config.ensure_directories()
    workdir = Path(tempfile.mkdtemp(prefix="globalstudy_bench_"))
    slide = workdir / "slide.png"
    render_slide(slide)
    print(f"テスト画像: {slide}")
    results: list[str] = []

    # 1. 画面キャプチャ（画面の左上 1280x720。中身は問わず、時間だけを見る）
    capturer = ScreenCapturer(config)
    region = CaptureRegion(left=0, top=0, width=1280, height=720)
    cap_times = []
    for _ in range(runs):
        t0 = time.perf_counter()
        shot = capturer.capture(region)
        cap_times.append(time.perf_counter() - t0)
        shot.unlink(missing_ok=True)
    results.append(summarize("capture (mss + PNG save)", cap_times))

    # 2. OCR
    ocr = OcrService(config, engine=RapidOcrEngine(lang="en"))
    t0 = time.perf_counter()
    ocr_result = ocr.extract_text(slide)
    ocr_cold = time.perf_counter() - t0
    ocr_warm = []
    for _ in range(runs):
        t0 = time.perf_counter()
        ocr_result = ocr.extract_text(slide)
        ocr_warm.append(time.perf_counter() - t0)
    results.append(summarize("OCR cold (model load + 1st)", [ocr_cold]))
    results.append(summarize("OCR warm", ocr_warm))

    truth = "\n".join(SLIDE_LINES)
    ratio = SequenceMatcher(None, truth, ocr_result.text).ratio()
    exact = sum(
        1 for a, b in zip(SLIDE_LINES, ocr_result.text.split("\n")) if a == b
    )
    results.append(
        f"OCR accuracy: char similarity {ratio:.3f}, exact lines "
        f"{exact}/{len(SLIDE_LINES)}, mean confidence {ocr_result.confidence:.3f}"
    )

    # 3. 翻訳（qwen3:8b）
    ai = AiService(config)
    prompt = build_translation_prompt(ocr_result.text)
    unload_model(config, config.llm.model)
    first, total, translation = time_stream(ai.ask_stream(prompt))
    results.append(summarize(f"translate cold first chunk ({config.llm.model})", [first]))
    results.append(summarize(f"translate cold total ({config.llm.model})", [total]))
    firsts, totals = [], []
    for _ in range(runs):
        first, total, translation = time_stream(ai.ask_stream(prompt))
        firsts.append(first)
        totals.append(total)
    results.append(summarize("translate warm first chunk", firsts))
    results.append(summarize("translate warm total", totals))

    # 4. オーバーレイ翻訳（qwen3:1.7b、行単位）。キャッシュを毎回消して測る
    overlay_ai = AiService(
        config, client=OllamaClient(config, llm_config=config.overlay_llm)
    )
    overlay = OverlayTranslationService(
        capture_service=_FixedImageCapture(slide),
        ocr_service=ocr,
        ai_service=overlay_ai,
    )

    def run_overlay() -> tuple[float, float, int]:
        overlay.clear_cache()
        t0 = time.perf_counter()
        _, _, patches = overlay.prepare_and_stream()
        first = None
        count = 0
        for _ in patches:
            if first is None:
                first = time.perf_counter() - t0
            count += 1
        total = time.perf_counter() - t0
        return (first if first is not None else total), total, count

    unload_model(config, config.overlay_llm.model)
    first, total, count = run_overlay()
    results.append(summarize(f"overlay cold first patch ({config.overlay_llm.model})", [first]))
    results.append(summarize("overlay cold all patches", [total]))
    o_first, o_total, counts = [], [], []
    for _ in range(runs):
        first, total, count = run_overlay()
        o_first.append(first)
        o_total.append(total)
        counts.append(count)
    results.append(summarize("overlay warm first patch (incl. OCR)", o_first))
    results.append(summarize("overlay warm all patches (incl. OCR)", o_total))
    results.append(f"overlay patches per run: {counts} (lines on slide: {len(SLIDE_LINES)})")

    print("\n".join(["", "=== results ==="] + results))
    print("\n=== OCR text ===\n" + ocr_result.text)
    print("\n=== translation (last warm run) ===\n" + translation)


if __name__ == "__main__":
    main()
