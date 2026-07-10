# Deployment

Sirius is two long-running processes sharing one data volume:

1. **bot** — the Telegram interface (`python -m sirius.telegram.bot`), which also
   runs the reminder scheduler.
2. **api** — the optional REST API (`uvicorn sirius.main:app`).

## Docker Compose (recommended)

```bash
copy .env.example .env   # edit values
docker compose up -d --build
docker compose logs -f bot
```

The `ollama` service in `docker-compose.yml` gives you a free local LLM:

```bash
docker compose exec ollama ollama pull llama3.1
# in .env: LLM_PROVIDER=ollama, OLLAMA_BASE_URL=http://ollama:11434
```

## Free cloud hosting

The bot uses long polling — no public URL or webhook needed, so any small
always-on container works.

### Railway / Render / Fly.io

1. Push the repo to GitHub.
2. Create a service from the Dockerfile.
3. Override the start command for the bot service: `python -m sirius.telegram.bot`.
4. Set env vars from `.env.example`.
5. Attach a persistent volume mounted at `/app/data` (memories, DB, backups live there).

Notes:
- Free tiers sleep on inactivity on some platforms — a slept bot misses reminders.
  Fly.io machines with `min_machines_running = 1` or Railway's hobby plan avoid this.
- Running Ollama in the cloud needs more RAM than free tiers offer; for cloud
  deployments the Anthropic provider (or a small paid VM for Ollama) is more practical.
- PostgreSQL: set `DATABASE_URL=postgresql+psycopg://...` and add `psycopg[binary]`
  to dependencies. Supabase's free Postgres works.

## Backups

Everything lives under `data/`:
- `data/sirius.db` — relational data
- `data/chroma/` — vector index (rebuildable from SQL if lost)
- `data/backups/` — JSON memory snapshots (`POST /memories/backup`)

Back up the whole `data/` directory, or schedule `POST /memories/backup` via cron.

## Monitoring

- `GET /health` for uptime checks (UptimeRobot free tier works).
- Logs: `data/logs/sirius.log` (app) and `data/logs/audit.log` (memory mutations).
- Prometheus/Grafana are intentionally deferred until there's something worth
  graphing (Phase 10) — for a single-user assistant, logs + health checks suffice.
