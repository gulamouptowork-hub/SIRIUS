from __future__ import annotations

import sys

from loguru import logger

from sirius.config import Settings

_configured = False


def setup_logging(settings: Settings) -> None:
    """Console + rotating file logs, plus a separate append-only audit log."""
    global _configured
    if _configured:
        return
    _configured = True

    logger.remove()
    logger.add(sys.stderr, level="INFO")
    logger.add(
        settings.log_dir / "sirius.log",
        level="DEBUG",
        rotation="10 MB",
        retention="30 days",
        enqueue=True,
    )
    logger.add(
        settings.log_dir / "audit.log",
        level="INFO",
        rotation="10 MB",
        retention="365 days",
        enqueue=True,
        filter=lambda record: record["extra"].get("audit") is True,
    )


def audit(event: str, **fields: object) -> None:
    """Write a structured entry to the audit log (memory changes, deletions, exports)."""
    logger.bind(audit=True).info("{} | {}", event, fields)
