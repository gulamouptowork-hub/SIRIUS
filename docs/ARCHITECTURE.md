# Architecture

## Overview

```
                 ┌────────────────────────────────────────────────┐
 Telegram ──────▶│                                                │
                 │                Orchestrator                    │──▶ LLM Provider
 REST API ──────▶│  (memory recall → system prompt → tool loop)   │    (Anthropic | Ollama)
                 └───────┬────────┬────────┬────────┬────────┬────┘
                         │        │        │        │        │
                    MemoryAgent TaskAgent NotesAgent StudyAgent KnowledgeAgent
                         │        │        │        │        │
                 ┌───────▼────────▼────────▼────────▼────────▼────┐
                 │  Services:  MemoryManager · TaskService ·      │
                 │  NoteService · StudyService · KnowledgeBase    │
                 └───────┬───────────────────────────┬────────────┘
                         │                           │
                     SQLite/PostgreSQL           ChromaDB
                  (source of truth, history)  (semantic search)
                         │
                     APScheduler (persistent jobs → Telegram reminders)
```

## Layers

| Layer | Location | Responsibility |
|---|---|---|
| Interfaces | `telegram/`, `api/` | Transport only — no business logic |
| Orchestrator | `agents/orchestrator.py` | Memory recall, prompt assembly, tool routing, history |
| Agents | `agents/*` | One capability each; contribute tools + prompt hints |
| Services | `memory/`, `tasks/`, `notes/`, `study/`, `knowledge/` | Business logic, persistence |
| Infrastructure | `db/`, `llm/`, `utils/` | SQL, vectors, LLM providers, crypto |
| Composition root | `app.py` | Builds and wires everything once per process |

Dependencies point strictly downward. Interfaces never touch the DB directly;
agents never talk to the LLM; services know nothing about Telegram.

## The three memory tiers

1. **Working memory** — the last N conversation turns (`chat_messages` table),
   replayed to the LLM on every request.
2. **Temporary memory** — `kind="temporary"` memories (shopping lists, one-off notes).
3. **Permanent memory** — `kind="permanent"` memories (goals, preferences, profile).

Before every answer the orchestrator runs a semantic search over memories and
injects the top hits into the system prompt, so Sirius "just knows" your context.
The LLM can also call memory tools explicitly (`remember_memory`, `forget_memory`,
`update_memory`, `search_memories`).

**Storage split:** SQL is the source of truth (with per-update `memory_versions`
for audit/rollback); ChromaDB mirrors non-sensitive memories for semantic search.
Sensitive memories are Fernet-encrypted at rest and deliberately **not** indexed
in the vector store — indexing would persist plaintext embeddings.

## The learning system

Learning is implemented as memory + study tracking, not fine-tuning:

- Preferences and corrections → stored as permanent memories, recalled automatically.
- Study sessions → logged per topic (`study_sessions`); the StudyAgent surfaces
  totals, recent sessions and past mistakes so the LLM tutors progressively.

## Multi-agent design

Each agent implements the `Agent` interface (`tools()`, `execute()`, `system_hint()`).
The orchestrator merges all tools into one LLM call — the model itself is the router.
This is deliberately simpler than agent-to-agent messaging: one context window, no
handoff loss, and adding a capability = registering one class.

| Agent | Responsibility |
|---|---|
| MemoryAgent | remember / forget / update / search / list memories |
| TaskAgent | tasks, reminders, recurrence |
| NotesAgent | notes and notebooks |
| StudyAgent | study logging and progress |
| KnowledgeAgent | semantic search over ingested documents |
| ResearchAgent | web search (DuckDuckGo) and web page reading |
| UtilityAgent | exact calculator (AST whitelist) and Python execution (isolated subprocess, timeout, user file workspace) |
| FilesAgent | uploaded CSV/Excel workspace: list and preview |

Planned (Phase 8+): GitHub/Gmail/Calendar integrations (need OAuth), AutomationAgent.

## LLM providers

`llm/base.py` defines a minimal contract: `complete()` and `run_with_tools()`.
Each provider runs its **own native tool loop**, so provider-specific message
formats never leak into the rest of the codebase.

- **AnthropicProvider** — Claude (`claude-opus-4-8`) with adaptive thinking and
  streaming; handles `tool_use`, `pause_turn`, and `refusal` stop reasons.
- **OllamaProvider** — any local model with tool support (llama3.1, qwen2.5, …)
  via `/api/chat`. 100% free and offline.
- **OpenAICompatProvider** (`LLM_PROVIDER=nvidia`) — any OpenAI-compatible
  `/chat/completions` endpoint with function calling. Configured for NVIDIA NIM
  (free hosted tier; retries 429/5xx with backoff since the free tier throttles),
  and reusable as-is for Groq, Together, OpenRouter, LM Studio, etc.
- **RouterProvider** (`LLM_PROVIDER=router`) — routes each request to a
  specialized model by task type:

  ```
  Usuário → Router ─┬─ código   → Qwen      (ROUTER_CODE_MODEL)
                    ├─ pesquisa → DeepSeek  (ROUTER_RESEARCH_MODEL, thinking)
                    └─ conversa → Mistral   (ROUTER_CHAT_MODEL, fast path)
  ```

  Classification is a zero-latency keyword/pattern heuristic (pt + en) on the
  latest user message; ambiguous messages fall through to the fast chat model.
  Measured on NVIDIA's free tier: chat ~1s, code ~4s, research ~18s — versus
  ~25s for everything on a single reasoning model.

## Key design decisions

| Decision | Rationale |
|---|---|
| SQLite default, PostgreSQL via `DATABASE_URL` | Zero-config for personal use; SQLAlchemy makes the swap a config change |
| ChromaDB with built-in local embeddings | Free, offline, no torch install; swap `embedding_function` to upgrade |
| APScheduler + SQL job store | Reminders survive restarts without Redis/Celery |
| The LLM is the intent router (tool use) | More robust than regex/keyword routing; zero routing code to maintain |
| Sync services + `asyncio.to_thread` at the edges | Simple, testable core; async only where the frameworks require it |
| API-key header auth instead of JWT | Single-user system; JWT adds complexity without benefit (revisit if multi-user) |
| Volatile prompt parts (memories, time) last | Keeps the stable persona prefix cache-friendly for Anthropic prompt caching |

## Security

- Sensitive memories encrypted with Fernet (`ENCRYPTION_KEY`)
- Telegram chat-id allowlist (`TELEGRAM_ALLOWED_CHAT_IDS`)
- REST API protected by `X-API-Key`
- Append-only audit log (`data/logs/audit.log`) for every memory mutation/export
- Memory versioning (`memory_versions`) — nothing is silently overwritten
- Backups: JSON snapshots in `data/backups/` via API or `memory.backup()`
