from __future__ import annotations

import json

from sirius.agents.base import Agent, AgentContext
from sirius.llm.base import ToolSpec
from sirius.notes.service import NoteService


class NotesAgent(Agent):
    """Owns notes and notebooks (the second-brain text layer)."""

    name = "notes"

    def __init__(self, notes: NoteService) -> None:
        self._notes = notes

    def tools(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                "create_note",
                "Create a note. Optionally place it in a notebook and tag it.",
                {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "content": {"type": "string"},
                        "notebook": {"type": "string"},
                        "tags": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["title", "content"],
                },
            ),
            ToolSpec(
                "search_notes",
                "Search notes by keyword across title, content, and tags.",
                {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
            ),
            ToolSpec(
                "update_note",
                "Update a note's title and/or content (find its id via search_notes).",
                {
                    "type": "object",
                    "properties": {
                        "note_id": {"type": "string"},
                        "title": {"type": "string"},
                        "content": {"type": "string"},
                    },
                    "required": ["note_id"],
                },
            ),
            ToolSpec(
                "list_notebooks",
                "List the user's notebooks.",
                {"type": "object", "properties": {}},
            ),
        ]

    def execute(self, tool_name: str, args: dict, ctx: AgentContext) -> str:
        if tool_name == "create_note":
            note = self._notes.create(
                ctx.user_id,
                args["title"],
                args["content"],
                notebook=args.get("notebook"),
                tags=args.get("tags"),
            )
            return f"Note created (id={note.id})."
        if tool_name == "search_notes":
            notes = self._notes.search(ctx.user_id, args["query"])
            if not notes:
                return "No notes found."
            return json.dumps(
                [
                    {"id": n.id, "title": n.title, "content": n.content[:500], "tags": n.tags}
                    for n in notes
                ]
            )
        if tool_name == "update_note":
            self._notes.update(args["note_id"], args.get("title"), args.get("content"))
            return "Note updated."
        if tool_name == "list_notebooks":
            books = self._notes.list_notebooks(ctx.user_id)
            return json.dumps([b.name for b in books]) if books else "No notebooks yet."
        raise ValueError(f"Unknown tool: {tool_name}")
