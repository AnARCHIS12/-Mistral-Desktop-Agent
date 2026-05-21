from __future__ import annotations

from typing import Any, Optional, TYPE_CHECKING

from config import Settings

if TYPE_CHECKING:
    from agent.loop import AgentLoop


class TelegramIntegration:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.agent: Optional["AgentLoop"] = None
        self.application = None
        self.chat_ids: set[int] = set()

    async def start(self, agent: "AgentLoop") -> None:
        self.agent = agent
        if not self.settings.enable_telegram or not self.settings.telegram_bot_token:
            return
        from telegram import Update
        from telegram.ext import Application, CommandHandler, ContextTypes

        async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
            self._remember_chat(update)
            if not self.agent or not self.agent.goal:
                await update.message.reply_text("Definis d'abord un objectif avec /goal <texte>.")
                return
            await self.agent.start()
            await update.message.reply_text("Agent demarre.")

        async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
            self._remember_chat(update)
            if self.agent:
                await self.agent.stop()
            await update.message.reply_text("Agent arrete.")

        async def cmd_goal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
            self._remember_chat(update)
            goal = " ".join(context.args).strip()
            if not goal:
                await update.message.reply_text("Usage: /goal <objectif>")
                return
            if self.agent:
                await self.agent.set_goal(goal)
            await update.message.reply_text(f"Objectif defini: {goal}")

        async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
            self._remember_chat(update)
            status = self.agent.status() if self.agent else {"running": False}
            await update.message.reply_text(
                f"running={status.get('running')} progress={status.get('progress')} goal={status.get('goal')}"
            )

        self.application = Application.builder().token(self.settings.telegram_bot_token).build()
        self.application.add_handler(CommandHandler("start", cmd_start))
        self.application.add_handler(CommandHandler("stop", cmd_stop))
        self.application.add_handler(CommandHandler("goal", cmd_goal))
        self.application.add_handler(CommandHandler("status", cmd_status))
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()

    async def stop(self) -> None:
        if not self.application:
            return
        await self.application.updater.stop()
        await self.application.stop()
        await self.application.shutdown()
        self.application = None

    async def notify(self, event: dict[str, Any]) -> None:
        if not self.application or not self.chat_ids:
            return
        event_type = event.get("type", "event")
        payload = event.get("payload", {})
        if event_type not in {"action", "result", "done", "error", "status"}:
            return
        text = self._format_event(event_type, payload)
        for chat_id in list(self.chat_ids):
            try:
                await self.application.bot.send_message(chat_id=chat_id, text=text[:3900])
            except Exception:
                self.chat_ids.discard(chat_id)

    def _remember_chat(self, update: Any) -> None:
        if update.effective_chat:
            self.chat_ids.add(update.effective_chat.id)

    @staticmethod
    def _format_event(event_type: str, payload: dict[str, Any]) -> str:
        if event_type == "action":
            action = payload.get("action", {})
            return f"Action: {action.get('tool')} {action.get('parameters')} - {action.get('reason', '')}"
        if event_type == "result":
            result = payload.get("result", {})
            return f"Resultat: {'ok' if result.get('ok') else 'error'} {result.get('error', '')}"
        if event_type == "done":
            return "Objectif termine."
        if event_type == "error":
            return f"Erreur: {payload.get('message') or payload.get('error') or payload}"
        status = payload if payload else {}
        return f"Status: running={status.get('running')} progress={status.get('progress')}"
