# SRTForge

あらゆるLLM APIでSRT字幕ファイルを翻訳 — **チャンク並列処理、再開可能**。

SRTForgeはWindowsデスクトップアプリ（PySide6）で、字幕ファイルを小さなチャンクに分割し、
OpenAI互換のチャット補完エンドポイント（OpenRouter、OpenAI、Together、ローカルのOllama、…）に
**並列に**送信し、整形式の`. srt`として書き戻します。チャンクサイズはモデルのコンテキスト
ウィンドウに合わせて調整されるため、小さいコンテキストモデル（8k）でも問題なく動作します。

![ダークテーマのプレビュー](docs/screenshot-dark.png)

**🌐 言語:** [English](README.md) · [فارسی (Persian)](README.fa.md) · [العربية (Arabic)](README.ar.md) · [日本語](README.ja.md)

## 機能

- 🌗 **ダークテーマがデフォルト**、ライトテーマ、またはOSに連動。
- 🧩 **スマートなチャンク分割** — 文の途中で分割されることはなく、
  モデルの実コンテキストウィンドウに基づいてサイズが調整されます。
- 📊 **美しいプログレスバー** — チャンクごとのグリッド表示、進捗率、残り時間。
- 🔁 **再開 / 再試行 / キャンセル** — サイドカーファイル（`<name>.srtforge.json`）が
  完了済みチャンクを記憶。クラッシュしても未完了分のみ再翻訳されます。
- ⚡ **並列リクエスト** — 同時実行数を設定可能（デフォルト6）。
- 🎛️ **モデルコンテキストを`/models`から自動検出**、または任意のカスタムモデルを手動入力。
- 🌐 **ソース言語の自動検出**（`auto`）または明示的指定；任意のターゲット言語。
- ✍️ **カスタムプロンプト** — 翻訳指示は完全に編集可能
  （トーン、用語集、技術用語など）。
- 👤 **APIプロファイル** — 複数のベースURLとキーを保存（OpenRouter、9Router、その他）。
- 📚 **バッチキュー** — 複数の`.srt`ファイルを追加して一括翻訳。
- 👀 **プレビュー** — 原文と翻訳を並べて表示、検索可能。
- 🪵 **リアルタイムログ** — カラー表示、保存可能。
- 🧵 **小コンテキストに優しい** — 8kコンテキストモデルですぐ動作。

## インストール

### 簡単な方法（Python不要）

1. [Releases](https://github.com/YOURUSER/srtforge/releases)ページから`SRTForge.exe`をダウンロード。
2. 実行する。完了。

### ソースから

Python 3.11+が必要です。

```bash
git clone https://github.com/YOURUSER/srtforge.git
cd srtforge
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -e .
srtforge                      # または: python -m srtforge
```

オプション — OpenAI系モデルのトークン推定が向上:

```bash
pip install -e .[tokenize]
```

## クイックスタート

1. **API Profiles**（ツールバー）→ **New**を開き、エンドポイントとAPIキーを入力。
   SRTForgeはOpenAI互換APIなら何でも動作します。例:
   - **OpenRouter:** `https://openrouter.ai/api/v1` — キー: `sk-or-…`
   - **9Router:** `https://9router.com/api/v1` — または任意のカスタムルーターエンドポイント
   - **OpenAI:** `https://api.openai.com/v1`
   - **ローカル (Ollama, LM Studio):** `http://localhost:11434/v1`
2. **Model**を選択 — SRTForgeがモデルリスト（コンテキストサイズ付き）を`/models`から
   自動取得します。`Refresh`で再取得。
3. **Add SRT…**で字幕ファイルを選択。
4. **Source**（`auto`または明示）と**Target**言語を選択。
5. **Start**を押す（または`Ctrl+Enter`）。

出力はソースファイルと同じ場所に`<name>.out.srt`として保存されます。
一部のチャンクが失敗した場合、次回のStartで失敗分のみ再送されます（再開）。

## チャンク分割の仕組み

各SRTキュー（cue）は分割不可能な単位 — 字幕を途中で割ることはありません。
トークンを見積もり（OpenAI系はtiktoken、それ以外はCJK対応ヒューリスティック）、
貪欲法で次の上限まで詰めます:

```
予算 = context_length × safety_margin − output_tokens − prompt_overhead
```

`safety_margin`（デフォルト0.85）と`max_output_tokens`は**Settings**で設定可能。
モデルコンテキスト長は`/models`から読み取ります
（`context_length` / `top_provider.max_completion_tokens`）；
モデルが検出できない場合は、モデルボックスに任意のIDを入力し、Settingsで
手動コンテキストを設定できます。

プロンプトは厳格なJSON出力（`{"translations": [{"i":…,"t":…}]}`）を要求し、
クライアントが検証・修復します — "モデルが余計なことを言った"という驚きはありません。

## プライバシー

- 設定（APIキーを含む）は**ローカル**の`%APPDATA%/srtforge/settings.json`に
  保存されます。キーはログに残されません。
- テレメトリなし、選択したAPIエンドポイント
  （`/models`と`/chat/completions`）以外へのネットワーク呼び出しなし。
- 字幕コンテンツは設定したAPIプロバイダーに送信されます — それがアプリの本質です。
  完全なプライバシーが必要な場合は、ローカルモデル
  （Ollama、LM Studio）へ`http://localhost:11434/v1`で接続してください。

## 開発

```bash
pip install -e .[dev]
pytest                 # ユニットテスト（ネットワーク不要）
ruff check src tests
```

### .exeのビルド

```bash
pip install pyinstaller
pyinstaller srtforge.spec
# → dist/SRTForge.exe
```

## ロードマップ

- Anthropicネイティブエンドポイント（OpenAI互換に加えて）
- ASS/SSA出力、VTTパススルー
- ファイル別の用語集 / 用語ガード
- アプリ内字幕エディタ

## ライセンス

MIT — [LICENSE](LICENSE)を参照。