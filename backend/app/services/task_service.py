"""Task CRUD operations backed by SQLAlchemy."""

from __future__ import annotations

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task

# Default timezone for relative date parsing (user-local can be extended)
DEFAULT_TZ = ZoneInfo("UTC")


def _start_of_day(dt: datetime) -> datetime:
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


def _time_of_day_bounds(time_of_day: str, base_date: datetime) -> tuple[datetime, datetime]:
    """Map morning/evening/etc. to hour ranges on base_date."""
    day = _start_of_day(base_date)
    ranges = {
        "morning": (time(5, 0), time(11, 59)),
        "afternoon": (time(12, 0), time(16, 59)),
        "evening": (time(17, 0), time(20, 59)),
        "tonight": (time(21, 0), time(23, 59)),
    }
    start_t, end_t = ranges.get(time_of_day.lower(), (time(0, 0), time(23, 59)))
    start = day.replace(hour=start_t.hour, minute=start_t.minute)
    end = day.replace(hour=end_t.hour, minute=end_t.minute, second=59)
    return start, end


def resolve_date_filter(
    filter_date: str | None,
    now: datetime | None = None,
) -> tuple[datetime | None, datetime | None]:
    """Convert today/tomorrow into datetime bounds."""
    now = now or datetime.now(DEFAULT_TZ)
    if not filter_date:
        return None, None
    fd = filter_date.lower().strip()
    today = _start_of_day(now)
    if fd == "today":
        return today, today + timedelta(days=1) - timedelta(seconds=1)
    if fd == "tomorrow":
        start = today + timedelta(days=1)
        return start, start + timedelta(days=1) - timedelta(seconds=1)
    # ISO date
    try:
        parsed = datetime.fromisoformat(fd.replace("Z", "+00:00"))
        start = _start_of_day(parsed)
        return start, start + timedelta(days=1) - timedelta(seconds=1)
    except ValueError:
        return None, None


class TaskService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, title: str, dt: datetime) -> Task:
        task = Task(title=title.strip(), scheduled_at=dt)
        self.session.add(task)
        await self.session.commit()
        await self.session.refresh(task)
        return task

    async def create_many(self, items: list[dict]) -> list[Task]:
        tasks = []
        for item in items:
            dt = item["datetime"]
            if isinstance(dt, str):
                dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
            tasks.append(Task(title=item["title"].strip(), scheduled_at=dt))
        self.session.add_all(tasks)
        await self.session.commit()
        for t in tasks:
            await self.session.refresh(t)
        return tasks

    async def get_by_id(self, task_id: int) -> Task | None:
        result = await self.session.execute(select(Task).where(Task.id == task_id))
        return result.scalar_one_or_none()

    async def list_tasks(
        self,
        date_start: datetime | None = None,
        date_end: datetime | None = None,
        time_of_day: str | None = None,
        now: datetime | None = None,
    ) -> list[Task]:
        now = now or datetime.now(DEFAULT_TZ)
        query = select(Task).order_by(Task.scheduled_at.asc())
        conditions = []

        if date_start and date_end:
            conditions.append(and_(Task.scheduled_at >= date_start, Task.scheduled_at <= date_end))
        elif date_start:
            conditions.append(Task.scheduled_at >= date_start)

        if time_of_day:
            # If we have a day filter, use that day; else use today
            base = date_start or _start_of_day(now)
            t_start, t_end = _time_of_day_bounds(time_of_day, base)
            conditions.append(and_(Task.scheduled_at >= t_start, Task.scheduled_at <= t_end))

        if conditions:
            query = query.where(and_(*conditions))

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def list_all(self) -> list[Task]:
        result = await self.session.execute(select(Task).order_by(Task.scheduled_at.asc()))
        return list(result.scalars().all())

    async def update(
        self,
        task_id: int,
        title: str | None = None,
        dt: datetime | None = None,
    ) -> Task | None:
        task = await self.get_by_id(task_id)
        if not task:
            return None
        if title is not None:
            task.title = title.strip()
        if dt is not None:
            task.datetime = dt
        await self.session.commit()
        await self.session.refresh(task)
        return task

    async def delete(self, task_id: int) -> bool:
        task = await self.get_by_id(task_id)
        if not task:
            return False
        await self.session.delete(task)
        await self.session.commit()
        return True

    async def search_by_hint(self, hint: str, limit: int = 10) -> list[Task]:
        """Simple title/time search for semantic fallback."""
        all_tasks = await self.list_all()
        hint_lower = hint.lower()
        scored: list[tuple[int, Task]] = []
        for t in all_tasks:
            score = 0
            if hint_lower in t.title.lower():
                score += 10
            for word in hint_lower.split():
                if word in t.title.lower():
                    score += 3
            if score > 0:
                scored.append((score, t))
        scored.sort(key=lambda x: (-x[0], x[1].datetime))
        return [t for _, t in scored[:limit]]
