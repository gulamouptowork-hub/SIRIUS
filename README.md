# ✨ Sirius — Your Personal AI Assistant

Sirius is a personal AI assistant, second brain, memory manager, learning companion,
and productivity coach. It runs on **free and open-source technology**, remembers
what matters, learns from you, and lives where you already are: **Telegram**.

```
You:    Remember that I prefer Python over Java.
Sirius: Got it — stored permanently. I'll keep that in mind for future code examples.

You:    Remind me tomorrow at 9 to submit the report.
Sirius: Done. I'll ping you tomorrow at 09:00. 🔔

You:    What do you remember about me?
Sirius: You prefer Python over Java, you're studying data analysis, and ...
```

## Features (today)

- 🧠 **Long-term memory** — permanent & temporary memories, semantic recall before
  every answer, versioning, encryption for sensitive entries, export/backup/restore,
  and a Telegram dashboard (`/memory`, `/remember`, `/forget`, `/export`)
- 💬 **Telegram control center** — chat, tasks, reminders, file ingestion
- 🛠️ **Tools** — web search (DuckDuckGo, no key), web page reading, exact calculator,
  Python execution, CSV/Excel analysis, PDF/Word/text ingestion
- ✅ **Task manager** — priorities, due dates, recurring reminders (persisted across restarts)
- 📝 **Notes & notebooks** — create, search, tag, organize
- 📚 **Knowledge base** — ingest PDFs and articles, semantic search, cited answers
- 🎓 **Study assistant** — tracks what you study and tutors you better over time
- 🤖 **Multi-agent architecture** — Memory, Task, Notes, Study, and Knowledge agents
  behind one orchestrator; every component is replaceable
- 🔌 **Pluggable LLMs** — free local models via **Ollama**, free hosted models via
  **NVIDIA NIM** (build.nvidia.com), or **Claude** via the Anthropic API.
  Swap with one env var.
- 🧭 **Model router** — code → Qwen, research → DeepSeek (thinking), casual chat →
  Mistral (fast path): every request gets the best model for the job.
- 🌐 **REST API** — everything is also scriptable over HTTP (FastAPI, OpenAPI docs at `/docs`)

## Quick start

```bash
git clone <your-repo> sirius && cd sirius
python -m venv .venv && .venv/Scripts/activate   # Windows (use bin/activate on Linux/macOS)
pip install -e ".[dev]"
copy .env.example .env                            # then edit .env
```

1. **Pick an LLM**:
   - Free hosted: get a key at [build.nvidia.com](https://build.nvidia.com), set
     `LLM_PROVIDER=nvidia` + `NVIDIA_API_KEY` (default model: DeepSeek V4 Flash).
   - Free local: install [Ollama](https://ollama.com), run `ollama pull llama3.1`,
     set `LLM_PROVIDER=ollama`.
   - Best quality: `LLM_PROVIDER=anthropic` + `ANTHROPIC_API_KEY`.
2. **Create a Telegram bot**: message [@BotFather](https://t.me/BotFather) → `/newbot`
   → paste the token into `TELEGRAM_BOT_TOKEN`.
3. **Run**:

```bash
python -m sirius.telegram.bot     # the Telegram interface
python -m sirius.main             # (optional) the REST API on :8000
```

Or run everything (API + bot + scheduler) in one process: `python -m sirius.run`.

## Production (Docker, 24/7)

One container runs the API, the Telegram bot, and the reminder scheduler:

```bash
cp .env.example .env      # fill in your keys
docker compose build      # multi-stage build, non-root user
docker compose up -d      # starts with restart: unless-stopped
docker compose logs -f    # follow logs
docker compose down       # stop
```

- **Health**: `GET /health` (local checks — used by the Docker HEALTHCHECK) and
  `GET /status` (live Telegram + NVIDIA probes). Uptime included in both.
- **Persistence**: everything lives in the `sirius-data` volume (SQLite, ChromaDB,
  uploaded files, backups, logs) — survives rebuilds, restarts, and reboots.
- **Fail-fast**: the container exits immediately with a clear message if mandatory
  env vars are missing (e.g. `NVIDIA_API_KEY` with `LLM_PROVIDER=router`).
- **Security**: non-root user, read-only root filesystem, secrets only via `.env`.

**Update to the latest version:**

```bash
git pull
docker compose build
docker compose up -d
```

**Backup** (memories + database + files):

```bash
docker compose exec sirius python -c "from sirius.app import get_app; print(get_app().memory.backup('SEU_CHAT_ID'))"
docker run --rm -v sirius_sirius-data:/data -v .:/backup alpine tar czf /backup/sirius-data.tgz /data
```

**Restore**: copy the tarball back into the volume the same way (`tar xzf`), or use
`POST /memories/restore` with an exported JSON.

**Optional services** (isolated in the same Docker network):
`docker compose --profile postgres up -d` (PostgreSQL), `--profile redis`,
`--profile ollama` (free local LLM).

**Troubleshooting:**
- Container restarting → `docker compose logs sirius`; a config error prints the
  exact missing variable.
- Bot silent → check `GET /status` for the live Telegram check; confirm only ONE
  instance is polling (Telegram allows a single `getUpdates` per token).
- Slow first reply → ChromaDB downloads its embedding model once (cached in the
  `sirius-cache` volume).
- NVIDIA 503s → free-tier throttling; Sirius retries with backoff automatically.

## Documentation

| Doc | What's inside |
|---|---|
| [docs/INSTALLATION.md](docs/INSTALLATION.md) | Full setup guide (Windows/Linux/Docker) |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design, agents, data flow, design decisions |
| [docs/DATABASE.md](docs/DATABASE.md) | Schema reference |
| [docs/API.md](docs/API.md) | REST API reference |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Docker, Railway/Render/Fly.io |
| [docs/ROADMAP.md](docs/ROADMAP.md) | The 10-phase development plan |
| [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) | Dev workflow, style, testing |

## Tests

```bash
pytest -q
ruff check .
```

## License

MIT
