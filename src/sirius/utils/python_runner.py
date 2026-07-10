from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_MAX_OUTPUT = 4000


def run_python(code: str, workdir: Path, timeout: int = 20) -> str:
    """Run a Python snippet in a separate isolated interpreter process.

    Runs with `-I` (isolated mode), a hard timeout, and cwd pinned to the
    user's file workspace so scripts can read uploaded CSV/Excel files.
    Note: this executes on the host — Sirius is a single-user personal
    assistant protected by the Telegram allowlist; do not expose it publicly.
    """
    workdir.mkdir(parents=True, exist_ok=True)
    try:
        result = subprocess.run(
            [sys.executable, "-I", "-c", code],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=workdir,
        )
    except subprocess.TimeoutExpired:
        return f"Error: execution exceeded {timeout}s and was killed."
    output = (result.stdout or "") + (("\n" + result.stderr) if result.stderr else "")
    output = output.strip() or "(no output)"
    if len(output) > _MAX_OUTPUT:
        output = output[:_MAX_OUTPUT] + "\n[... truncated]"
    return output
