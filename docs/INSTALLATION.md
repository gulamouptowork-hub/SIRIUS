# Installation

## Requirements

- Python 3.11+ (3.12 recommended)
- ~1 GB disk (ChromaDB downloads a small local embedding model on first use)
- Optional: [Ollama](https://ollama.com) for a free local LLM
- Optional: Docker + Docker Compose

## 1. Clone and install

```bash
git clone <your-repo> sirius
cd sirius
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate
pip install -e ".[dev]"
```

## 2. Configure

```bash
copy .env.example .env    # cp on Linux/macOS
```

Edit `.env`:

| Variable | Notes |
|---|---|
| `LLM_PROVIDER` | `nvidia` (free hosted), `ollama` (free local), or `anthropic` |
| `NVIDIA_API_KEY` | From https://build.nvidia.com (if using NVIDIA) |
| `NVIDIA_MODEL` | e.g. `deepseek-ai/deepseek-v4-flash`, `meta/llama-3.3-70b-instruct` |
| `ANTHROPIC_API_KEY` | From https://platform.claude.com (if using Anthropic) |
| `OLLAMA_MODEL` | Any tool-capable model, e.g. `llama3.1`, `qwen2.5` |
| `TELEGRAM_BOT_TOKEN` | From @BotFather |
| `TELEGRAM_ALLOWED_CHAT_IDS` | Your chat id (send `/id` to the bot to find it) |
| `ENCRYPTION_KEY` | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `SIRIUS_API_KEY` | Any secret string, protects the REST API |
| `TIMEZONE` | e.g. `Asia/Taipei` |

## 3. Free LLM setup (Ollama)

```bash
# install from https://ollama.com, then:
ollama pull llama3.1
```

Keep `LLM_PROVIDER=ollama` in `.env`. Done — no API keys, no cost.

## 4. Telegram bot setup

1. Open Telegram, message **@BotFather** → `/newbot` → follow prompts.
2. Paste the token into `TELEGRAM_BOT_TOKEN`.
3. Start the bot (below), send it `/id`, and put that number into
   `TELEGRAM_ALLOWED_CHAT_IDS` so only you can use it.

## 5. Run

```bash
python -m sirius.telegram.bot     # Telegram interface (includes reminder scheduler)
python -m sirius.main             # REST API on http://localhost:8000 (docs at /docs)
```

## 6. Verify

```bash
pytest -q          # test suite
ruff check .       # lint
curl http://localhost:8000/health
```

## Troubleshooting

- **First message is slow** — ChromaDB downloads its embedding model (~80 MB) once.
- **Reminders not arriving** — the scheduler runs inside the bot/API process;
  make sure one of them is running, and `TELEGRAM_BOT_TOKEN` is set.
- **`Encrypted content found but ENCRYPTION_KEY is not set`** — you removed or
  changed the key after storing sensitive memories. Restore the original key.
- **Ollama connection refused** — check `ollama serve` is running and
  `OLLAMA_BASE_URL` matches (inside Docker Compose use `http://ollama:11434`).
