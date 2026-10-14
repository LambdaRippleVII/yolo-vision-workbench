# YOLO Vision Workbench

专业 AI 视觉工程平台 · 桌面端 YOLO 检测工作台

**Electron + Vue3 + TypeScript** 界面 · **Python FastAPI** 推理后端

---

## 简介

YOLO Vision Workbench 是一款面向中文用户的桌面视觉检测工具：选模型、选图/视频/摄像头，调整参数后出检测框，支持逐帧微调与导出。

- 图片检测（单图 / 文件夹批量，多模型，类别筛选）
- 视频检测（跳帧、框持续，时间轴编辑、导出）
- 摄像头实时（USB / RTSP，可录制后编辑）
- 模型管理（本地 YAML、类别中文映射、按类配色）
- 全中文 UI

## 快速开始

### 环境

- Windows 10/11
- Node.js 18+（构建桌面端）
- Python 3.11+（推荐用 [uv](https://github.com/astral-sh/uv)）

### 1. 安装后端依赖

```powershell
cd backend
uv venv
uv pip install -r requirements/base.txt -r requirements/yolo.txt
```

> 仅演示模型可不装 `yolo.txt`；真实 YOLO 需要 ultralytics + torch。

### 2. 启动桌面应用

```powershell
cd ..\desktop
npm install
npm run dev
```

应用启动后会**自动拉起** Python 后端（默认 `127.0.0.1:8765`）。

### 3. 基本用法

1. 顶栏选 **图片检测 / 视频检测 / 摄像头**
2. 加载模型（如「演示模型」或「COCO YOLOv8n」）
3. 选择图片/文件夹/视频，或拖入 / Ctrl+V
4. 点 **开始推理**，在画布查看结果并导出

## 目录结构

```
YOLO Vision Workbench/
├── desktop/          # Electron + Vue3 + TS 界面
├── backend/          # FastAPI + WebSocket + 推理
├── models/           # 模型 YAML 与权重
├── projects/         # 项目数据（SQLite）
├── docs/             # 架构 / 实现 / UI 设计文档
└── README.md
```

## 功能一览

| 模块 | 说明 |
|------|------|
| 图片检测 | 多模型、类别筛选、标签配置、保存识别图 |
| 视频检测 | 跳帧/框持续、时间轨或缩略胶片、多帧导出、整段导出 |
| 摄像头 | USB/RTSP、录制帧率、录后进编辑器（无需重识别） |
| 模型管理 | 显示名映射、自动/自定义类别颜色 |
| 项目 | 可临时识别或挂项目归档 |

## 技术要点

- 推理：`TaskManager → Pipeline → InferenceSession → BaseRuntime`
- 后端可扩展：YOLO / ONNX / TensorRT / RKNN（接口已预留）
- 存储：项目 SQLite + JSON 导出
- 通信：本机 WebSocket JSON

## 文档

详细设计见 [`docs/`](docs/)：

- `ARCHITECTURE_v0.2.md` 架构
- `IMPLEMENTATION_DESIGN_v0.1.md` 实现设计
- `UI_DESIGN_SPEC.md` / `LOCALIZATION.md` / `IA.md`
- `V1_RELEASE.md` 版本说明

## 许可证

TBD（计划开源，许可证待定）

## 致谢

- [Ultralytics YOLO](https://github.com/ultralytics/ultralytics)
- [Electron](https://www.electronjs.org/) · [Vue](https://vuejs.org/) · [FastAPI](https://fastapi.tiangolo.com/)
