from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from loguru import logger
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from sirius.app import SiriusApp, get_app
from sirius.tasks.scheduler import start_scheduler

HELP_TEXT = """I'm Sirius — your personal AI assistant. Just talk to me naturally:

• "Remember that I prefer Python over Java."
• "Remind me tomorrow at 9 to submit the report."
• "What do you remember about me?"
• "Quiz me on SQL joins."
• "Create a note: ideas for my thesis..."
• Send me a PDF and I'll add it to your knowledge base.

Commands:
/tasks — today's tasks
/overdue — overdue tasks
/memories — everything I remember
/id — show your chat id
/help — this message"""


def _user_id(update: Update) -> str:
    return str(update.effective_chat.id)


class SiriusBot:
    def __init__(self, app: SiriusApp) -> None:
        self._app = app
        self._allowed = app.settings.allowed_chat_ids

    def _authorized(self, update: Update) -> bool:
        if not self._allowed:
            return True
        return update.effective_chat.id in self._allowed

    async def _guard(self, update: Update) -> bool:
        if self._authorized(update):
            return True
        await update.message.reply_text(
            "Sorry, this Sirius instance is private. "
            f"Ask the owner to allow chat id {update.effective_chat.id}."
        )
        return False

    # ── commands ─────────────────────────────────────────────

    async def start(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text("Hello, I'm Sirius. ✨\n\n" + HELP_TEXT)

    async def help(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text(HELP_TEXT)

    async def chat_id(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text(f"Your chat id: {update.effective_chat.id}")

    async def tasks_today(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._guard(update):
            return
        tasks = self._app.tasks.list_today(_user_id(update))
        await update.message.reply_text(_format_tasks(tasks, "No tasks due today. 🎉"))

    async def tasks_overdue(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._guard(update):
            return
        tasks = self._app.tasks.list_overdue(_user_id(update))
        await update.message.reply_text(_format_tasks(tasks, "Nothing overdue. ✅"))

    async def memories(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._guard(update):
            return
        items = self._app.memory.list_all(_user_id(update))
        if not items:
            await update.message.reply_text("I don't have any memories about you yet.")
            return
        lines = [f"• [{m['kind']}] {m['content']}" for m in items[:50]]
        await update.message.reply_text("Here's what I remember:\n" + "\n".join(lines))

    # ── messages ─────────────────────────────────────────────

    async def text_message(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._guard(update):
            return
        await update.effective_chat.send_action("typing")
        try:
            reply = await asyncio.to_thread(
                self._app.orchestrator.handle,
                _user_id(update),
                update.message.text,
                update.effective_chat.id,
            )
        except Exception:
            logger.exception("Chat handling failed")
            reply = "Something went wrong on my side. Please try again."
        await update.message.reply_text(reply or "…")

    async def document(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._guard(update):
            return
        doc = update.message.document
        if not doc.file_name.lower().endswith(".pdf"):
            await update.message.reply_text("For now I can only ingest PDF documents.")
            return
        await update.message.reply_text("Reading your PDF…")
        tg_file = await context.bot.get_file(doc.file_id)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / doc.file_name
            await tg_file.download_to_drive(str(path))
            chunks = await asyncio.to_thread(
                self._app.knowledge.ingest_pdf, _user_id(update), path, doc.file_name
            )
        await update.message.reply_text(
            f"Added '{doc.file_name}' to your knowledge base ({chunks} chunks). "
            "Ask me anything about it!"
        )

    async def voice(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text(
            "Voice messages are on the roadmap (Phase 9 — local Whisper transcription). "
            "Please type your message for now."
        )

    async def photo(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text(
            "Image understanding arrives with the vision-capable provider setup. "
            "For now, please describe the image in text."
        )


def build_application(app: SiriusApp) -> Application:
    token = app.settings.telegram_bot_token
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set (see .env.example).")
    bot = SiriusBot(app)
    application = Application.builder().token(token).build()
    application.add_handler(CommandHandler("start", bot.start))
    application.add_handler(CommandHandler("help", bot.help))
    application.add_handler(CommandHandler("id", bot.chat_id))
    application.add_handler(CommandHandler("tasks", bot.tasks_today))
    application.add_handler(CommandHandler("overdue", bot.tasks_overdue))
    application.add_handler(CommandHandler("memories", bot.memories))
    application.add_handler(MessageHandler(filters.Document.ALL, bot.document))
    application.add_handler(MessageHandler(filters.VOICE, bot.voice))
    application.add_handler(MessageHandler(filters.PHOTO, bot.photo))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.text_message))
    return application


def _format_tasks(tasks, empty_message: str) -> str:
    if not tasks:
        return empty_message
    icons = {"high": "🔴", "medium": "🟡", "low": "🟢"}
    lines = []
    for t in tasks:
        due = f" — {t.due_at:%Y-%m-%d %H:%M}" if t.due_at else ""
        lines.append(f"{icons.get(t.priority, '•')} {t.title}{due}")
    return "\n".join(lines)


def main() -> None:
    app = get_app()
    start_scheduler()  # reminders fire from the bot process
    application = build_application(app)
    logger.info("Sirius Telegram bot starting (long polling)…")
    application.run_polling()


if __name__ == "__main__":
    main()
