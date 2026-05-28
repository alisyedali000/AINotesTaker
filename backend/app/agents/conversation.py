"""Orchestrates LLM actions against the task database."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.session import SessionState
from app.schemas.agent import AgentAction
from app.services.openai_service import OpenAIService
from app.services.task_service import TaskService, resolve_date_filter

logger = logging.getLogger(__name__)
TZ = ZoneInfo("UTC")


def _parse_dt(value: datetime | str | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _format_task_natural(task: Any) -> str:
    dt = task.datetime
    time_str = dt.strftime("%I:%M %p").lstrip("0")
    return f"{task.title} at {time_str}"


def _format_tasks_conversational(tasks: list) -> str:
    if not tasks:
        return "You don't have any tasks matching that."
    if len(tasks) == 1:
        return f"You have {_format_task_natural(tasks[0])}."
    parts = [_format_task_natural(t) for t in tasks]
    if len(parts) == 2:
        return f"You have {parts[0]} and {parts[1]}."
    return "You have " + ", ".join(parts[:-1]) + f", and {parts[-1]}."


class ConversationOrchestrator:
    def __init__(
        self,
        openai: OpenAIService,
        task_service: TaskService,
        session: SessionState,
    ):
        self.openai = openai
        self.tasks = task_service
        self.session = session

    async def process_user_text(self, user_text: str) -> tuple[str, AgentAction]:
        """Run full turn: reason → execute → return spoken response."""
        if not user_text.strip():
            return (
                "I didn't catch that. Could you repeat?",
                AgentAction(action="clarify", response_text="I didn't catch that. Could you repeat?"),
            )

        self.session.add_message("user", user_text)
        now = datetime.now(TZ)

        recent_tasks_data = await self._load_recent_tasks()
        action = await self.openai.reason(
            user_message=user_text,
            history=self.session.messages,
            recent_tasks=recent_tasks_data,
            pending_delete=self.session.pending_delete_task_id,
            now_iso=now.isoformat(),
        )

        response_text = await self._execute_action(action, now)
        self.session.add_message("assistant", response_text)
        self.session.last_assistant_response = response_text
        return response_text, action

    async def _load_recent_tasks(self) -> list[dict]:
        result = []
        for tid in self.session.recent_task_ids:
            t = await self.tasks.get_by_id(tid)
            if t:
                result.append(t.to_dict())
        return result

    async def _resolve_task_id(self, action: AgentAction) -> int | None:
        if action.task_id:
            return action.task_id
        if action.task_ids and len(action.task_ids) == 1:
            return action.task_ids[0]
        # Semantic hint from LLM
        if action.reference_hint:
            matches = await self.tasks.search_by_hint(action.reference_hint)
            if len(matches) == 1:
                return matches[0].id
            if len(matches) > 1 and action.task_ids:
                idx = action.task_ids[0] - 1 if action.task_ids else 0
                if 0 <= idx < len(matches):
                    return matches[idx].id
        # "second one" etc. from recent list
        if self.session.recent_task_ids:
            hint = (action.reference_hint or "").lower()
            if "second" in hint or "2" in hint:
                if len(self.session.recent_task_ids) >= 2:
                    return self.session.recent_task_ids[1]
            if "first" in hint or "previous" in hint or "last" in hint:
                return self.session.recent_task_ids[0]
        return None

    async def _execute_action(self, action: AgentAction, now: datetime) -> str:
        try:
            if action.action == "create_task":
                return await self._handle_create(action)
            if action.action == "read_tasks":
                return await self._handle_read(action, now)
            if action.action == "update_task":
                return await self._handle_update(action)
            if action.action == "confirm_delete":
                return await self._handle_confirm_delete(action)
            if action.action == "delete_task":
                return await self._handle_delete(action)
            if action.action in ("ask_followup", "clarify", "noop"):
                return action.response_text
            return action.response_text
        except Exception as e:
            logger.exception("Action execution failed: %s", e)
            return "Something went wrong on my end. Could you try that again?"

    async def _handle_create(self, action: AgentAction) -> str:
        created_ids: list[int] = []
        if action.tasks:
            items = []
            for t in action.tasks:
                dt = _parse_dt(t.get("datetime"))
                if dt and t.get("title"):
                    items.append({"title": t["title"], "datetime": dt})
            if items:
                tasks = await self.tasks.create_many(items)
                created_ids = [t.id for t in tasks]
        elif action.title:
            dt = _parse_dt(action.datetime)
            if not dt:
                return "When should I schedule that? Give me a date and time."
            task = await self.tasks.create(action.title, dt)
            created_ids = [task.id]

        if created_ids:
            self.session.track_tasks(created_ids)
            return action.response_text or "Done, I've added that to your schedule."
        return action.response_text or "I need a bit more detail — what's the task and when?"

    async def _handle_read(self, action: AgentAction, now: datetime) -> str:
        date_start, date_end = resolve_date_filter(action.filter_date, now)
        tasks = await self.tasks.list_tasks(
            date_start=date_start,
            date_end=date_end,
            time_of_day=action.filter_time_of_day,
            now=now,
        )
        if not tasks and not action.filter_date:
            tasks = await self.tasks.list_all()

        self.session.track_tasks([t.id for t in tasks])
        formatted = _format_tasks_conversational(tasks)
        if not tasks:
            return action.response_text or formatted
        # Always include the actual task list in voice responses (LLM intro alone is often incomplete)
        intro = (action.response_text or "").strip()
        if intro and intro not in formatted:
            return f"{intro.rstrip('.')}. {formatted}"
        return formatted

    async def _handle_update(self, action: AgentAction) -> str:
        task_id = await self._resolve_task_id(action)
        if not task_id:
            return action.response_text or "Which task did you mean? I couldn't quite tell."

        dt = _parse_dt(action.datetime)
        title = action.title
        updated = await self.tasks.update(task_id, title=title, dt=dt)
        if not updated:
            return "I couldn't find that task to update."
        self.session.track_tasks([task_id])
        return action.response_text or f"Got it, I've updated {updated.title}."

    async def _handle_confirm_delete(self, action: AgentAction) -> str:
        task_id = action.pending_delete_task_id or await self._resolve_task_id(action)
        if not task_id:
            return action.response_text or "Which task should I remove?"
        task = await self.tasks.get_by_id(task_id)
        if not task:
            return "I couldn't find that task."
        self.session.pending_delete_task_id = task_id
        self.session.track_tasks([task_id])
        return action.response_text or (
            f"Do you want me to delete {task.title} "
            f"scheduled for {task.datetime.strftime('%I:%M %p').lstrip('0')}?"
        )

    async def _handle_delete(self, action: AgentAction) -> str:
        task_id = action.task_id or self.session.pending_delete_task_id
        if not task_id:
            task_id = await self._resolve_task_id(action)
        if not task_id:
            return "Which task should I delete?"

        task = await self.tasks.get_by_id(task_id)
        if not task:
            self.session.clear_pending_delete()
            return "That task doesn't seem to exist anymore."

        # Require pending confirmation unless user message was clearly confirmatory
        if self.session.pending_delete_task_id != task_id:
            self.session.pending_delete_task_id = task_id
            return (
                f"Just to confirm — should I delete {task.title} "
                f"at {task.datetime.strftime('%I:%M %p').lstrip('0')}?"
            )

        ok = await self.tasks.delete(task_id)
        self.session.clear_pending_delete()
        if ok:
            return action.response_text or f"Alright, I've removed {task.title}."
        return "I couldn't delete that task."
