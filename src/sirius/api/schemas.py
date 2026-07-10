from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    user_id: str = "default"
    message: str


class ChatResponse(BaseModel):
    reply: str


class MemoryCreate(BaseModel):
    user_id: str = "default"
    content: str
    kind: str = "permanent"
    tags: list[str] = Field(default_factory=list)
    sensitive: bool = False


class MemoryUpdate(BaseModel):
    new_content: str


class MemoryRestore(BaseModel):
    user_id: str = "default"
    memories: list[dict]


class TaskCreate(BaseModel):
    user_id: str = "default"
    title: str
    due_at: datetime | None = None
    priority: str = "medium"
    recurrence: str = ""
    telegram_chat_id: int | None = None


class NoteCreate(BaseModel):
    user_id: str = "default"
    title: str
    content: str
    notebook: str | None = None
    tags: list[str] = Field(default_factory=list)


class NoteUpdate(BaseModel):
    title: str | None = None
    content: str | None = None


class IngestText(BaseModel):
    user_id: str = "default"
    source: str
    text: str
