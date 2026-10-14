# YOLO Vision Workbench 架构设计

> 版本：v0.1（设计稿，待确认后进入编码）
> 目标平台：Windows 优先，架构兼容 Linux / ARM / RK3588 / TensorRT / ONNX

---

## 1. 产品定位

YOLO Vision Workbench 是个人使用优先、未来可能开源的**桌面端视觉 AI 推理工作台**。

它不是 Demo，而是长期可扩展的平台，覆盖：

| 能力域 | 第一阶段 | 后续阶段 |
|--------|----------|----------|
| 模型类型 | YOLO Detect | Segment / Pose / OCR / Tracking / SAM |
| 推理后端 | Ultralytics (PyTorch) | ONNX Runtime / TensorRT / RKNN |
| 输入源 | 单图 / 图片文件夹 | 视频文件 / USB Camera / RTSP |
| 结果呈现 | JSON + Canvas 叠加 | 视频时间轴 / 录制 / 操作记录回放 |
| 任务形态 | ImageTask / FolderTask | VideoTask / StreamTask / Pipeline |

---

## 2. 总体架构

```
┌─────────────────────────────────────────────────────────────┐
│  Electron Desktop (UI Only)                                 │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────────┐  │
│  │ views    │ │components│ │ stores   │ │ api / protocol │  │
│  │ 项目/图片 │ │ Konva    │ │ Pinia    │ │ WS Client      │  │
│  │ 视频/相机 │ │ Video.js │ │          │ │                │  │
│  └──────────┘ └──────────┘ └──────────┘ └───────┬────────┘  │
└─────────────────────────────────────────────────│───────────┘
                                                  │ WebSocket
                                                  │ JSON Message
┌─────────────────────────────────────────────────│───────────┐
│  Python Backend Service                         ▼           │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  FastAPI + WebSocket Gateway                         │   │
│  │  main.py / websocket/                                │   │
│  └──────────────────────────────────────────────────────┘   │
│           │                    │                    │        │
│  ┌────────▼──────┐   ┌────────▼──────┐   ┌────────▼──────┐  │
│  │ Task Manager  │   │ Model Manager │   │ Project Store │  │
│  │ Image/Folder  │   │ 扫描/加载/缓存 │   │ project.json  │  │
│  │ Video/Stream  │   │ class 名称    │   │ sqlite        │  │
│  └────────┬──────┘   └────────┬──────┘   └───────────────┘  │
│           │                   │                             │
│  ┌────────▼───────────────────▼──────────────────────────┐  │
│  │  Inference Engine (Pipeline)                          │  │
│  │  多模型并行 / 级联 / Result Merge                      │  │
│  └────────────────────────┬──────────────────────────────┘  │
│                           │                                 │
│  ┌────────────────────────▼──────────────────────────────┐  │
│  │  Runtime Interface (BaseRuntime)                      │  │
│  │  YOLORuntime │ ONNXRuntime │ TensorRTRuntime │ RKNN   │  │
│  └───────────────────────────────────────────────────────┘  │
│                           │                                 │
│                    ┌──────▼──────┐                          │
│                    │ Hardware /  │                          │
│                    │ Runtime SDK │                          │
│                    └─────────────┘                          │
└─────────────────────────────────────────────────────────────┘
```

### 2.1 职责边界（硬约束）

| 层 | 负责 | 禁止 |
|----|------|------|
| Electron | UI、文件选择、交互、图像/视频显示、项目管理界面 | 直接调用 YOLO、推理逻辑、业务状态机 |
| Python Backend | 模型加载、推理、视频/摄像头处理、任务管理、数据保存 | UI 渲染、前端状态 |
| Inference Engine | 多模型编排、结果合并、后处理 | 硬编码具体 Runtime |
| Runtime | 具体推理实现（predict / load / unload） | 上层业务语义 |

**禁止 Electron 直接调用 YOLO。禁止把推理逻辑写入前端。**

---

## 3. 技术栈

### 3.1 Frontend（desktop/）

| 组件 | 选型 | 用途 |
|------|------|------|
| 桌面壳 | Electron | 窗口、文件对话框、进程生命周期 |
| 构建 | Vite + electron-vite（或等价） | 开发热更新 / 生产打包 |
| UI 框架 | Vue 3 + TypeScript | 组件化界面 |
| 状态 | Pinia | 项目、任务、模型、日志状态 |
| 组件库 | Element Plus | 表单、表格、对话框、布局 |
| 画布 | Konva.js | 检测框叠加、交互（高亮/隐藏/选中） |
| 视频 | Video.js | 视频文件播放、时间轴（后续阶段） |
| 通信 | 原生 WebSocket + 类型化协议层 | 与 Python Backend 通信 |

### 3.2 Backend（backend/）

| 组件 | 选型 | 用途 |
|------|------|------|
| 运行时 | Python 3.12 | — |
| 包管理 | uv | 依赖锁定、虚拟环境 |
| Web 框架 | FastAPI | HTTP + WebSocket |
| 校验 | pydantic v2 | 消息 / 配置 / 结果 schema |
| 日志 | loguru | 文件 + WebSocket 推送 |
| 存储 | sqlite（标准库 / aiosqlite） | 项目元数据、任务、结果索引 |
| 视觉 | opencv-python | 读图、读视频、摄像头 |
| 推理 | ultralytics（第一阶段） | YOLO Detect |
| 多媒体 | ffmpeg（可执行或 imageio-ffmpeg） | 视频解码/转码辅助 |
| 配置 | PyYAML | 模型配置、应用配置 |

### 3.3 环境初始化（偏好对齐）

采用 `setup_env.py` + `wheels/` 本地轮子目录模式：

```
backend/
├── setup_env.py          # 一键创建 venv + 安装依赖
├── requirements/
│   ├── base.txt          # FastAPI / pydantic / loguru / pyyaml ...
│   ├── yolo.txt          # ultralytics + torch（第一阶段）
│   ├── onnx.txt          # onnxruntime（后续）
│   ├── tensorrt.txt      # （后续）
│   └── rknn.txt          # （后续）
└── wheels/               # 本地 wheel 缓存（可选，离线安装）
```

不同推理后端使用**独立 requirements**，保证依赖隔离。

---

## 4. 目录结构

```
YOLO-Studio/
├── desktop/
│   ├── electron/                 # Electron 主进程
│   │   ├── main.ts               # 窗口创建、生命周期
│   │   ├── preload.ts            # contextBridge 安全桥
│   │   └── ipc/                  # 原生对话框、路径、窗口控制
│   ├── src/
│   │   ├── views/                # 页面：Home / Project / Image / Video / Camera / Settings
│   │   ├── components/           # Konva 画布、结果列表、模型选择器、日志面板
│   │   ├── stores/               # Pinia：project / model / task / log / ui
│   │   ├── api/                  # WebSocket 客户端、消息编解码、类型定义
│   │   ├── utils/                # 颜色、格式化、文件工具
│   │   ├── router/
│   │   ├── App.vue
│   │   └── main.ts
│   ├── package.json
│   └── electron.vite.config.ts
│
├── backend/
│   ├── app/
│   │   ├── main.py               # FastAPI 入口（仅装配，不含业务）
│   │   ├── config.py             # 路径、端口、日志级别（不硬编码路径）
│   │   ├── websocket/
│   │   │   ├── server.py         # WS 连接管理、消息分发
│   │   │   ├── protocol.py       # 消息类型枚举 + pydantic 模型
│   │   │   └── handlers/         # 按域拆分：model / detect / video / task / project
│   │   ├── task/
│   │   │   ├── base.py           # Task 抽象、状态机
│   │   │   ├── image_task.py
│   │   │   ├── folder_task.py
│   │   │   ├── video_task.py     # 后续
│   │   │   ├── stream_task.py    # 后续
│   │   │   └── manager.py        # TaskManager：创建/暂停/取消/进度
│   │   ├── inference/
│   │   │   ├── base.py           # BaseRuntime 抽象
│   │   │   ├── factory.py        # Runtime 工厂（按 backend 类型实例化）
│   │   │   ├── pipeline.py       # 多模型 Pipeline / Result Merge
│   │   │   ├── postprocess.py    # 统一 Detection 结果结构
│   │   │   └── yolo_runtime.py   # YOLORuntime（ultralytics）
│   │   ├── runtime/
│   │   │   └── registry.py       # 后端注册表（扩展点）
│   │   ├── model_manager/
│   │   │   ├── scanner.py        # 扫描 models/ 目录
│   │   │   ├── loader.py         # 加载 / 卸载 / 缓存
│   │   │   ├── metadata.py       # class names、显示名映射
│   │   │   └── config_schema.py  # 模型 YAML schema
│   │   ├── project/
│   │   │   ├── schema.py         # project.json 结构
│   │   │   ├── store.py          # 打开/创建/保存项目
│   │   │   └── results.py        # 结果读写
│   │   ├── database/
│   │   │   ├── connection.py
│   │   │   ├── models.py         # 表定义
│   │   │   └── migrations/
│   │   └── utils/
│   │       ├── logging.py        # loguru 配置：文件 + WS sink
│   │       ├── paths.py          # 路径解析（禁止硬编码）
│   │       └── image_io.py
│   ├── requirements/
│   ├── setup_env.py
│   └── pyproject.toml
│
├── models/                       # 模型权重 + YAML 配置
│   └── examples/
│       └── person.yaml
│
├── projects/                     # 用户项目数据（运行时生成）
│   └── demo/
│       ├── project.json
│       ├── images/
│       ├── videos/
│       ├── models/
│       ├── results/
│       └── database.sqlite
│
├── docs/
│   ├── ARCHITECTURE.md           # 本文档
│   ├── PHASE1.md                 # 第一阶段任务
│   ├── PROTOCOL.md               # 通信协议
│   └── MODEL_CONFIG.md           # 模型 YAML 说明
│
└── README.md
```

---

## 5. 核心抽象设计

### 5.1 Runtime Interface（推理后端抽象）

**禁止**上层直接 `model.predict()`。统一走 `BaseRuntime`。

```python
# backend/app/inference/base.py （设计示意，非最终代码）

class BackendType(str, Enum):
    YOLO = "yolo"
    ONNX = "onnx"
    TENSORRT = "tensorrt"
    RKNN = "rknn"

@dataclass
class DetectObject:
    id: int
    class_id: int
    class_name: str          # 原始类别名（代码逻辑用）
    display_name: str        # 渲染名（可中文，来自映射）
    confidence: float
    bbox: tuple[float, float, float, float]  # x1,y1,x2,y2
    visible: bool = True
    extra: dict = field(default_factory=dict)  # pose keypoints / mask 等扩展

@dataclass
class FrameResult:
    frame_id: int
    objects: list[DetectObject]
    meta: dict               # 耗时、模型 id 等

class BaseRuntime(ABC):
    backend_type: BackendType

    @abstractmethod
    def load(self, model_path: Path, config: ModelConfig) -> None: ...

    @abstractmethod
    def predict(self, image: np.ndarray) -> list[DetectObject]: ...

    @abstractmethod
    def class_names(self) -> list[str]: ...

    @abstractmethod
    def unload(self) -> None: ...
```

实现类：

| 类 | 阶段 | 说明 |
|----|------|------|
| `YOLORuntime` | P1 | ultralytics 封装 |
| `ONNXRuntime` | P2+ | onnxruntime |
| `TensorRTRuntime` | P3+ | TensorRT engine |
| `RKNNRuntime` | P3+ | RK3588 / RDK |

**扩展新后端时不修改上层代码**，只需：
1. 实现 `BaseRuntime`
2. 在 `registry.py` 注册
3. 增加对应 `requirements/*.txt`

### 5.2 Model Manager

职责：

1. 扫描 `models/` 目录（及项目内 `models/`）
2. 解析模型 YAML 配置
3. 加载模型到 `BaseRuntime`
4. 读取并暴露 class 列表（含显示名映射）
5. **缓存已加载模型**，避免每次推理重载
6. 支持多模型同时驻留内存

#### 模型 YAML 配置（独立文件，支持多模型并行）

```yaml
# models/examples/person.yaml
id: person                    # 模型短 id / 英文简写，渲染前缀 {id}:{class}
name: 人员检测
backend: yolo                 # yolo | onnx | tensorrt | rknn
model_path: weights/person.pt
task: detect                  # detect | segment | pose | ...
conf: 0.45
iou: 0.5
device: cpu                   # cpu | 0 | 0,1 ...
classes:                      # 可选：过滤类别
  - person
  - helmet

class_display:                # 仅影响渲染名称；代码仍用原始 class 名
  person: 人员
  helmet: 安全帽
  stone: 石块

render:
  color: "#FF3B30"
  line_width: 2
  label_template: "{id}:{class}"   # 支持 {id} {class} {confidence} {track_id}
```

渲染规则（偏好对齐）：

- 标签格式默认 `{id}:{class}`，`class` 使用**显示名**（可中文）
- 映射只改渲染；业务/过滤/保存仍用原始 `class_name`
- 中文渲染由前端 Canvas / 后端可选绘制共同保证字体

### 5.3 Task System

所有操作进入 `TaskManager`。

```python
class TaskType(str, Enum):
    IMAGE = "image"
    FOLDER = "folder"
    VIDEO = "video"
    STREAM = "stream"

class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class Task:
    task_id: str
    type: TaskType
    status: TaskStatus
    progress: float            # 0.0 ~ 1.0
    created_time: datetime
    updated_time: datetime
    params: dict
    error: str | None
    result_ref: str | None     # 结果索引路径
```

状态机：

```
PENDING ──start──► RUNNING ──complete──► COMPLETED
   │                 │  │
   │                 │  └──fail──► FAILED
   │                 │
   │              pause│resume
   │                 ▼
   │               PAUSED
   │                 │
   └──cancel─────────┴──cancel──► CANCELLED
```

### 5.4 Inference Pipeline（多模型）

多个模型**不是简单 for 循环**，而是 Pipeline：

```
Input Frame
    │
    ├─► Model A (person)
    ├─► Model B (helmet)
    └─► Model C (vest)
    │
    ▼
Result Merge（按 frame_id 聚合，分配全局 object id）
    │
    ▼
FrameResult → 渲染 / 保存
```

设计要点：

- 每个模型节点独立 Runtime 实例
- 支持并行（线程/进程池，受 GIL 与设备限制约束）
- Merge 时保留 `model_id` 来源
- 预留级联接口：`PipelineNode.next` / `condition`（后续）

### 5.5 检测框缓存（视频/流，偏好对齐）

```
frame 0    detect  ──► boxes_cache = [b1, b2]
frame 1    render cache
frame 2    render cache
...
frame N-1  render cache
frame N    detect  ──► boxes_cache = [b3]
```

规则：

| 规则 | 说明 |
|------|------|
| 检测间隔 `skip_frame` | 每 N 帧推理一次 |
| 框持续 `box_persistence` | 检测结果持续渲染的帧数 |
| 约束 | `box_persistence <= skip_frame`（超出时自动钳制为 skip_frame） |
| 缓存 | 只存 JSON 结果，**不复制图像帧** |
| 渲染 | 叠加在当前显示帧上；保存视频时由渲染管线合成 |

---

## 6. 推理结果数据结构

**禁止**把框画死后才保存。必须保存：**原始媒体 + JSON 结果**。

```json
{
  "frame_id": 100,
  "model_id": "person",
  "objects": [
    {
      "id": 1,
      "class_id": 0,
      "class_name": "person",
      "display_name": "人员",
      "confidence": 0.95,
      "bbox": [120.5, 80.2, 340.0, 520.8],
      "visible": true,
      "style": {
        "color": "#ff0000",
        "line_width": 2
      }
    }
  ],
  "meta": {
    "infer_ms": 23.4,
    "timestamp": "2026-03-27T12:00:00.123Z"
  }
}
```

前端使用 Konva Canvas 渲染叠加层，支持：

- 点击结果列表 → 对应框高亮
- 隐藏/显示单个框（`visible`）
- 框颜色 / 粗细 / 标签模板
- 标签模板变量：`{class}` `{confidence}` `{id}` `{track_id}`

### 6.1 视频操作记录（后续阶段）

```json
{
  "ops": [
    { "frame_id": 100, "action": "hide_object", "object_id": 2 },
    { "frame_id": 200, "action": "modify_bbox", "object_id": 1, "bbox": [1,2,3,4] }
  ]
}
```

支持时间轴查看、逐帧查看、操作回放。

---

## 7. 通信协议

统一 JSON 消息，经 WebSocket 传输。

### 7.1 信封格式

```json
{
  "type": "detect.image",
  "id": "uuid-or-seq",
  "data": { },
  "ts": 1711526400123
}
```

- `type`：`domain.action` 命名
- `id`：请求关联（响应/进度可回带）
- `data`：负载
- `ts`：时间戳

### 7.2 消息类型（第一阶段）

| type | 方向 | 说明 |
|------|------|------|
| `model.list` | C→S | 列出可用模型 |
| `model.load` | C→S | 加载模型（返回 class 列表） |
| `model.unload` | C→S | 卸载模型 |
| `model.loaded` | S→C | 加载完成事件（含 classes / display 映射） |
| `detect.image` | C→S | 单图推理 |
| `detect.folder` | C→S | 文件夹批量推理 |
| `detect.result` | S→C | 推理结果（FrameResult） |
| `task.create` | C→S | 创建任务 |
| `task.start` / `task.pause` / `task.cancel` | C→S | 任务控制 |
| `task.progress` | S→C | 进度推送 |
| `task.done` | S→C | 任务完成/失败 |
| `project.open` / `project.save` | C→S | 项目读写 |
| `log.message` | S→C | 日志推送 |
| `ping` / `pong` | 双向 | 心跳 |

后续扩展：`video.start` `video.seek` `camera.open` `stream.frame` `pipeline.run` 等。

### 7.3 日志双通道

```
loguru ──► 文件 (logs/yolo-vision-workbench_YYYYMMDD.log)
       └──► WebSocket sink ──► Electron 日志面板
```

级别：`DEBUG` / `INFO` / `WARNING` / `ERROR` / `CRITICAL`。

---

## 8. 项目系统

```
projects/<project_name>/
├── project.json          # 项目元数据、模型绑定、参数
├── images/               # 原始图片
├── videos/               # 原始视频
├── models/               # 项目引用的模型配置/权重（可选）
├── results/              # JSON 结果（按 task_id 组织）
│   └── <task_id>/
│       ├── meta.json
│       └── frames.jsonl
└── database.sqlite       # 任务、结果索引、操作记录
```

`project.json` 示例：

```json
{
  "name": "demo",
  "version": 1,
  "created_at": "...",
  "models": [
    { "config": "models/examples/person.yaml", "enabled": true }
  ],
  "params": {
    "conf": 0.45,
    "skip_frame": 5,
    "box_persistence": 5
  },
  "last_task_id": "..."
}
```

打开项目时恢复：模型绑定、参数、历史结果索引。

---

## 9. 配置与路径（禁止硬编码）

```
backend/app/config.py
  - 从环境变量 + 配置文件加载
  - 根路径可覆盖（YOLO_STUDIO_ROOT）
  - 端口、主机、日志目录、models 目录、projects 目录均可配置

配置优先级：
  环境变量 > config.yaml > 代码默认值
```

---

## 10. 跨平台扩展预留

| 关注点 | 设计 |
|--------|------|
| 路径 | `pathlib`，禁止字符串拼接绝对路径 |
| 进程 | 后端可独立启动或由 Electron 子进程拉起 |
| 设备 | Runtime 层封装 device（cpu/cuda/npu） |
| 打包 | Electron 打包 UI；Python 侧可选 PyInstaller / 系统 Python |
| ARM/RKNN | 仅新增 Runtime + requirements，不动上层 |
| 依赖 | 按 backend 拆分 requirements，避免 torch 污染轻量环境 |

---

## 11. 安全与工程约束

1. Electron `contextIsolation: true`，`nodeIntegration: false`，preload 白名单 API
2. WebSocket 仅绑定 `127.0.0.1`（桌面单机）
3. 文件对话框只在主进程打开，渲染层不直接碰文件系统
4. pydantic 校验所有入站消息
5. 不写巨型文件；单一模块建议 ≤ 400 行
6. 类型提示全覆盖（Python `typing` / TS `strict`）
7. 模块化、高复用；推理后端与 UI 零耦合

---

## 12. 阶段路线图

| 阶段 | 内容 | 出口标准 |
|------|------|----------|
| **P1 基础骨架** | Electron + Vue3 初始化、Python Backend、WebSocket、日志、模型管理、图片推理、Canvas 显示 | 能选图 → 选模型 → 推理 → 画布显示框 |
| **P2 图片增强** | 文件夹任务、多模型 Pipeline、conf/classes 调节、结果列表交互、项目保存 | 批量图片 + 多模型可用 |
| **P3 视频** | VideoTask、跳帧、框缓存、时间轴、操作记录 | 视频检测可回放 |
| **P4 相机/流** | USB Camera、RTSP、实时推理、录制生成 VideoTask | 实时流可用 |
| **P5 多后端** | ONNX Runtime、TensorRT、RKNN | 同 UI 切换后端 |
| **P6 高级模型** | Segment / Pose / OCR / Tracking / SAM | 多任务类型 |

---

## 13. 关键设计决策（ADR 摘要）

| # | 决策 | 理由 |
|---|------|------|
| D1 | Electron 与 Python 进程分离 | 职责清晰、后端可独立测试/替换 |
| D2 | WebSocket JSON 协议而非仅 IPC | 便于调试、未来远程/多客户端 |
| D3 | Runtime 抽象强制 | 满足多硬件后端扩展，避免上层改动 |
| D4 | 结果存 JSON 不画死图 | 可回放、可改样式、可二次分析 |
| D5 | 模型 YAML 独立配置 | 多模型并行、显示名映射、可版本管理 |
| D6 | 框缓存不拷贝图像 | 内存可控（尤其视频/流） |
| D7 | 按后端拆 requirements + setup_env.py | 依赖隔离，贴合既有环境习惯 |

---

## 14. 第一阶段范围（摘要）

见 `docs/PHASE1.md` 完整任务拆解。P1 交付物：

1. 可运行的 Electron + Vue3 + TS 桌面壳
2. 可运行的 FastAPI Backend + WebSocket
3. 结构化日志（文件 + UI）
4. 模型扫描/加载/缓存/class 列表（含显示名映射）
5. 单图 / 文件夹推理（ImageTask + FolderTask）
6. Konva Canvas 叠加渲染 + 结果列表 + 高亮/隐藏
7. 基础协议与类型定义

**明确不包含（P1）**：视频、摄像头、Tracking、非 YOLO 后端、完整项目系统 UI。
