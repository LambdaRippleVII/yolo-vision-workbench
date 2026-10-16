"""创建后端虚拟环境并安装项目依赖。"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

# 后端仓库目录的绝对路径。
ROOT = Path(__file__).resolve().parent
# 后端虚拟环境目录。
VENV = ROOT / ".venv"
# 用于离线安装的 Python wheel 文件目录。
WHEELS = ROOT / "wheels"
# 保存不同运行环境依赖清单的目录。
REQ_DIR = ROOT / "requirements"


def python_in_venv() -> Path:
    """返回当前平台对应的虚拟环境 Python 可执行文件路径。

    Returns:
        返回当前平台下虚拟环境中的 Python 可执行文件路径。
    """

    if os.name == "nt":
        return VENV / "Scripts" / "python.exe"
    return VENV / "bin" / "python"


def run(cmd: list[str]) -> None:
    """执行环境安装命令，并在失败时中止后续步骤。

    Args:
        cmd: 要执行的虚拟环境或 pip 命令及其参数。
    """

    print("+", " ".join(cmd))
    subprocess.check_call(cmd, cwd=ROOT)


def main() -> int:
    """检查依赖清单并准备后端虚拟环境。

    Returns:
        返回安装流程的退出码；成功时为 0，依赖清单或安装失败时为 1。
    """

    parser = argparse.ArgumentParser(description="Setup YOLO Vision Workbench backend env")
    parser.add_argument(
        "--requirements",
        nargs="+",
        default=["base"],
        help="requirement file names without .txt (default: base)",
    )
    args = parser.parse_args()

    if not VENV.exists():
        run([sys.executable, "-m", "venv", str(VENV)])

    py = str(python_in_venv())
    run([py, "-m", "pip", "install", "--upgrade", "pip"])

    for name in args.requirements:
        req = REQ_DIR / f"{name}.txt"
        if not req.exists():
            print(f"missing requirements file: {req}")
            return 1
        cmd = [py, "-m", "pip", "install", "-r", str(req)]
        if WHEELS.exists() and any(WHEELS.iterdir()):
            cmd.extend(["--no-index", "--find-links", str(WHEELS)])
            print("using local wheels (no-index)")
        # 优先使用本地 wheel；缺包导致离线安装失败时再回退到网络源。
        try:
            run(cmd)
        except subprocess.CalledProcessError:
            if "--no-index" in cmd:
                print("local wheels incomplete, falling back to network install")
                run([py, "-m", "pip", "install", "-r", str(req)])
            else:
                return 1

    print("backend env ready:", py)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
