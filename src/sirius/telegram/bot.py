from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from loguru import logger
from telegram import BotCommand, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from sirius.app import SiriusApp, get_app
from sirius.tasks.scheduler import start_scheduler

# Registered with Telegram on startup so the "/" menu shows them automatically.
BOT_COMMANDS = [
    ("memory", "Painel de memória (ou /memory <busca>)"),
    ("remember", "Gravar uma memória permanente"),
    ("forget", "Apagar memória (id ou busca)"),
    ("export", "Baixar todas as memórias em JSON"),
    ("tasks", "Tarefas de hoje"),
    ("overdue", "Tarefas atrasadas"),
    ("id", "Mostrar seu chat id"),
    ("help", "Ajuda"),
]

HELP_TEXT = """I'm Sirius — your personal AI assistant. Just talk to me naturally:

• "Remember that I prefer Python over Java."
• "Remind me tomorrow at 9 to submit the report."
• "Search the web for today's TSMC stock price."
• "Quiz me on SQL joins."
• Send me a PDF/Word file (→ knowledge base) or CSV/Excel (→ data analysis).

Memory dashboard:
/memory — overview of everything I remember
/memory <search> — search memories
/remember <text> — store a permanent memory
/forget <id or search> — delete a memory
/export — download all memories as JSON
(to edit, just tell me: "update my memory about X to ...")

Tasks:
/tasks — today's tasks
/overdue — overdue tasks

Other:
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

    # ── memory dashboard ─────────────────────────────────────

    async def memory_dashboard(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._guard(update):
            return
        user_id = _user_id(update)
        query = " ".join(context.args or [])
        if query:
            hits = await asyncio.to_thread(self._app.memory.search, user_id, query, 8)
            if not hits:
                await update.message.reply_text("No memories matched that search.")
                return
            lines = [f"• [{m['kind']}] {m['content']}\n  id: {m['id']}" for m in hits]
            await update.message.reply_text("🔎 Matching memories:\n\n" + "\n".join(lines))
            return

        items = self._app.memory.list_all(user_id)
        permanent = sum(1 for m in items if m["kind"] == "permanent")
        temporary = len(items) - permanent
        lines = [
            "🧠 Memory dashboard",
            f"Permanent: {permanent} | Temporary: {temporary}",
        ]
        if items:
            lines.append("\nMost recent:")
            lines.extend(f"• [{m['kind']}] {m['content']}" for m in items[:8])
        lines.append(
            "\n/memory <search> · /remember <text> · /forget <id or search> · /export"
        )
        await update.message.reply_text("\n".join(lines))

    async def remember_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._guard(update):
            return
        text = " ".join(context.args or [])
        if not text:
            await update.message.reply_text("Usage: /remember <what I should remember>")
            return
        record = self._app.memory.remember(_user_id(update), text, kind="permanent")
        await update.message.reply_text(f"🧠 Remembered permanently (id: {record.id}).")

    async def forget_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._guard(update):
            return
        arg = " ".join(context.args or [])
        if not arg:
            await update.message.reply_text("Usage: /forget <memory id or search text>")
            return
        if len(arg) == 32 and all(c in "0123456789abcdef" for c in arg):
            if self._app.memory.forget(arg):
                await update.message.reply_text("🗑️ Forgotten.")
            else:
                await update.message.reply_text("No memory with that id.")
            return
        hits = await asyncio.to_thread(self._app.memory.search, _user_id(update), arg, 5)
        if not hits:
            await update.message.reply_text("No memories matched that search.")
            return
        lines = [f"• {m['content']}\n  /forget {m['id']}" for m in hits]
        await update.message.reply_text(
            "Found these — tap the /forget line of the one to delete:\n\n" + "\n".join(lines)
        )

    async def export_cmd(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._guard(update):
            return
        path = await asyncio.to_thread(self._app.memory.backup, _user_id(update))
        with open(path, "rb") as f:
            await update.message.reply_document(
                f, filename=Path(path).name, caption="📦 All your memories, as JSON."
            )

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
        name = doc.file_name
        suffix = Path(name).suffix.lower()
        user_id = _user_id(update)

        if suffix in (".csv", ".xlsx", ".xlsm", ".xls"):
            tg_file = await context.bot.get_file(doc.file_id)
            content = bytes(await tg_file.download_as_bytearray())
            await asyncio.to_thread(self._app.files.save, user_id, name, content)
            await update.message.reply_text(
                f"📊 Saved '{name}' to your workspace. "
                "Ask me anything about it — I can preview and analyze it with Python."
            )
            return

        if suffix in (".pdf", ".docx", ".txt", ".md"):
            await update.message.reply_text(f"Reading '{name}'…")
            tg_file = await context.bot.get_file(doc.file_id)
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / name
                await tg_file.download_to_drive(str(path))
                if suffix == ".pdf":
                    chunks = await asyncio.to_thread(
                        self._app.knowledge.ingest_pdf, user_id, path, name
                    )
                else:
                    if suffix == ".docx":
                        from sirius.files.service import extract_docx_text

                        text = await asyncio.to_thread(extract_docx_text, path)
                    else:
                        text = path.read_text(encoding="utf-8", errors="replace")
                    chunks = await asyncio.to_thread(
                        self._app.knowledge.ingest_text, user_id, name, text
                    )
            await update.message.reply_text(
                f"📚 Added '{name}' to your knowledge base ({chunks} chunks). "
                "Ask me anything about it!"
            )
            return

        await update.message.reply_text(
            "Supported files: PDF/Word/text → knowledge base; CSV/Excel → data analysis."
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

    async def _register_commands(application: Application) -> None:
        await application.bot.set_my_commands(
            [BotCommand(name, description) for name, description in BOT_COMMANDS]
        )
        logger.info("Registered {} bot commands with Telegram", len(BOT_COMMANDS))

    application = Application.builder().token(token).post_init(_register_commands).build()
    application.add_handler(CommandHandler("start", bot.start))
    application.add_handler(CommandHandler("help", bot.help))
    application.add_handler(CommandHandler("id", bot.chat_id))
    application.add_handler(CommandHandler("tasks", bot.tasks_today))
    application.add_handler(CommandHandler("overdue", bot.tasks_overdue))
    application.add_handler(CommandHandler("memory", bot.memory_dashboard))
    application.add_handler(CommandHandler("memories", bot.memory_dashboard))
    application.add_handler(CommandHandler("remember", bot.remember_cmd))
    application.add_handler(CommandHandler("forget", bot.forget_cmd))
    application.add_handler(CommandHandler("export", bot.export_cmd))
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
