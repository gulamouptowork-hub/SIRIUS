"""Production entrypoint: API + Telegram bot + scheduler in one process.

    python -m sirius.run

Startup sequence (all automatic):
  1. load .env and validate mandatory variables (fail fast)
  2. initialize database and ChromaDB
  3. build the LLM provider and agents
  4. start the reminder scheduler
  5. start the FastAPI server
  6. start the Telegram bot (if a token is configured)

This is what the Docker container runs. For development you can still run
`python -m sirius.telegram.bot` or `python -m sirius.main` separately.
"""

from __future__ import annotations

import asyncio

import uvicorn
from loguru import logger

from sirius import runtime  # noqa: F401  (records process start time)
from sirius.app import get_app
from sirius.config import get_settings, validate_settings
from sirius.main import create_api
from sirius.tasks.scheduler import start_scheduler


async def _serve() -> None:
    settings = get_settings()
    validate_settings(settings)

    app = get_app()  # builds DB, ChromaDB, agents, LLM provider
    start_scheduler()

    server = uvicorn.Server(
        uvicorn.Config(create_api(), host=settings.host, port=settings.port, log_config=None)
    )
    api_task = asyncio.create_task(server.serve())
    logger.info("API listening on {}:{}", settings.host, settings.port)

    telegram_app = None
    if settings.telegram_bot_token:
        from sirius.telegram.bot import build_application

        telegram_app = build_application(app)
        await telegram_app.initialize()
        await telegram_app.start()
        await telegram_app.updater.start_polling()
        logger.info("Telegram bot polling started")
    else:
        logger.warning("TELEGRAM_BOT_TOKEN not set — running API only")

    # uvicorn owns SIGINT/SIGTERM; when it exits, tear the bot down gracefully.
    try:
        await api_task
    finally:
        if telegram_app is not None:
            await telegram_app.updater.stop()
            await telegram_app.stop()
            await telegram_app.shutdown()
            logger.info("Telegram bot stopped")


def main() -> None:
    asyncio.run(_serve())


if __name__ == "__main__":
    main()
