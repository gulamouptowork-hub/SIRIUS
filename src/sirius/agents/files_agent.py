from __future__ import annotations

import json

from sirius.agents.base import Agent, AgentContext
from sirius.files.service import FileService
from sirius.llm.base import ToolSpec


class FilesAgent(Agent):
    """Owns the user's uploaded file workspace (CSV, Excel, text)."""

    name = "files"

    def __init__(self, files: FileService) -> None:
        self._files = files

    def system_hint(self) -> str:
        return (
            "Files: the user can upload CSV/Excel files via Telegram. Use list_files to see "
            "them and preview_file to inspect structure; use run_python for real analysis."
        )

    def tools(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                "list_files",
                "List the user's uploaded files (name and size).",
                {"type": "object", "properties": {}},
            ),
            ToolSpec(
                "preview_file",
                "Show the first rows of an uploaded CSV/Excel file (or head of a text file).",
                {
                    "type": "object",
                    "properties": {"filename": {"type": "string"}},
                    "required": ["filename"],
                },
            ),
        ]

    def execute(self, tool_name: str, args: dict, ctx: AgentContext) -> str:
        if tool_name == "list_files":
            files = self._files.list_files(ctx.user_id)
            return json.dumps(files) if files else "No files uploaded yet."
        if tool_name == "preview_file":
            return self._files.preview(ctx.user_id, args["filename"])
        raise ValueError(f"Unknown tool: {tool_name}")
