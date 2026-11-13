"""画面・LLM に依存しない小さな関数の単体テスト。"""

import numpy as np

from globalstudy.ai.prompts import build_line_translation_prompt
from globalstudy.capture.hotkey_listener import HotkeyListener
from globalstudy.capture.slide_monitor import _dhash_from_gray, hash_distance
from globalstudy.config import Config
from globalstudy.config.settings import source_language_to_ocr_code


def test_dhash_same_image_distance_zero() -> None:
    gray = np.tile(np.arange(90, dtype=np.uint8), (80, 1))
    assert hash_distance(_dhash_from_gray(gray), _dhash_from_gray(gray.copy())) == 0


def test_dhash_detects_slide_change() -> None:
    """左から右へ明るくなる画像と、その左右反転は、64bit すべてが違う。"""
    gradient = np.tile(np.arange(0, 180, 2, dtype=np.uint8), (80, 1))
    flipped = gradient[:, ::-1].copy()
    a, b = _dhash_from_gray(gradient), _dhash_from_gray(flipped)
    assert a.shape == (64,)
    assert hash_distance(a, b) == 64


def test_dhash_ignores_small_noise() -> None:
    """圧縮のノイズ程度の揺れでは、変化と判定する閾値(既定 10bit)を超えない。"""
    rng = np.random.default_rng(0)
    gradient = np.tile(np.arange(0, 180, 2, dtype=np.int16), (80, 1))
    noisy = np.clip(gradient + rng.integers(-2, 3, gradient.shape), 0, 255)
    distance = hash_distance(
        _dhash_from_gray(gradient.astype(np.uint8)),
        _dhash_from_gray(noisy.astype(np.uint8)),
    )
    assert distance <= Config().capture.auto_hash_threshold


def test_hotkey_to_pynput_format() -> None:
    assert HotkeyListener._to_pynput_format("Ctrl+Shift+Q") == "<ctrl>+<shift>+q"
    assert HotkeyListener._to_pynput_format("alt+f1") == "<alt>+f1"


def test_source_language_to_ocr_code() -> None:
    assert source_language_to_ocr_code("English") == "en"
    assert source_language_to_ocr_code("japanese") == "japan"
    assert source_language_to_ocr_code("klingon") == "en"  # 未定義は英語に戻す


def test_line_prompt_is_numbered_from_one() -> None:
    prompt = build_line_translation_prompt(["first", "second"])
    assert "1: first\n2: second" in prompt


def test_ollama_url_uses_ipv4_literal() -> None:
    """localhost だと Windows で IPv6 を先に試して約 2 秒待つため、IPv4 を直接指定する。"""
    config = Config()
    for url in (config.llm.base_url, config.overlay_llm.base_url, config.vlm.base_url):
        assert "localhost" not in url
        assert url.startswith("http://127.0.0.1:")
