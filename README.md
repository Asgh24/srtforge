# SRTForge

Translate SRT subtitle files with any LLM API — **chunked, parallel, resumable**.

SRTForge is a Windows desktop app (PySide6) that splits a subtitle file into
small chunks, sends them to an OpenAI-compatible chat-completions endpoint
(OpenRouter, OpenAI, Together, local Ollama, …) **concurrently**, and writes
back a properly-formatted `.srt`. Chunk size adapts to the model's context
window, so even small-context models (8k) work fine.

![Dark theme preview](docs/screenshot-dark.png)

**🌐 Languages:** [English](README.md) · [فارسی (Persian)](README.fa.md) · [العربية (Arabic)](README.ar.md) · [日本語 (Japanese)](README.ja.md)

## Features

- 🌗 **Dark theme by default**, light theme, or follow the OS.
- 🧩 **Smart chunking** — cues are grouped without ever splitting a sentence,
  sized from the model's real context window.
- 📊 **Beautiful progress bar** — per-chunk grid overlay, % done, ETA.
- 🔁 **Resume / retry / cancel** — per-file sidecar (`<name>.srtforge.json`)
  remembers done chunks; a crash means you only re-translate what's left.
- ⚡ **Parallel requests** — configurable concurrency (default 6).
- 🎛️ **Detect model context automatically** from `/models`, or enter it
  manually for any custom model.
- 🌐 **Source auto-detect** (`auto`) or explicit; any target language.
- ✍️ **Custom prompt** — the translation instructions are fully editable
  (tone, glossary, technical terms, etc.).
- 👤 **API profiles** — save multiple base URLs + keys (OpenRouter, others).
- 📚 **Batch queue** — add many `.srt` files, translate them in one go.
- 👀 **Preview** — source/translated cues side by side, searchable.
- 🪵 **Real-time logs** — color-coded, saveable.
- 🧵 **Small-context friendly** — works with 8k-context models out of the box.

## Installation

### Easy way (no Python needed)

1. Download `SRTForge.exe` from the [Releases](https://github.com/YOURUSER/srtforge/releases) page.
2. Run it. Done.

### From source

Requires Python 3.11+.

```bash
git clone https://github.com/YOURUSER/srtforge.git
cd srtforge
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -e .
srtforge                      # or: python -m srtforge
```

Optional — better token estimation for OpenAI-family models:

```bash
pip install -e .[tokenize]
```

## Quick start

1. Open **API Profiles** (toolbar) → **New**, enter your API endpoint and key.
   SRTForge works with any OpenAI-compatible API. Examples:
   - **OpenRouter:** `https://openrouter.ai/api/v1` — key: `sk-or-…`
   - **9Router:** `https://9router.com/api/v1` — or any custom router endpoint
   - **OpenAI:** `https://api.openai.com/v1`
   - **Local (Ollama, LM Studio):** `http://localhost:11434/v1`
2. Pick a **Model** — SRTForge fetches the model list (with context sizes)
   from `/models` automatically. `Refresh` re-fetches.
3. **Add SRT…** and pick your subtitle file(s).
4. Choose **Source** (`auto` or specific) and **Target** language.
5. Hit **Start** (or `Ctrl+Enter`).

Output is written next to the source as `<name>.out.srt`. If some chunks
fail, only those are re-sent on the next Start (resume).

## How chunking works

Each SRT cue is an indivisible unit — we never split a subtitle in half.
We estimate tokens (tiktoken for OpenAI models, a CJK-aware heuristic
otherwise), then greedily fill chunks up to:

```
budget = context_length × safety_margin − output_tokens − prompt_overhead
```

`safety_margin` (default 0.85) and `max_output_tokens` are configurable in
**Settings**. The model's context length is read from `/models`
(`context_length` / `top_provider.max_completion_tokens`); if a model can't
be detected you can type any ID in the model box and set a manual context
in Settings.

The prompt asks for strict JSON output (`{"translations": [{"i":…,"t":…}]}`)
and the client validates + repairs it — no “the model added a commentary”
surprises.

## Privacy

- Settings (including API keys) are stored **locally** in
  `%APPDATA%/srtforge/settings.json`. Keys are never logged.
- No telemetry, no network calls except to your chosen API endpoint
  (`/models` and `/chat/completions`).
- Subtitle content is sent to the API provider you configured — that's the
  whole point of the app. If you need full privacy, point it at a local
  model (Ollama, LM Studio) via `http://localhost:11434/v1`.

## Development

```bash
pip install -e .[dev]
pytest                 # unit tests (no network)
ruff check src tests
```

### Build the .exe

```bash
pip install pyinstaller
pyinstaller srtforge.spec
# → dist/SRTForge/SRTForge.exe
```

## Roadmap

- Anthropic-native endpoint (alongside OpenAI-compatible)
- ASS/SSA output, VTT passthrough
- Glossary / term-guard per file
- In-app subtitle editor

## License

MIT — see [LICENSE](LICENSE).
