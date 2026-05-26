"""SQLAlchemy Task model."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    # Column name "datetime" per spec; Python attr avoids shadowing datetime type
    scheduled_at: Mapped[dt.datetime] = mapped_column("datetime", DateTime, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    @property
    def datetime(self) -> dt.datetime:
        """Alias for scheduled_at (matches API/schema field name)."""
        return self.scheduled_at

    @datetime.setter
    def datetime(self, value: dt.datetime) -> None:
        self.scheduled_at = value

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "datetime": self.scheduled_at.isoformat(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
