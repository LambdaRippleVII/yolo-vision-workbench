"""定义任务类型、状态转换规则和基础任务数据结构。"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class TaskType(str, Enum):
    """枚举应用支持的推理和导出任务类型。"""

    IMAGE = "image"
    FOLDER = "folder"
    VIDEO = "video"
    STREAM = "stream"
    PIPELINE = "pipeline"
    EXPORT = "export"


class TaskStatus(str, Enum):
    """枚举任务生命周期中的有效状态。"""

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    FAILED = "failed"


# 定义任务状态之间允许发生的迁移关系。
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
    """表示任务状态转换不符合生命周期规则。"""

    pass


def _now() -> str:
    """返回 ISO 8601 格式的当前 UTC 时间。

    Returns:
        当前 UTC 时间的 ISO 8601 字符串。
    """

    return datetime.now(timezone.utc).isoformat()


@dataclass
class Task:
    """保存任务输入、执行状态、进度和结果引用。"""

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
        """查询任务状态迁移表，判断目标状态是否有效。

        Args:
            to: 需要迁移到的任务目标状态。

        Returns:
            目标状态是否在当前状态允许的迁移集合中。
        """

        return to in _ALLOWED[self.status]

    def transition(self, to: TaskStatus, error: str | None = None) -> None:
        """应用有效状态迁移并同步任务错误与结束时间。

        Args:
            to: 需要迁移到的任务目标状态。
            error: 需要记录或返回的错误描述。

        Raises:
            TaskStateError: 目标状态不允许从当前状态迁移时抛出。
        """

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
        """记录任务取消请求供运行线程在安全点处理。"""

        self.cancel_requested = True

    def to_dict(self) -> dict[str, Any]:
        """返回包含任务状态和进度详情的可序列化字典。

        Returns:
            含状态、进度、参数和结果引用的可序列化任务字典。
        """

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
