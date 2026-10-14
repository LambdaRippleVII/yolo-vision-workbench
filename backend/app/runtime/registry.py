"""Runtime registry and factory."""

from __future__ import annotations

from typing import Callable

from app.inference.base import BackendType, BaseRuntime


class RuntimeRegistry:
    def __init__(self) -> None:
        self._factories: dict[BackendType, Callable[[], BaseRuntime]] = {}

    def register(self, backend_type: BackendType, factory: Callable[[], BaseRuntime]) -> None:
        self._factories[backend_type] = factory

    def create(self, backend_type: BackendType) -> BaseRuntime:
        factory = self._factories.get(backend_type)
        if factory is None:
            raise KeyError(f"runtime not registered: {backend_type}")
        return factory()

    def supported(self) -> list[str]:
        return [bt.value for bt in self._factories]


registry = RuntimeRegistry()


def _register_builtin() -> None:
    from app.inference.mock_runtime import MockRuntime
    from app.inference.yolo_runtime import YOLORuntime

    registry.register(BackendType.YOLO, lambda: YOLORuntime())
    registry.register(BackendType.MOCK, lambda: MockRuntime())


_register_builtin()
