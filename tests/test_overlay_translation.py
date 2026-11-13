"""オーバーレイ翻訳サービスの単体テスト。

キャプチャ・OCR・LLM を偽物に差し替え、LLM のストリーミング応答の解析、
翻訳しない行の判定、キャッシュ、背景色と文字色の決め方を確かめる。
Ollama と画面は使わない。
"""

from pathlib import Path

import cv2
import numpy as np
import pytest

from globalstudy.models.ocr_result import OcrLine, OcrResult
from globalstudy.models.region import CaptureRegion
from globalstudy.services.overlay_translation_service import (
    OverlayTranslationError,
    OverlayTranslationService,
)


class FakeCapture:
    def __init__(self, image_path: Path) -> None:
        self._image_path = image_path
        self.region = CaptureRegion(left=0, top=0, width=200, height=100)

    def capture(self) -> Path:
        return self._image_path


class FakeOcr:
    def __init__(self, result: OcrResult) -> None:
        self._result = result

    def extract_text(self, image_path: Path) -> OcrResult:
        return self._result


class FakeAi:
    """決めたチャンク列をそのまま返す LLM の代わり。受け取ったプロンプトを記録する。"""

    def __init__(self, chunks: list[str]) -> None:
        self._chunks = chunks
        self.prompts: list[str] = []

    def ask_stream(self, prompt: str):
        self.prompts.append(prompt)
        yield from self._chunks


def _line(text: str, top: int = 10) -> OcrLine:
    return OcrLine(text=text, confidence=0.99, left=10, top=top, width=80, height=20)


@pytest.fixture
def white_image(tmp_path: Path) -> Path:
    path = tmp_path / "white.png"
    cv2.imwrite(str(path), np.full((100, 200, 3), 255, dtype=np.uint8))
    return path


def _service(image: Path, lines: list[OcrLine], chunks: list[str]):
    ocr = OcrResult(text="\n".join(l.text for l in lines), confidence=0.99, lines=tuple(lines))
    ai = FakeAi(chunks)
    service = OverlayTranslationService(FakeCapture(image), FakeOcr(ocr), ai)
    return service, ai


def test_stream_split_mid_line_is_reassembled(white_image: Path) -> None:
    """行の途中でチャンクが切れても、改行がそろってから 1 行として解析する。"""
    lines = [_line("Hello world", 10), _line("Good morning", 40)]
    service, _ = _service(white_image, lines, ["1: こんに", "ちは世界\n2: おは", "よう"])

    _, _, patches = service.prepare_and_stream()
    texts = [p.text for p in patches]

    assert texts == ["こんにちは世界", "おはよう"]


def test_lines_without_words_and_urls_are_not_sent(white_image: Path) -> None:
    """数字だけ・記号だけ・URL の行は LLM に送らない。"""
    lines = [
        _line("Attention is all you need", 10),
        _line("42", 30),
        _line("--> |", 50),
        _line("https://example.com/paper", 70),
    ]
    service, ai = _service(white_image, lines, ["1: アテンションこそすべて\n"])

    _, _, patches = service.prepare_and_stream()
    patches = list(patches)

    assert len(ai.prompts) == 1
    assert "1: Attention is all you need" in ai.prompts[0]
    assert "42" not in ai.prompts[0]
    assert "example.com" not in ai.prompts[0]
    assert [p.text for p in patches] == ["アテンションこそすべて"]


def test_out_of_range_and_unparsable_lines_are_ignored(white_image: Path) -> None:
    """番号が範囲外の行や、番号のない行(前置きなど)は無視する。"""
    lines = [_line("Hello world")]
    service, _ = _service(
        white_image, lines, ["以下が訳です\n", "5: 余計な行\n", "1：こんにちは世界\n"]
    )

    _, _, patches = service.prepare_and_stream()

    assert [p.text for p in patches] == ["こんにちは世界"]


def test_cache_skips_llm_on_second_run(white_image: Path) -> None:
    """同じ画面をもう一度訳すときは、キャッシュから出して LLM を呼ばない。"""
    lines = [_line("Hello world")]
    service, ai = _service(white_image, lines, ["1: こんにちは世界\n"])

    list(service.prepare_and_stream()[2])
    second = list(service.prepare_and_stream()[2])

    assert len(ai.prompts) == 1
    assert [p.text for p in second] == ["こんにちは世界"]

    service.clear_cache()
    list(service.prepare_and_stream()[2])
    assert len(ai.prompts) == 2


def test_duplicate_lines_are_translated_once(white_image: Path) -> None:
    """同じ文字列の行が 2 つあれば、1 回だけ送り、両方の位置にパッチを置く。"""
    lines = [_line("Summary", 10), _line("Summary", 60)]
    service, ai = _service(white_image, lines, ["1: まとめ\n"])

    patches = list(service.prepare_and_stream()[2])

    assert ai.prompts[0].count("Summary") == 1
    assert sorted(p.top for p in patches) == [10, 60]


def test_empty_ocr_raises(white_image: Path) -> None:
    service, _ = _service(white_image, [], [])
    with pytest.raises(OverlayTranslationError):
        service.prepare_and_stream()


def test_background_and_text_color(tmp_path: Path) -> None:
    """背景は行の周りの色の中央値、文字色は背景の明るさで白か黒を選ぶ。"""
    image = np.zeros((100, 200, 3), dtype=np.uint8)
    image[:, :] = (40, 20, 10)  # BGR。暗い青
    line = _line("Hello world", 30)

    bg = OverlayTranslationService._sample_background(image, line)

    assert bg == (10, 20, 40)  # RGB に並べ替わる
    assert OverlayTranslationService._contrast_color(bg) == (255, 255, 255)
    assert OverlayTranslationService._contrast_color((250, 250, 250)) == (0, 0, 0)
    assert OverlayTranslationService._sample_background(None, line) == (255, 255, 255)
