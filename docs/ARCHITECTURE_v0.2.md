# YOLO Vision Workbench 架构设计

> 版本：**v0.2**（架构 Review 修订稿，待确认后进入编码）
> 基线：v0.1 → 本版按 7 项 Review 意见修订
> 目标平台：Windows 优先，架构兼容 Linux / ARM / RK3588 / TensorRT / ONNX

---

## 0. v0.2 Review 记录

| # | Review 项 | 结论 | 落点 |
|---|-----------|------|------|
| 1 | P1 加入基础多模型 Pipeline | 采纳。需求明确「多模型同时选择」，不能推到 P2 | §5.4；PHASE1 P1-07/P1-16 |
| 2 | SQLite 基础设计 | 采纳。JSON 仅作导出/交换，查询与索引以 SQLite 为准 | §8.2；PHASE1 P1-08 |
| 3 | Electron 自动拉起 Backend 生命周期 | 采纳。补齐进程管理、健康检查、退出策略 | §3.4 / §10.1 |
| 4 | Inference Profile | 采纳。项目级「推理参数预设」独立实体，可保存/切换 | §5.6 |
| 5 | 视频导出设计 | 采纳。原视频 + JSON 结果 + 操作记录 → 合成视频 | §9 |
| 6 | Model Repository | 采纳。为内置官方模型预留目录与索引协议 | §5.7 |
| 7 | 未来扩展重构风险检查 | 完成。发现 6 处需在 P1 稳固的扩展点，避免后患 | §15 |

**v0.2 相对 v0.1 的结构性变化**

1. 结果模型从「纯 bbox 检测」扩展为 **Geometry 多态**（bbox / mask / keypoints / text）
2. 存储从「JSON 为主」改为 **SQLite 为主、JSON 为导出/交换格式**
3. 新增 **Process Supervisor**（Electron ↔ Python 生命周期）
4. 新增 **Inference Profile**、**Video Export**、**Model Repository** 三个子系统
5. P1 范围纳入 **基础多模型并行 Pipeline**

---

## 1. 产品定位

YOLO Vision Workbench 是个人使用优先、未来可能开源的**桌面端视觉 AI 推理工作台**。

它不是 Demo，而是长期可扩展的平台，覆盖：

| 能力域 | 第一阶段 | 后续阶段 |
|--------|----------|----------|
| 模型类型 | YOLO Detect（多模型并行） | Segment / Pose / OCR / Tracking / SAM |
| 推理后端 | Ultralytics (PyTorch) | ONNX Runtime / TensorRT / RKNN |
| 输入源 | 单图 / 图片文件夹 | 视频文件 / USB Camera / RTSP |
| 结果呈现 | SQLite + JSON + Canvas | 时间轴 / 操作回放 / 视频导出 |
| 任务形态 | Image / Folder / **Pipeline(基础)** | Video / Stream / Export / Cascade |
| 模型来源 | 本地 models/ | Model Repository（官方/社区包） |

---

## 2. 总体架构

```
┌──────────────────────────────────────────────────────────────────┐
│  Electron Desktop                                                │
│  ┌─────────────────────┐  ┌──────────────────────────────────┐   │
│  │ Renderer (UI Only)  │  │ Main Process                     │   │
│  │ views / components  │  │ ┌────────────┐ ┌──────────────┐  │   │
│  │ Konva / Video.js    │  │ │ Process    │ │ File Dialog  │  │   │
│  │ Pinia stores        │  │ │ Supervisor │ │ Window Mgmt  │  │   │
│  │ api/ws client       │  │ │ spawn/     │ └──────────────┘  │   │
│  └──────────┬──────────┘  │ │ health/kill│                   │   │
│             │ IPC(有限)   │ └─────┬──────┘                   │   │
│             └─────────────┼───────┘                          │   │
└───────────────────────────┼──────────────────────────────────┘   │
                            │ spawn / stdio / port                 │
                            │ WebSocket 127.0.0.1                  │
┌───────────────────────────▼──────────────────────────────────────┐
│  Python Backend Service                                          │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │ FastAPI HTTP (/health) + WebSocket Gateway               │    │
│  └────────────┬─────────────────────┬───────────────────────┘    │
│               │                     │                            │
│  ┌────────────▼──────┐  ┌───────────▼────────┐  ┌─────────────┐  │
│  │ Task Manager      │  │ Model Manager      │  │ Project     │  │
│  │ Image/Folder/     │  │ scan/load/cache    │  │ Store       │  │
│  │ Pipeline/Export   │  │ class display map  │  │ Profile     │  │
│  └────────────┬──────┘  └───────────┬────────┘  └──────┬──────┘  │
│               │                     │                  │         │
│  ┌────────────▼─────────────────────▼──────────────────▼──────┐  │
│  │ Inference Engine (Pipeline)                               │  │
│  │ 多模型并行 / 级联预留 / Result Merge / Geometry 多态       │  │
│  └────────────────────────────┬───────────────────────────────┘  │
│                               │                                  │
│  ┌────────────────────────────▼───────────────────────────────┐  │
│  │ Runtime Interface (BaseRuntime)                            │  │
│  │ YOLO │ ONNX │ TensorRT │ RKNN │ (OCR/Track 扩展点)         │  │
│  └────────────────────────────┬───────────────────────────────┘  │
│                               │                                  │
│  ┌──────────────┐  ┌──────────▼─────────┐  ┌──────────────────┐  │
│  │ SQLite       │  │ Media / Export     │  │ Model Repository │  │
│  │ (主存储)     │  │ opencv/ffmpeg      │  │ catalog + local  │  │
│  └──────────────┘  └────────────────────┘  └──────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

### 2.1 职责边界（硬约束）

| 层 | 负责 | 禁止 |
|----|------|------|
| Electron Renderer | UI、交互、Canvas/视频显示 | 推理、直接 FS（除 dialog 结果路径）、YOLO 调用 |
| Electron Main | 窗口、dialog、**Backend 进程生命周期**、端口管理 | 业务推理逻辑 |
| Python Backend | 模型、推理、任务、存储、导出 | UI 渲染 |
| Inference Engine | 多模型编排、合并、后处理 | 硬编码 Runtime |
| Runtime | load / predict / unload | 上层业务语义 |
| Storage | SQLite 持久化、导出 JSON | 业务决策 |

**禁止 Electron 直接调用 YOLO。禁止把推理逻辑写入前端。**

---

## 3. 技术栈

### 3.1 Frontend（desktop/）

| 组件 | 选型 | 用途 |
|------|------|------|
| 桌面壳 | Electron | 窗口、文件对话框、**子进程管理** |
| 构建 | Vite + electron-vite | 开发热更新 / 生产打包 |
| UI | Vue 3 + TypeScript | 组件化界面 |
| 状态 | Pinia | project / model / task / log / profile |
| 组件库 | Element Plus | 表格、表单、对话框 |
| 画布 | Konva.js | 检测框/mask/keypoints 叠加、交互 |
| 视频 | Video.js | 播放、时间轴、导出预览 |
| 通信 | WebSocket + 类型化协议 | 与 Backend 通信 |

### 3.2 Backend（backend/）

| 组件 | 选型 | 用途 |
|------|------|------|
| 运行时 | Python 3.12 | — |
| 包管理 | uv | 依赖锁定 |
| Web | FastAPI | HTTP + WebSocket |
| 校验 | pydantic v2 | 消息 / 配置 / 结果 |
| 日志 | loguru | 文件 + WS 推送 |
| **主存储** | **SQLite**（aiosqlite / sqlite3） | 项目、任务、结果、操作记录、Profile |
| 交换/导出 | JSON / JSONL | 可读导出、跨工具交换、备份 |
| 视觉 | opencv-python | IO / 绘制辅助 |
| 推理 | ultralytics | YOLO 系列 |
| 媒体 | ffmpeg | 解码、**视频导出合成** |
| 配置 | PyYAML | 模型配置、应用配置 |
| 模型仓库 | httpx（后续） | 官方模型目录拉取 |

### 3.3 环境初始化

```
backend/
├── setup_env.py
├── requirements/
│   ├── base.txt          # FastAPI / pydantic / loguru / pyyaml / aiosqlite
│   ├── yolo.txt          # ultralytics + torch
│   ├── onnx.txt
│   ├── tensorrt.txt
│   └── rknn.txt
└── wheels/
```

### 3.4 Electron ↔ Python Backend 生命周期（新增）

**目标**：用户双击桌面应用即用；Backend 崩溃可恢复；退出不残留进程。

```
App Launch
    │
    ▼
Electron Main: ProcessSupervisor
    │
    ├─ 1. 解析后端启动配置（python 路径 / venv / 端口 / 超时）
    ├─ 2. 选择空闲端口（或配置固定端口，占用则递增）
    ├─ 3. spawn(backend)  ── env: YOLO_STUDIO_PORT / YOLO_STUDIO_ROOT
    ├─ 4. 轮询 GET /health  直到 ready 或 timeout
    │         │
    │         ├─ success ──► 通知 Renderer: backend.ready {ws_url}
    │         └─ timeout ──► 通知 Renderer: backend.error（可重试/查看日志）
    │
    ├─ 5. 常驻监控
    │         ├─ 健康检查间隔（如 5s）
    │         ├─ 进程 exit / WS 断连 ──► 指数退避重启（有限次数）
    │         └─ 重启耗尽 ──► UI 错误态 + 导出诊断日志
    │
    └─ 6. App Quit
              ├─ 优雅：WS 发送 system.shutdown → 等待 backend 退出（短超时）
              └─ 强制：kill 进程树（Windows: taskkill /T；POSIX: process group）
```

| 策略项 | 设计 |
|--------|------|
| 启动模式 | 默认自动拉起；开发模式可「仅连接已有 backend」 |
| 端口 | 配置优先；失败则探测 `port+1..port+N`，结果写入运行时状态 |
| 超时 | `/health` 默认 30s（torch 首次 import 可能慢，可配置） |
| 崩溃重启 | 最多 N 次（默认 3），间隔指数退避 |
| 退出 | 先优雅后强制；保证无孤儿 python 进程 |
| 日志归属 | backend stdout/stderr 接到主进程 logger，再转发 UI |
| 多开 | 单实例锁（可选）；避免多 backend 抢端口/项目锁 |

**Backend 侧配合约定**

- `GET /health` → `{status, version, pid, uptime}`
- `GET /ready` → 模型系统/DB 初始化完成（可选，P1 用 /health 即可）
- 监听 `127.0.0.1`；收到 `system.shutdown` 后收尾再退出

---

## 4. 目录结构

```
YOLO-Studio/
├── desktop/
│   ├── electron/
│   │   ├── main.ts               # 窗口 + 装配
│   │   ├── preload.ts
│   │   ├── backend/
│   │   │   ├── supervisor.ts     # 【新增】spawn/health/restart/kill
│   │   │   └── ports.ts
│   │   └── ipc/
│   ├── src/
│   │   ├── views/                # Home / Project / Image / Video / Export / Settings
│   │   ├── components/           # Konva、结果列表、模型/Profile 选择、日志
│   │   ├── stores/
│   │   ├── api/
│   │   ├── utils/
│   │   ├── router/
│   │   ├── App.vue
│   │   └── main.ts
│   ├── package.json
│   └── electron.vite.config.ts
│
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── websocket/
│   │   │   ├── server.py
│   │   │   ├── protocol.py
│   │   │   └── handlers/         # model / detect / task / project / profile / export / system
│   │   ├── task/
│   │   │   ├── base.py
│   │   │   ├── image_task.py
│   │   │   ├── folder_task.py
│   │   │   ├── pipeline_task.py  # 【P1】多模型任务（与 Image/Folder 组合）
│   │   │   ├── video_task.py     # 后续
│   │   │   ├── stream_task.py    # 后续
│   │   │   ├── export_task.py    # 【设计】视频导出任务
│   │   │   └── manager.py
│   │   ├── inference/
│   │   │   ├── base.py           # BaseRuntime + Geometry 多态结果
│   │   │   ├── factory.py
│   │   │   ├── pipeline.py       # 多模型并行 + Merge
│   │   │   ├── postprocess.py
│   │   │   └── yolo_runtime.py
│   │   ├── runtime/
│   │   │   └── registry.py
│   │   ├── model_manager/
│   │   │   ├── scanner.py
│   │   │   ├── loader.py
│   │   │   ├── metadata.py
│   │   │   ├── config_schema.py
│   │   │   └── repository.py     # 【新增】Model Repository 目录/索引
│   │   ├── project/
│   │   │   ├── schema.py
│   │   │   ├── store.py
│   │   │   ├── profile.py        # 【新增】Inference Profile
│   │   │   └── results.py
│   │   ├── database/
│   │   │   ├── connection.py
│   │   │   ├── schema.sql        # 【强化】权威表结构
│   │   │   ├── dao/              # tasks / frames / objects / ops / profiles
│   │   │   └── migrations/
│   │   ├── export/
│   │   │   ├── video_exporter.py # 【新增】原视频+结果+操作 → 输出视频
│   │   │   └── draw.py           # 服务端绘制（导出用，与 UI 样式同源）
│   │   └── utils/
│   │       ├── logging.py
│   │       ├── paths.py
│   │       └── image_io.py
│   ├── requirements/
│   ├── setup_env.py
│   └── pyproject.toml
│
├── models/
│   ├── examples/                 # 用户/项目本地模型
│   └── repository/               # 【新增】官方/内置模型包
│       ├── catalog.yaml          # 或 catalog.json：索引
│       └── packages/
│           └── coco-yolov8n/
│               ├── manifest.yaml
│               └── weights/
│
├── projects/
│   └── demo/
│       ├── project.json          # 轻量元数据（名字、路径、版本）
│       ├── profiles/             # Inference Profile 导出（可选）
│       ├── images/
│       ├── videos/
│       ├── models/
│       ├── results/              # 大结果文件 JSONL/媒体缓存
│       └── database.sqlite       # 【权威】项目数据
│
├── docs/
│   ├── ARCHITECTURE.md           # 本文档
│   ├── PHASE1.md
│   ├── PROTOCOL.md
│   ├── MODEL_CONFIG.md
│   ├── DATABASE.md               # 【新增】SQLite schema
│   └── EXPORT.md                 # 【新增】视频导出说明
│
└── README.md
```

---

## 5. 核心抽象设计

### 5.1 Runtime Interface + 多态结果（扩展性强化）

**禁止**上层直接 `model.predict()`。统一走 `BaseRuntime`。

v0.2 将 `DetectObject` 升级为 **Task 感知的结果对象**，避免 Segment/OCR/Tracking 时推翻重来。

```python
# 设计示意，非最终代码

class BackendType(str, Enum):
    YOLO = "yolo"
    ONNX = "onnx"
    TENSORRT = "tensorrt"
    RKNN = "rknn"

class ModelTaskType(str, Enum):
    DETECT = "detect"
    SEGMENT = "segment"
    POSE = "pose"
    OCR = "ocr"
    TRACK = "track"
    CUSTOM = "custom"

class GeometryType(str, Enum):
    BBOX = "bbox"
    MASK = "mask"            # 多边形/RLE 引用
    KEYPOINTS = "keypoints"
    POLYGON = "polygon"
    TEXT = "text"

@dataclass
class Geometry:
    type: GeometryType
    bbox: tuple[float, float, float, float] | None = None
    mask_ref: str | None = None          # 指向 results/ 中 mask 数据，避免内存爆炸
    points: list[tuple[float, float]] | None = None
    keypoints: list[dict] | None = None  # {x,y,visible,name}
    text: str | None = None              # OCR
    text_conf: float | None = None

@dataclass
class ResultObject:
    id: int                          # 帧内 id
    model_id: str                    # 来源模型（Pipeline 合并后必填）
    class_id: int
    class_name: str                  # 原始名（逻辑用）
    display_name: str                # 渲染名（可中文）
    confidence: float
    geometry: Geometry
    track_id: int | None = None      # Tracking 预留，P1 为 None
    visible: bool = True
    style: dict = field(default_factory=dict)
    extra: dict = field(default_factory=dict)

@dataclass
class FrameResult:
    frame_id: int
    media_ref: str                   # 原图/帧引用（路径或 id），不内嵌图像
    objects: list[ResultObject]
    meta: dict                       # infer_ms, pipeline_ms, timestamp, model_ids

class BaseRuntime(ABC):
    backend_type: BackendType
    model_task: ModelTaskType

    @abstractmethod
    def load(self, model_path: Path, config: "ModelConfig") -> None: ...

    @abstractmethod
    def predict(self, image: "np.ndarray") -> list[ResultObject]: ...

    @abstractmethod
    def class_names(self) -> list[str]: ...

    @abstractmethod
    def unload(self) -> None: ...
```

实现与扩展：

| 类 | 阶段 | 备注 |
|----|------|------|
| `YOLORuntime` | P1 | detect；segment/pose 同入口不同 task |
| `ONNXRuntime` | P2+ | 通用 onnx |
| `TensorRTRuntime` | P3+ | engine 序列化缓存 |
| `RKNNRuntime` | P3+ | RK3588 / RDK |
| `OCRRuntime` | P6 | 输出 GeometryType.TEXT |
| `TrackRuntime` | P6 | 或 Pipeline 节点级 Tracker 后处理 |

**扩展新后端时不修改上层代码**：实现接口 → `registry.py` 注册 → 独立 requirements。

### 5.2 Model Manager

职责：扫描、解析 YAML、加载缓存、class 列表与显示名映射、多模型驻留。

#### 模型 YAML

```yaml
id: person
name: 人员检测
backend: yolo
model_path: weights/person.pt
task: detect                  # detect | segment | pose | ocr | track
conf: 0.45
iou: 0.5
device: cpu
classes: [person, helmet]

class_display:
  person: 人员
  helmet: 安全帽

render:
  color: "#FF3B30"
  line_width: 2
  label_template: "{id}:{class}"
```

规则：`class_display` 仅影响渲染；逻辑仍用 `class_name`。标签默认 `{id}:{class}`。

### 5.3 Task System

```python
class TaskType(str, Enum):
    IMAGE = "image"
    FOLDER = "folder"
    PIPELINE = "pipeline"       # 【P1】多模型包装/组合任务
    VIDEO = "video"
    STREAM = "stream"
    EXPORT = "export"           # 视频导出

class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    FAILED = "failed"
```

`Task` 字段：`task_id / type / status / progress / created_time / updated_time / params / profile_id / model_ids / error / result_ref`。

状态机同 v0.1（PENDING→RUNNING→COMPLETED/FAILED，支持 pause/cancel）。

**P1 多模型任务形态**：不单独发明并行业务，而是：

- `ImageTask` / `FolderTask` 可绑定 **多个 model_id**
- 内部通过 `Pipeline` 执行 merge
- `task.type` 仍为 image/folder；`params.pipeline = {model_ids, mode: parallel}`

`PIPELINE` 类型预留给后续级联/自定义 DAG。

### 5.4 Inference Pipeline（多模型 · P1 基础版）

```
Input Frame
    │
    ▼
PipelineExecutor (mode=parallel)
    ├─► Runtime A (person)
    ├─► Runtime B (helmet)
    └─► Runtime C (vest)
    │
    ▼
Result Merge
    - 按 frame 聚合
    - 保留 model_id
    - object id 在帧内统一编号
    - 可选 IoU NMS 跨模型去重（P1 默认关闭）
    │
    ▼
FrameResult (SQLite + 可选 JSON)
```

| 项 | P1 基础版 | 后续 |
|----|-----------|------|
| 拓扑 | 并行 fan-out / merge | 级联、条件跳转、ROI 传递 |
| 并行度 | 线程池（模型数上限） | 进程池 / 设备亲和 |
| 合并策略 | 简单拼接 + id 分配 | 跨模型 NMS、优先级、规则引擎 |
| 失败策略 | 单模型失败记 warning，其余继续 | 可配置 fail-fast |
| 性能 | 串行亦可（小模型） | 批处理、流水线帧级并行 |

**P1 必须支持：用户同时勾选多个模型 → 一次推理输出合并结果。**

### 5.5 检测框缓存（视频/流）

| 规则 | 说明 |
|------|------|
| `skip_frame` | 每 N 帧推理 |
| `box_persistence` | 结果持续渲染帧数；**≤ skip_frame**，超出自动钳制 |
| 缓存 | 只存结果引用（SQLite/JSON），**不复制图像帧** |
| 渲染 | 叠加在当前帧；导出时由 `export/draw.py` 合成 |

### 5.6 Inference Profile（新增）

**问题**：项目打开后要恢复「推理参数」——conf、iou、skip_frame、box_persistence、选中模型、class 过滤、样式等。不应散落在 project.json 各处。

**设计**：独立实体 **Inference Profile**（可命名、可切换、可导入导出）。

```yaml
# profiles/default.yaml （亦可存 SQLite profiles 表）
id: default
name: 默认检测参数
description: 项目常用配置

models:
  - model_id: person
    enabled: true
    conf: 0.45
    iou: 0.5
    classes: [person, helmet]    # 过滤；空=全部
  - model_id: helmet
    enabled: true
    conf: 0.40

pipeline:
  mode: parallel                 # parallel | serial
  merge: concat                  # concat | nms

runtime:
  device: cpu
  skip_frame: 5                  # 视频/流
  box_persistence: 5

render:
  label_template: "{id}:{class}"
  default_color: "#3B82F6"
  line_width: 2
  show_confidence: true

export:
  fps: 0                         # 0=与源视频一致
  draw: true
  codec: h264
```

| 能力 | 说明 |
|------|------|
| 保存 | 项目内 profiles + SQLite；可导出 yaml |
| 切换 | 一键应用到当前检测会话 |
| 绑定任务 | `task.profile_id` 记录当时参数，保证可复现 |
| 与 Model YAML 关系 | 模型 YAML=模型固有能力/默认；Profile=项目内用户覆盖 |

WS：`profile.list` / `profile.save` / `profile.apply` / `profile.delete`。

### 5.7 Model Repository（新增）

**目标**：未来内置官方/常用模型包（COCO、安全帽、工地等），用户可浏览/启用，而不手工拷权重。

```
models/
├── examples/           # 用户本地手放
└── repository/
    ├── catalog.yaml    # 索引：包列表、版本、任务类型、下载源、校验和
    └── packages/
        └── <package_id>/
            ├── manifest.yaml   # 与 Model YAML 兼容 + 发行元数据
            └── weights/
```

**catalog.yaml（示意）**

```yaml
schema_version: 1
packages:
  - id: coco-yolov8n
    name: COCO YOLOv8n Detect
    version: "1.0.0"
    task: detect
    backend: yolo
    source: builtin              # builtin | url
    # url: https://...
    # sha256: ...
    entry: manifest.yaml
    license: AGPL-3.0
    tags: [coco, detect, yolo]
```

**manifest.yaml** = Model YAML 超集（增加 `package_id / version / license / requirements`）。

| 机制 | 设计 |
|------|------|
| 发现 | 启动扫描 `repository/catalog.yaml` + `packages/*/manifest.yaml` |
| 来源 | P1：仅本地 builtin；后续：URL 下载 + sha256 校验 + 缓存 |
| 与 Model Manager | Repository 产出标准 `ModelConfig`，进入同一 loader |
| UI | 模型市场列表（只读展示 P1）；启用即复制/引用到项目 |
| 版本 | manifest 内 version；同 id 多版本可并存，选择器显示 |

**P1 只做目录结构 + catalog 读取 + 合并进 model.list；不做下载。**

---

## 6. 推理结果与存储策略

### 6.1 结果对象（JSON 形态，交换/导出用）

```json
{
  "frame_id": 100,
  "media_ref": "images/001.jpg",
  "objects": [
    {
      "id": 1,
      "model_id": "person",
      "class_id": 0,
      "class_name": "person",
      "display_name": "人员",
      "confidence": 0.95,
      "geometry": {
        "type": "bbox",
        "bbox": [120.5, 80.2, 340.0, 520.8]
      },
      "track_id": null,
      "visible": true,
      "style": { "color": "#ff0000", "line_width": 2 }
    }
  ],
  "meta": { "infer_ms": 23.4, "timestamp": "..." }
}
```

Segment 扩展示意：`geometry: { "type": "mask", "bbox": [...], "mask_ref": "results/t0/masks/f100_o1.png" }`。

### 6.2 SQLite 基础设计（新增，权威存储）

> 原则：**SQLite 是项目数据的 source of truth**；JSON/JSONL 用于导出、交换、备份与大块媒体索引。禁止「只写 JSON、再扫目录」作为主路径。

**库位置**：`projects/<name>/database.sqlite`

```sql
-- 项目元数据
CREATE TABLE project_meta (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

-- Inference Profile
CREATE TABLE profiles (
  id          TEXT PRIMARY KEY,
  name        TEXT NOT NULL,
  description TEXT,
  payload     TEXT NOT NULL,          -- JSON: models/pipeline/runtime/render/export
  created_at  TEXT NOT NULL,
  updated_at  TEXT NOT NULL
);

-- 任务
CREATE TABLE tasks (
  task_id     TEXT PRIMARY KEY,
  type        TEXT NOT NULL,          -- image|folder|pipeline|video|stream|export
  status      TEXT NOT NULL,
  progress    REAL NOT NULL DEFAULT 0,
  params      TEXT NOT NULL,          -- JSON
  profile_id  TEXT REFERENCES profiles(id),
  error       TEXT,
  created_at  TEXT NOT NULL,
  updated_at  TEXT NOT NULL,
  finished_at TEXT
);

-- 媒体/文件索引
CREATE TABLE media (
  media_id    TEXT PRIMARY KEY,
  task_id     TEXT NOT NULL,
  kind        TEXT NOT NULL,          -- image|video|frame
  path        TEXT NOT NULL,
  width       INTEGER,
  height      INTEGER,
  fps         REAL,
  frame_count INTEGER,
  sha256      TEXT,
  FOREIGN KEY (task_id) REFERENCES tasks(task_id)
);

-- 帧级结果头
CREATE TABLE frames (
  task_id     TEXT NOT NULL,
  frame_id    INTEGER NOT NULL,
  media_id    TEXT,
  infer_ms    REAL,
  created_at  TEXT NOT NULL,
  PRIMARY KEY (task_id, frame_id),
  FOREIGN KEY (task_id) REFERENCES tasks(task_id)
);

-- 对象级结果
CREATE TABLE objects (
  task_id      TEXT NOT NULL,
  frame_id     INTEGER NOT NULL,
  object_id    INTEGER NOT NULL,
  model_id     TEXT NOT NULL,
  class_id     INTEGER NOT NULL,
  class_name   TEXT NOT NULL,
  display_name TEXT,
  confidence   REAL NOT NULL,
  geom_type    TEXT NOT NULL,         -- bbox|mask|keypoints|text
  geom_json    TEXT NOT NULL,         -- bbox/mask_ref/keypoints/text
  track_id     INTEGER,
  visible      INTEGER NOT NULL DEFAULT 1,
  style_json   TEXT,
  PRIMARY KEY (task_id, frame_id, object_id, model_id),
  FOREIGN KEY (task_id, frame_id) REFERENCES frames(task_id, frame_id)
);

-- 操作记录（视频/编辑）
CREATE TABLE ops (
  op_id       INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id     TEXT NOT NULL,
  frame_id    INTEGER,
  action      TEXT NOT NULL,          -- hide_object|modify_bbox|modify_style|...
  target_type TEXT,                   -- object|frame|task
  target_id   TEXT,
  payload     TEXT NOT NULL,          -- JSON
  created_at  TEXT NOT NULL,
  FOREIGN KEY (task_id) REFERENCES tasks(task_id)
);

-- 索引建议
CREATE INDEX idx_objects_frame ON objects(task_id, frame_id);
CREATE INDEX idx_objects_model ON objects(model_id);
CREATE INDEX idx_ops_task_frame ON ops(task_id, frame_id);
CREATE INDEX idx_tasks_status ON tasks(status);
```

| 存什么 | SQLite | 文件系统 |
|--------|--------|----------|
| 任务/状态/进度 | ✓ | — |
| Profile | ✓ | 可选 yaml 导出 |
| 帧/对象结果 | ✓ | 大结果 JSONL 备份 |
| 操作记录 | ✓ | 导出 JSON |
| 图像/视频/mask 位图 | 路径索引 | ✓ 本体 |
| 完整推理导出包 | 索引 | ✓ `results/<task>/export.json` |

**DAO 层**：`database/dao/` 封装，禁止业务层裸写 SQL。迁移用 `migrations/` 版本表。

### 6.3 样式与可见性

- `visible` / `style` 可写回 SQLite（用户编辑后）
- 导出时以 DB 为准；原始 JSON 保留推理时刻快照

---

## 7. 通信协议

### 7.1 信封

```json
{
  "type": "detect.image",
  "id": "uuid-or-seq",
  "data": {},
  "ts": 1711526400123
}
```

### 7.2 消息类型（P1）

| type | 方向 | 说明 |
|------|------|------|
| `model.list` | C→S | 本地 + repository 合并列表 |
| `model.load` / `model.unload` | C→S | 加载/卸载 |
| `model.loaded` | S→C | 含 classes / display / model_id |
| `detect.image` | C→S | **支持 model_ids[]（多模型）** |
| `detect.folder` | C→S | 同上 |
| `detect.result` | S→C | FrameResult（objects 含 model_id） |
| `task.create` / `task.start` / `task.pause` / `task.cancel` | C→S | 任务控制 |
| `task.progress` / `task.done` | S→C | 进度/结束 |
| `profile.list` / `profile.save` / `profile.apply` | C→S | Inference Profile |
| `project.open` / `project.save` | C→S | 项目 |
| `system.health` / `system.shutdown` | 双向 | 生命周期配合 |
| `log.message` | S→C | 日志 |
| `ping` / `pong` | 双向 | 心跳 |

后续：`video.*` `camera.*` `export.video` `repository.*` `track.*`。

### 7.3 日志双通道

loguru → 文件 `logs/` + WS `log.message`。级别 DEBUG~CRITICAL。

---

## 8. 项目系统

```
projects/<name>/
├── project.json          # 轻量：name/version/paths/last_opened
├── profiles/             # 可选 yaml
├── images/
├── videos/
├── models/
├── results/              # 媒体/mask/导出包
└── database.sqlite       # 权威数据
```

`project.json` 仅存「打开项目所需的最小元数据」；模型绑定、参数、结果、历史 → **SQLite**。

打开项目：挂载 DB → 恢复 profiles / 任务列表 / 模型绑定。

---

## 9. 视频导出设计（新增）

**输入**：`原视频` + `JSON/SQLite 结果` + `操作记录(ops)`  
**输出**：`合成视频（可选导出结果 JSON 包）`

```
videos/source.mp4
       │
       ▼
ExportPipeline
  1. 读视频流（opencv/ffmpeg 逐帧）
  2. 取该帧结果：frames + objects（按 skip/persistence 展开缓存帧）
  3. 叠加 ops：hide_object / modify_bbox / modify_style
  4. export/draw.py 绘制（与前端同一 label_template / 颜色 / 中文字体）
  5. 编码写出 outputs/xxx.mp4
       │
       └─► 可选：sidecar export.json（最终生效结果快照）
```

| 项 | 设计 |
|----|------|
| 任务类型 | `TaskType.EXPORT`（后台执行，进度推送） |
| 绘制 | 服务端统一 draw，保证与 UI 样式同源（读 Profile render） |
| 框缓存 | 按 `box_persistence` 将检测帧结果扩展到持续帧；超过 clamp |
| 操作记录 | 时间线应用：`ops` 按 frame_id 排序合并到对象状态机 |
| 可见性 | `visible=false` 的对象不绘制 |
| 编码 | 默认 H.264 (`libx264`)；fps 默认同源；分辨率可 1:1 或缩放 |
| 进度 | 按帧/总帧数推送 `task.progress` |
| 失败 | 缺帧/缺结果策略：跳过并 log，或 fail-fast（Profile 可配） |

WS：`export.video` / `task.progress`。详细协议见 `docs/EXPORT.md`（编码阶段补全）。

**P1 不做完整导出 UI**，但架构与任务类型、draw 模块、DB ops 表预留到位；导出实现放 P3。

---

## 10. 进程与运行时

### 10.1 生命周期（详见 §3.4）

- Electron Main 拥有 ProcessSupervisor
- 开发模式：可连接外部已启动 backend（`YOLO_STUDIO_ATTACH=1`）
- 生产模式：spawn venv python → `app.main`

### 10.2 配置

优先级：`环境变量 > config.yaml > 默认值`  
关键：`YOLO_STUDIO_ROOT`、host/port、models/repository/projects/logs 路径、python 解释器路径。

---

## 11. 安全与工程约束

1. Electron `contextIsolation: true`，`nodeIntegration: false`
2. WS 仅 `127.0.0.1`
3. 渲染层不直接碰文件系统
4. pydantic 校验入站消息
5. 模块 ≤ ~400 行；业务不进 `main.py`
6. Python type hints + TS strict
7. 推理必须 `BaseRuntime`
8. **SQLite 为权威存储；JSON 为交换/导出**
9. 路径 pathlib，禁止硬编码

---

## 12. 阶段路线图（v0.2）

| 阶段 | 内容 | 出口标准 |
|------|------|----------|
| **P1 骨架+多模型** | Electron 生命周期、Backend、WS、日志、Runtime、ModelManager、**多模型 Pipeline 基础**、Image/Folder、SQLite、Profile 基础、Konva、结果列表 | 多模型选图推理合并显示；参数可存 Profile |
| **P2 项目增强** | 完整项目 UI、Profile 管理 UI、结果编辑持久化、Repository 展示 | 项目打开恢复完整 |
| **P3 视频** | VideoTask、跳帧、框缓存、时间轴、ops、**视频导出** | 导出带框视频 |
| **P4 相机/流** | USB / RTSP、实时推理、录制 → VideoTask | 实时可用 |
| **P5 多后端** | ONNX / TensorRT / RKNN | 同 UI 切换后端 |
| **P6 高级** | Segment / Pose / OCR / Tracking / SAM | 多任务类型 |

---

## 13. 关键设计决策（ADR）

| # | 决策 | 理由 |
|---|------|------|
| D1 | Electron / Python 进程分离 + Supervisor | 职责清晰；生命周期可控 |
| D2 | WebSocket JSON | 可调试、可扩展 |
| D3 | Runtime 强制抽象 + Geometry 多态 | 多后端、多任务类型不重构 |
| D4 | SQLite 权威 + JSON 导出 | 可查询、可迁移、可读 |
| D5 | Profile 独立于 project.json | 参数可复用、任务可复现 |
| D6 | Pipeline P1 就做并行合并 | 需求要求多模型同时选择 |
| D7 | Model Repository 与 ModelManager 同构配置 | 内置模型不走特例 |
| D8 | 导出在服务端 draw | 与 UI 一致、无 Electron 渲染瓶颈 |
| D9 | 框缓存只存结果引用 | 内存可控 |
| D10 | 分后端 requirements | 依赖隔离 |

---

## 14. 第一阶段范围（摘要）

见 `docs/PHASE1.md`。P1 交付：

1. Electron 可运行且**自动拉起/监控 Backend**
2. FastAPI + WS + 日志双通道
3. Runtime 抽象 + YOLORuntime
4. ModelManager + YAML + 显示名映射
5. **多模型并行 Pipeline（合并结果）**
6. ImageTask / FolderTask + 进度/取消
7. **SQLite 基础表结构 + DAO**
8. **Inference Profile 保存/应用**
9. Konva 渲染 + 结果列表交互
10. 协议与类型定义

**P1 不含**：视频检测与导出 UI、摄像头、Tracking、非 YOLO 后端、模型下载。

---

## 15. 未来扩展重构风险检查（Review #7）

> 问题：直接上 Tracking / Segmentation / OCR / RK3588 / TensorRT 时，v0.1 有哪些地方会迫使重构？

| # | v0.1 风险点 | 后果 | v0.2 处置 | 状态 |
|---|-------------|------|-----------|------|
| R1 | `DetectObject` 只有 bbox | Segment mask / Pose / OCR text 都要改协议与 DB | `Geometry` 多态 + `geom_type/geom_json` | **已在 P1 稳固** |
| R2 | `track_id` 仅在 label 模板字符串出现 | Tracking 时对象身份、跨帧关联无处安放 | `ResultObject.track_id` 一等字段 + DB 列 | **已在 P1 预留** |
| R3 | 结果仅 JSON 文件 | 视频逐帧查询、ops 回放、导出 join 性能差 | SQLite 权威 schema | **已在 P1 建表** |
| R4 | 无 Profile，参数散落 | 换模型/复现实验困难；导出样式不一致 | Inference Profile | **已在 P1 基础实现** |
| R5 | Pipeline 只是草图且不在 P1 | 多模型需求落空；后续加级联会改 Task 形态 | P1 并行 Pipeline + Task 绑定 model_ids | **已纳入 P1** |
| R6 | Backend 启动未设计 | 打包后用户无法使用；Windows 进程残留 | ProcessSupervisor | **已在 P1 任务** |
| R7 | Runtime 只列 backend，未强调 ModelTaskType | yolo 做 segment/pose 时接口含糊 | `model_task` + 统一 `predict→ResultObject` | **接口已预留** |
| R8 | 导出未设计 | 视频导出时临时拼绘制，样式与 UI 不一致 | `export/` + ExportTask + ops 应用 | **设计已补，实现 P3** |
| R9 | 无模型包形态 | 官方模型靠手拷，路径硬编码 | Model Repository catalog/manifest | **结构已补，下载 P2+** |
| R10 | OCR/Track 无扩展点 | 塞进 YOLORuntime 会变上帝类 | OCRRuntime / Track 后处理节点；Pipeline 节点可插拔 | **注册表扩展** |

### 15.1 仍可接受的「阶段性欠账」（刻意不 P1 做完）

| 项 | 说明 | 何时做 |
|----|------|--------|
| mask 位图存储策略 | P1 只留 `mask_ref`，大 mask 压缩/差分后续 | Segment 落地时 |
| 跨模型 NMS | 默认 concat；规则引擎后置 | P2 |
| TensorRT engine 缓存目录约定 | 仅 requirements + Runtime 空位 | P5 |
| RKNN 量化/工具链文档 | 设备抽象已在 Runtime | P5 |
| Tracking 全局 ID 跨任务 | track_id 先帧内/视频任务内 | P6 |

### 15.2 结论

v0.2 在 **结果模型、存储、生命周期、Profile、Pipeline、导出、模型仓库** 七个点上消除了「加 Tracking/Seg/OCR/RKNN/TRT 必须大改」的结构风险。  
剩余工作属于**实现扩展**，不推翻数据与接口边界。

---

## 16. 附录：与 v0.1 差异清单

1. 新增 §0 Review 记录、§3.4 生命周期、§5.6 Profile、§5.7 Repository、§6.2 SQLite、§9 视频导出、§15 扩展风险
2. `DetectObject` → `ResultObject` + `Geometry`
3. 任务增加 `PIPELINE` / `EXPORT`，task 携带 `profile_id` / `model_ids`
4. 目录增加 `backend/app/export`、`model_manager/repository`、`electron/backend/supervisor`、`database/dao`
5. P1 范围调整：多模型 Pipeline、SQLite、Profile、生命周期进入 P1
6. 路线图重排（Pipeline 从 P2 提前）
