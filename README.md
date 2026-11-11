# GlobalStudy

英語のAI・プログラミング・コンピュータサイエンス動画を視聴しながら、日本語でより深く理解するためのローカル学習支援アプリ。

「翻訳」ではなく「理解」を支援する。

## 全体フロー

```
範囲を選ぶ → Ctrl+Shift+Q → 画面キャプチャ → OCR → ローカルLLM (Ollama) → 日本語訳を流れるように表示(ストリーミング)
```

すべてこの PC の中で動く(外部の API を使わない)。

## いまできること / まだのこと(2026/11/05 時点)

| | 状態 |
| --- | --- |
| 範囲選択・ホットキーでのキャプチャ・OCR・日本語訳(ストリーミング表示) | **できる**(画面から使える) |
| 専門用語の解説・重要ポイント・初心者向けの説明 | **プロンプトと解析処理はある**(`build_analysis_prompt`、`parse_analysis_response`)。ただし、**画面からは呼ばれていない**。応答の速さを優先して、画面は訳だけにしている。手動の確認スクリプト `tests/manual_prompt_check.py` で動作を確かめられる |
| 学習履歴の保存(SQLite) | **未実装**(`storage/` は空。保存先のパスの設定だけある) |
| リアルタイムのキャプチャ(dxcam) | **未実装**(今は mss での 1 枚ずつのキャプチャ。dxcam に差し替えられる設計にしてある) |

## 技術スタック

| 役割 | 技術 |
| --- | --- |
| GUI | PySide6 |
| 画面キャプチャ・ホットキー | mss / pynput |
| OCR | PaddleOCR(RapidOCR に設定で切り替え可能) |
| LLM | Ollama (ローカル)、既定のモデルは `qwen3:8b` |

設定値はすべて `src/globalstudy/config/settings.py` に集めている(ホットキー、OCR エンジン、モデル名など)。

## セットアップ

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e .
ollama pull qwen3:8b
```

## 実行

```powershell
python -m globalstudy.main
```

## 速さ(2026/11/05、この PC で測定、各 1 回)

環境: RTX 3060 Laptop(6GB)、Windows 11。2 行の英文(約 100 文字)で測った。

| 処理 | 時間 |
| --- | --- |
| OCR(PaddleOCR、エンジンの初期化を含む) | 約 18 秒 |
| 日本語訳(LLM)、**最初の 1 回** | 約 76 秒 |
| 日本語訳(LLM)、**2 回目から** | 約 4 秒 |

最初の 1 回が遅いのは、モデル(読み込むと約 6GB)を GPU に読み込むため。GPU のメモリに入りきらず、約 3 割を CPU で動かしている(`ollama ps` で `30%/70% CPU/GPU`)。
Ollama は 5 分使わないとモデルを外すので、間が空くと、また最初の 1 回と同じだけ待つ。

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
└── storage/      # 学習履歴(未実装)
```

アーキテクチャ詳細は [docs/architecture.md](docs/architecture.md) を参照。
目指している全体像(用語辞典など、これから作るものを含む)は [開発コンセプト.md](開発コンセプト.md) にある。
