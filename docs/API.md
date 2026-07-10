# REST API

Base URL: `http://localhost:8000`. Interactive docs: `/docs` (Swagger) and `/redoc`.

**Auth:** if `SIRIUS_API_KEY` is set, send it on every request:
`X-API-Key: <your key>`.

## Chat

| Method | Path | Body |
|---|---|---|
| POST | `/chat` | `{"user_id": "default", "message": "Remind me tomorrow at 9 to ..."}` → `{"reply": "..."}` |

The chat endpoint goes through the full orchestrator: memory recall, tool use,
history persistence — identical behavior to Telegram.

## Memories

| Method | Path | Notes |
|---|---|---|
| POST | `/memories` | `{content, kind, tags, sensitive, user_id}` |
| GET | `/memories?user_id=&kind=` | list all |
| GET | `/memories/search?query=&user_id=&limit=` | semantic search |
| PATCH | `/memories/{id}` | `{new_content}` (creates a version) |
| DELETE | `/memories/{id}` | forget |
| GET | `/memories/export?user_id=` | full JSON export |
| POST | `/memories/backup?user_id=` | write snapshot to `data/backups/` |
| POST | `/memories/restore` | `{user_id, memories: [...]}` |

## Tasks

| Method | Path | Notes |
|---|---|---|
| POST | `/tasks` | `{title, due_at?, priority?, recurrence?, telegram_chat_id?}` |
| GET | `/tasks?scope=pending\|today\|overdue` | list |
| POST | `/tasks/{id}/complete` | mark done |
| POST | `/tasks/{id}/cancel` | cancel |

## Notes

| Method | Path |
|---|---|
| POST | `/notes` |
| GET | `/notes/search?query=` |
| PATCH | `/notes/{id}` |

## Knowledge base

| Method | Path | Notes |
|---|---|---|
| POST | `/knowledge/ingest` | `{source, text}` → chunked + indexed |
| GET | `/knowledge/search?query=` | semantic search with sources |

## Health

`GET /health` → `{"status": "ok", "version": "..."}`
