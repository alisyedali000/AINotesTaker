"""In-memory per-WebSocket session state."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class SessionState:
    """Lightweight conversation memory for one voice session."""

    session_id: str
    messages: list[dict[str, str]] = field(default_factory=list)
    recent_task_ids: list[int] = field(default_factory=list)
    pending_delete_task_id: int | None = None
    last_assistant_response: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)

    def add_message(self, role: str, content: str) -> None:
        self.messages.append({"role": role, "content": content})
        # Keep last 20 turns
        if len(self.messages) > 40:
            self.messages = self.messages[-40:]

    def track_tasks(self, task_ids: list[int]) -> None:
        for tid in reversed(task_ids):
            if tid in self.recent_task_ids:
                self.recent_task_ids.remove(tid)
            self.recent_task_ids.insert(0, tid)
        self.recent_task_ids = self.recent_task_ids[:10]

    def clear_pending_delete(self) -> None:
        self.pending_delete_task_id = None


# Global session store keyed by websocket id
_sessions: dict[str, SessionState] = {}


def get_session(session_id: str) -> SessionState:
    if session_id not in _sessions:
        _sessions[session_id] = SessionState(session_id=session_id)
    return _sessions[session_id]


def remove_session(session_id: str) -> None:
    _sessions.pop(session_id, None)
