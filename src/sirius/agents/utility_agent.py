from __future__ import annotations

from sirius.agents.base import Agent, AgentContext
from sirius.files.service import FileService
from sirius.llm.base import ToolSpec
from sirius.utils.calculator import calculate
from sirius.utils.python_runner import run_python


class UtilityAgent(Agent):
    """Owns computation: exact math and Python execution over the user's files."""

    name = "utility"

    def __init__(self, files: FileService) -> None:
        self._files = files

    def system_hint(self) -> str:
        return (
            "Computation: never do arithmetic in your head — use calculate for math and "
            "run_python for anything beyond a single expression (data analysis, dates, "
            "conversions). run_python executes in the user's file workspace, so uploaded "
            "CSV/Excel files can be opened by name (openpyxl is available for .xlsx)."
        )

    def tools(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                "calculate",
                "Evaluate an arithmetic expression exactly. Supports +-*/%//**, "
                "sqrt/sin/cos/log/etc., pi and e.",
                {
                    "type": "object",
                    "properties": {"expression": {"type": "string"}},
                    "required": ["expression"],
                },
            ),
            ToolSpec(
                "run_python",
                "Run a short Python script and return its printed output. Executes in the "
                "user's file workspace; print() what you want to see. 20s timeout.",
                {
                    "type": "object",
                    "properties": {"code": {"type": "string"}},
                    "required": ["code"],
                },
            ),
        ]

    def execute(self, tool_name: str, args: dict, ctx: AgentContext) -> str:
        if tool_name == "calculate":
            return str(calculate(args["expression"]))
        if tool_name == "run_python":
            return run_python(args["code"], self._files.workdir(ctx.user_id))
        raise ValueError(f"Unknown tool: {tool_name}")
