# Roadmap

## ✅ Phase 1 — Core chatbot
Pluggable LLM providers (Ollama free/local, Anthropic Claude), persona system
prompt, conversation history, REST `/chat`.

## ✅ Phase 2 — Persistent memory
Permanent/temporary memories, semantic recall (ChromaDB), versioning, encryption
for sensitive entries, export/backup/restore, audit log.

## ✅ Phase 3 — Telegram bot
Chat, task commands, memory listing, PDF ingestion, chat-id allowlist,
reminder delivery.

## ✅ Phase 4 — Knowledge base (v1)
Text/PDF ingestion, chunking, semantic search, source citations.
Next: URL/article ingestion, ingestion from conversations.

## ✅ Phase 5 — Task manager
Priorities, due dates, today/overdue views, recurring reminders with a
persistent scheduler.

## ✅ Phase 6 — Learning system (v1)
Study session tracking, per-topic progress, tutoring guided by history.
Next: spaced-repetition flashcards, mistake review queue.

## ✅ Phase 7 — AI agents & tools
Agent abstraction + orchestrator with 8 agents (Memory, Task, Notes, Study,
Knowledge, Research, Utility, Files). Tools: web search (DuckDuckGo),
web page reading, calculator, Python execution, CSV/Excel upload + analysis,
PDF/Word/text ingestion. Memory dashboard on Telegram
(`/memory`, `/remember`, `/forget`, `/export`).
Next: GitHub (PAT), Gmail/Calendar (OAuth), report generation.

## 🔜 Phase 8 — Automation
- Morning briefing & evening review (scheduled orchestrator runs → Telegram)
- Habit tracking with streaks
- Weekly summaries of tasks/study/notes
- Auto-promotion of repeated temporary memories to permanent

## 🔜 Phase 9 — Voice assistant
- Voice message transcription with local Whisper (faster-whisper, free)
- Optional TTS replies (Piper, free)

## 🔮 Phase 10 — Future upgrades
- Web dashboard (Next.js) with a progress/productivity view
- Vision: image understanding through the Anthropic provider
- Plugin system: third-party agents discovered via entry points
- Prometheus/Grafana metrics; Alembic migrations
- Multi-user support with per-user encryption keys
