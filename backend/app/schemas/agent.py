"""Structured LLM action schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


ActionType = Literal[
    "create_task",
    "read_tasks",
    "update_task",
    "delete_task",
    "ask_followup",
    "confirm_delete",
    "clarify",
    "noop",
]


class AgentAction(BaseModel):
    """Structured output from the conversation LLM."""

    action: ActionType
    title: str | None = None
    datetime: datetime | str | None = None
    task_id: int | None = None
    task_ids: list[int] | None = None
    tasks: list[dict[str, Any]] | None = Field(
        default=None,
        description="Batch create: [{title, datetime}, ...]",
    )
    filter_date: str | None = Field(default=None, description="today | tomorrow | YYYY-MM-DD")
    filter_time_of_day: str | None = Field(
        default=None, description="morning | afternoon | evening | tonight"
    )
    response_text: str = Field(description="Natural spoken response for the user")
    pending_delete_task_id: int | None = None
    reference_hint: str | None = Field(
        default=None, description="Semantic hint e.g. 'evening workout', 'second one'"
    )
