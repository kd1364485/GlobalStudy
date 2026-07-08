# GlobalStudy

英語のAI・プログラミング・コンピュータサイエンス動画を視聴しながら、日本語でより深く理解するためのローカル学習支援アプリ。

「翻訳」ではなく「理解」を支援する。

## 全体フロー

```
画面キャプチャ → OCR → ローカルLLM (Ollama) → 日本語訳・専門用語解説・重要ポイント表示
```

## 技術スタック

| 役割 | 技術 |
| --- | --- |
| GUI | PySide6 |
| 画面キャプチャ | dxcam / mss |
| OCR | PaddleOCR |
| LLM | Ollama (ローカル) |
| DB | SQLite |

## セットアップ

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e .
```

## 実行

```powershell
python -m globalstudy.main
```

## ディレクトリ構成

```
src/globalstudy/
├── main.py       # エントリポイント
├── config/       # 設定値の集約
├── utils/        # ロガー等の共通ユーティリティ
├── ui/           # GUI（services のみに依存）
├── capture/      # 画面キャプチャ・ホットキー
├── ocr/          # OCR（エンジン差し替え可能）
├── ai/           # LLM クライアント（差し替え可能）
├── services/     # ユースケース統合（capture→ocr→ai）
├── models/       # データモデル
└── storage/      # SQLite・学習履歴
```

アーキテクチャ詳細は [docs/architecture.md](docs/architecture.md) を参照。
