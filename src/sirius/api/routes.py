from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from sirius import __version__
from sirius.api import schemas
from sirius.api.deps import app_dep, require_api_key
from sirius.app import SiriusApp

router = APIRouter(dependencies=[Depends(require_api_key)])


# ── health ───────────────────────────────────────────────────


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "version": __version__}


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
