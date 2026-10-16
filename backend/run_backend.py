"""提供启动 FastAPI 后端服务的命令行入口。"""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
# 当前文件位于 backend 目录，父目录即为后端包所在目录。
    """启动 FastAPI 后端服务。"""

    backend_dir = Path(__file__).resolve().parent
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))
    import runpy

    runpy.run_module("app.main", run_name="__main__")


if __name__ == "__main__":
    main()
