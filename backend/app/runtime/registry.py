"""按后端类型注册并创建推理运行时。"""

from __future__ import annotations

from typing import Callable

from app.inference.base import BackendType, BaseRuntime


class RuntimeRegistry:
    """把后端类型映射到运行时构造函数。"""

    def __init__(self) -> None:
        """初始化RuntimeRegistry实例并准备运行所需状态。"""

        self._factories: dict[BackendType, Callable[[], BaseRuntime]] = {}

    def register(self, backend_type: BackendType, factory: Callable[[], BaseRuntime]) -> None:
        """把指定后端类型和构造函数加入运行时注册表。

        Args:
            backend_type: 推理后端类型。
            factory: 根据配置创建运行时实例的工厂函数。
        """

        self._factories[backend_type] = factory

    def create(self, backend_type: BackendType) -> BaseRuntime:
        """根据后端类型创建已注册的推理运行时。

        Args:
            backend_type: 推理后端类型。

        Returns:
            新建的推理运行时实例。

        Raises:
            KeyError: backend_type 尚未注册时抛出。
        """

        factory = self._factories.get(backend_type)
        if factory is None:
            raise KeyError(f"runtime not registered: {backend_type}")
        return factory()

    def supported(self) -> list[str]:
        """返回已注册的推理后端类型。

        Returns:
            已注册后端的字符串标识列表。
        """

        return [bt.value for bt in self._factories]


# 进程内共享的推理后端注册表。
registry = RuntimeRegistry()


def _register_builtin() -> None:
    """注册应用内置的模拟与 YOLO 推理后端。"""

    from app.inference.mock_runtime import MockRuntime
    from app.inference.yolo_runtime import YOLORuntime

    registry.register(BackendType.YOLO, lambda: YOLORuntime())
    registry.register(BackendType.MOCK, lambda: MockRuntime())


_register_builtin()
