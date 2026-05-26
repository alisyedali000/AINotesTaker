"""Pydantic schemas for tasks."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class TaskCreate(BaseModel):
    title: str
    datetime: datetime


class TaskUpdate(BaseModel):
    title: str | None = None
    datetime: datetime | None = None


class TaskResponse(BaseModel):
    id: int
    title: str
    datetime: datetime
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class TaskFilter(BaseModel):
    """Optional filters for read_tasks queries."""

    date_start: datetime | None = None
    date_end: datetime | None = None
    time_of_day: str | None = Field(
        default=None,
        description="morning | afternoon | evening | tonight",
    )
