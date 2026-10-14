"""Task domain models and state machine."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class TaskType(str, Enum):
    IMAGE = "image"
    FOLDER = "folder"
    VIDEO = "video"
    STREAM = "stream"
    PIPELINE = "pipeline"
    EXPORT = "export"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    FAILED = "failed"


_ALLOWED: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.PENDING: {TaskStatus.RUNNING, TaskStatus.CANCELLED, TaskStatus.COMPLETED, TaskStatus.FAILED},
    TaskStatus.RUNNING: {
        TaskStatus.PAUSED,
        TaskStatus.COMPLETED,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.PAUSED: {TaskStatus.RUNNING, TaskStatus.CANCELLED, TaskStatus.COMPLETED, TaskStatus.FAILED},
    TaskStatus.COMPLETED: set(),
    TaskStatus.FAILED: set(),
    TaskStatus.CANCELLED: set(),
}


class TaskStateError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Task:
    type: TaskType
    params: dict[str, Any]
    task_id: str = field(default_factory=lambda: f"t_{uuid.uuid4().hex[:12]}")
    status: TaskStatus = TaskStatus.PENDING
    progress: float = 0.0
    progress_detail: dict[str, Any] = field(default_factory=dict)
    profile_id: str | None = None
    model_ids: list[str] = field(default_factory=list)
    session_id: str | None = None
    project_id: str | None = None
    error: str | None = None
    result_ref: str | None = None
    parent_task_id: str | None = None
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    finished_at: str | None = None
    cancel_requested: bool = False

    def can_transition(self, to: TaskStatus) -> bool:
        return to in _ALLOWED[self.status]

    def transition(self, to: TaskStatus, error: str | None = None) -> None:
        if to != self.status and not self.can_transition(to):
            raise TaskStateError(f"illegal transition {self.status} -> {to}")
        self.status = to
        self.updated_at = _now()
        if error is not None:
            self.error = error
        if to in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
            self.finished_at = _now()
            if to == TaskStatus.COMPLETED:
                self.progress = 1.0

    def request_cancel(self) -> None:
        self.cancel_requested = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "type": self.type.value,
            "status": self.status.value,
            "progress": self.progress,
            "progress_detail": self.progress_detail,
            "params": self.params,
            "profile_id": self.profile_id,
            "model_ids": list(self.model_ids),
            "session_id": self.session_id,
            "project_id": self.project_id,
            "error": self.error,
            "result_ref": self.result_ref,
            "parent_task_id": self.parent_task_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "finished_at": self.finished_at,
        }
