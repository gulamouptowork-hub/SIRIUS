from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile
from loguru import logger

from sirius import __version__
from sirius.api import schemas
from sirius.api.deps import app_dep, require_api_key
from sirius.app import SiriusApp
from sirius.runtime import uptime_seconds

router = APIRouter(dependencies=[Depends(require_api_key)])


# ── system ───────────────────────────────────────────────────


@router.get("/")
def root() -> dict:
    return {
        "name": "Sirius",
        "version": __version__,
        "docs": "/docs",
        "health": "/health",
        "status": "/status",
    }


@router.get("/version")
def version() -> dict:
    return {"name": "Sirius", "version": __version__}


def _component_checks(app: SiriusApp) -> dict[str, str]:
    """Fast local checks (no external network) — safe for Docker healthchecks."""
    checks: dict[str, str] = {}
    try:
        app.db.ping()
        checks["database"] = "ok"
    except Exception as exc:
        logger.error("Health check: database failed: {}", exc)
        checks["database"] = f"error: {exc}"
    try:
        count = app.memory.heartbeat()
        checks["vector_store"] = f"ok ({count} memories indexed)"
    except Exception as exc:
        logger.error("Health check: vector store failed: {}", exc)
        checks["vector_store"] = f"error: {exc}"
    checks["telegram"] = (
        "configured" if app.settings.telegram_bot_token else "not configured"
    )
    checks["llm"] = f"configured ({app.settings.llm_provider})"
    return checks


@router.get("/health")
def health(response: Response, app: SiriusApp = Depends(app_dep)) -> dict:
    """Local health: database, vector store, uptime. Used by Docker HEALTHCHECK."""
    checks = _component_checks(app)
    healthy = all(not v.startswith("error") for v in checks.values())
    if not healthy:
        response.status_code = 503
    return {
        "status": "ok" if healthy else "degraded",
        "version": __version__,
        "uptime_seconds": uptime_seconds(),
        "components": checks,
    }


@router.get("/status")
def status(app: SiriusApp = Depends(app_dep)) -> dict:
    """Deep status: everything in /health plus LIVE external checks
    (Telegram getMe, NVIDIA /models). Slower and rate-limited upstream —
    call it manually, not from automated probes."""
    result = {
        "status": "ok",
        "version": __version__,
        "uptime_seconds": uptime_seconds(),
        "components": _component_checks(app),
        "external": {},
    }
    settings = app.settings
    if settings.telegram_bot_token:
        try:
            r = httpx.get(
                f"https://api.telegram.org/bot{settings.telegram_bot_token}/getMe", timeout=15
            )
            username = r.json().get("result", {}).get("username")
            result["external"]["telegram"] = (
                f"ok (@{username})" if r.status_code == 200 else f"error: HTTP {r.status_code}"
            )
        except Exception as exc:
            result["external"]["telegram"] = f"error: {exc}"
    if settings.llm_provider in ("nvidia", "router"):
        try:
            r = httpx.get(
                f"{settings.nvidia_base_url.rstrip('/')}/models",
                headers={"Authorization": f"Bearer {settings.nvidia_api_key}"},
                timeout=20,
            )
            result["external"]["nvidia"] = (
                f"ok ({len(r.json().get('data', []))} models)"
                if r.status_code == 200
                else f"error: HTTP {r.status_code}"
            )
        except Exception as exc:
            result["external"]["nvidia"] = f"error: {exc}"
    if any(str(v).startswith("error") for v in result["external"].values()):
        result["status"] = "degraded"
    return result


# ── chat ─────────────────────────────────────────────────────


@router.post("/chat", response_model=schemas.ChatResponse)
def chat(body: schemas.ChatRequest, app: SiriusApp = Depends(app_dep)) -> schemas.ChatResponse:
    # Sync endpoint on purpose: FastAPI runs it in a worker thread, keeping the
    # event loop free while the LLM call blocks.
    reply = app.orchestrator.handle(body.user_id, body.message)
    return schemas.ChatResponse(reply=reply)


# ── memories ─────────────────────────────────────────────────


@router.post("/memories")
def create_memory(body: schemas.MemoryCreate, app: SiriusApp = Depends(app_dep)) -> dict:
    record = app.memory.remember(
        body.user_id, body.content, kind=body.kind, tags=body.tags, sensitive=body.sensitive
    )
    return {"id": record.id}


@router.get("/memories")
def list_memories(
    user_id: str = "default", kind: str | None = None, app: SiriusApp = Depends(app_dep)
) -> list[dict]:
    return app.memory.list_all(user_id, kind=kind)


@router.get("/memories/search")
def search_memories(
    query: str, user_id: str = "default", limit: int = 5, app: SiriusApp = Depends(app_dep)
) -> list[dict]:
    return app.memory.search(user_id, query, limit=limit)


@router.patch("/memories/{memory_id}")
def update_memory(
    memory_id: str, body: schemas.MemoryUpdate, app: SiriusApp = Depends(app_dep)
) -> dict:
    try:
        app.memory.update(memory_id, body.new_content)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": "updated"}


@router.delete("/memories/{memory_id}")
def forget_memory(memory_id: str, app: SiriusApp = Depends(app_dep)) -> dict:
    if not app.memory.forget(memory_id):
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"status": "forgotten"}


@router.get("/memories/export")
def export_memories(user_id: str = "default", app: SiriusApp = Depends(app_dep)) -> list[dict]:
    return app.memory.export_all(user_id)


@router.post("/memories/backup")
def backup_memories(user_id: str = "default", app: SiriusApp = Depends(app_dep)) -> dict:
    return {"path": app.memory.backup(user_id)}


@router.post("/memories/restore")
def restore_memories(body: schemas.MemoryRestore, app: SiriusApp = Depends(app_dep)) -> dict:
    return {"restored": app.memory.restore(body.user_id, body.memories)}


# Convenience aliases mirroring the Telegram commands.


@router.post("/remember")
def remember(body: schemas.MemoryCreate, app: SiriusApp = Depends(app_dep)) -> dict:
    record = app.memory.remember(
        body.user_id, body.content, kind=body.kind, tags=body.tags, sensitive=body.sensitive
    )
    return {"id": record.id, "kind": record.kind}


@router.post("/forget")
def forget(body: schemas.MemoryForget, app: SiriusApp = Depends(app_dep)) -> dict:
    if not app.memory.forget(body.memory_id):
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"status": "forgotten"}


# ── uploads ──────────────────────────────────────────────────


@router.post("/upload")
async def upload(
    file: UploadFile, user_id: str = "default", app: SiriusApp = Depends(app_dep)
) -> dict:
    """Route uploads like Telegram does: PDF/Word/text → knowledge base,
    CSV/Excel → the user's file workspace for analysis."""
    import asyncio
    import tempfile
    from pathlib import Path

    name = file.filename or "upload.bin"
    suffix = Path(name).suffix.lower()
    content = await file.read()

    if suffix in (".csv", ".xlsx", ".xlsm", ".xls"):
        await asyncio.to_thread(app.files.save, user_id, name, content)
        return {"destination": "files", "filename": name}

    if suffix in (".pdf", ".docx", ".txt", ".md"):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / Path(name).name
            path.write_bytes(content)
            if suffix == ".pdf":
                chunks = await asyncio.to_thread(app.knowledge.ingest_pdf, user_id, path, name)
            elif suffix == ".docx":
                from sirius.files.service import extract_docx_text

                text = await asyncio.to_thread(extract_docx_text, path)
                chunks = await asyncio.to_thread(app.knowledge.ingest_text, user_id, name, text)
            else:
                text = path.read_text(encoding="utf-8", errors="replace")
                chunks = await asyncio.to_thread(app.knowledge.ingest_text, user_id, name, text)
        return {"destination": "knowledge_base", "filename": name, "chunks": chunks}

    raise HTTPException(
        status_code=422,
        detail="Supported: .pdf/.docx/.txt/.md (knowledge base), .csv/.xlsx (analysis)",
    )


# ── tasks ────────────────────────────────────────────────────


@router.post("/tasks")
def create_task(body: schemas.TaskCreate, app: SiriusApp = Depends(app_dep)) -> dict:
    task = app.tasks.create(
        body.user_id,
        body.title,
        due_at=body.due_at,
        priority=body.priority,
        recurrence=body.recurrence,
        telegram_chat_id=body.telegram_chat_id,
    )
    return {"id": task.id}


@router.get("/tasks")
def list_tasks(
    user_id: str = "default", scope: str = "pending", app: SiriusApp = Depends(app_dep)
) -> list[dict]:
    fn = {
        "pending": app.tasks.list_pending,
        "today": app.tasks.list_today,
        "overdue": app.tasks.list_overdue,
    }.get(scope)
    if fn is None:
        raise HTTPException(status_code=422, detail="scope must be pending|today|overdue")
    return [
        {
            "id": t.id,
            "title": t.title,
            "status": t.status,
            "priority": t.priority,
            "due_at": t.due_at.isoformat() if t.due_at else None,
            "recurrence": t.recurrence,
        }
        for t in fn(user_id)
    ]


@router.post("/tasks/{task_id}/complete")
def complete_task(task_id: str, app: SiriusApp = Depends(app_dep)) -> dict:
    try:
        app.tasks.complete(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": "done"}


@router.post("/tasks/{task_id}/cancel")
def cancel_task(task_id: str, app: SiriusApp = Depends(app_dep)) -> dict:
    try:
        app.tasks.cancel(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": "cancelled"}


# ── notes ────────────────────────────────────────────────────


@router.post("/notes")
def create_note(body: schemas.NoteCreate, app: SiriusApp = Depends(app_dep)) -> dict:
    note = app.notes.create(
        body.user_id, body.title, body.content, notebook=body.notebook, tags=body.tags
    )
    return {"id": note.id}


@router.get("/notes/search")
def search_notes(
    query: str, user_id: str = "default", app: SiriusApp = Depends(app_dep)
) -> list[dict]:
    return [
        {"id": n.id, "title": n.title, "content": n.content, "tags": n.tags}
        for n in app.notes.search(user_id, query)
    ]


@router.patch("/notes/{note_id}")
def update_note(note_id: str, body: schemas.NoteUpdate, app: SiriusApp = Depends(app_dep)) -> dict:
    try:
        app.notes.update(note_id, body.title, body.content)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": "updated"}


# ── knowledge ────────────────────────────────────────────────


@router.post("/knowledge/ingest")
def ingest_text(body: schemas.IngestText, app: SiriusApp = Depends(app_dep)) -> dict:
    return {"chunks": app.knowledge.ingest_text(body.user_id, body.source, body.text)}


@router.get("/knowledge/search")
def search_knowledge(
    query: str, user_id: str = "default", limit: int = 5, app: SiriusApp = Depends(app_dep)
) -> list[dict]:
    return app.knowledge.search(user_id, query, limit=limit)
