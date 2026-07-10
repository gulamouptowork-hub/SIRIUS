# Database Schema

Relational store: SQLite by default, PostgreSQL via `DATABASE_URL`.
Vector store: ChromaDB collections `memories` and `knowledge` under `data/chroma/`.

## Tables

### memories
Source of truth for long-term memory.

| Column | Type | Notes |
|---|---|---|
| id | str(32) PK | uuid4 hex |
| user_id | str(64) idx | Telegram chat id or API user id |
| kind | str | `permanent` \| `temporary` |
| content | text | Fernet-encrypted when `sensitive` |
| tags | str | comma-separated |
| sensitive | bool | encrypted + excluded from vector index |
| version | int | incremented on every update |
| created_at / updated_at | datetime | UTC |

### memory_versions
Previous contents of a memory (audit / rollback). One row per update.

### chat_messages
Working memory — conversation history per user (`role`, `content`, `created_at`).

### tasks
| Column | Notes |
|---|---|
| status | `pending` \| `done` \| `cancelled` |
| priority | `high` \| `medium` \| `low` |
| due_at | UTC datetime, nullable |
| recurrence | `""`, `daily HH:MM`, `weekly:mon HH:MM`, `monthly:15 HH:MM`, or raw cron |
| telegram_chat_id | reminder destination |

### notebooks / notes
Notes with optional notebook grouping and comma-separated tags.

### study_sessions
Per-topic study log (`topic`, `minutes`, `notes`) powering the learning system.

### apscheduler_jobs
Created automatically by APScheduler's SQLAlchemy job store — persistent reminders.

## Vector collections

| Collection | Documents | Metadata |
|---|---|---|
| `memories` | non-sensitive memory contents | `user_id`, `kind`, `tags` |
| `knowledge` | document chunks (~1200 chars, 150 overlap) | `user_id`, `source`, `chunk` |

## Migrations

Tables are created with `Base.metadata.create_all()` (fine while the schema is
additive). When the schema starts changing shape, adopt Alembic:
`alembic init`, point `env.py` at `sirius.db.database.Base.metadata`.
