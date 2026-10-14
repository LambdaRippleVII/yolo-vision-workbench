# YOLO Vision Workbench · Implementation Design

> 版本：**v0.1**（详细实现设计，可直接指导编码）
> 依据：`docs/ARCHITECTURE_v0.2.md`、`docs/PHASE1_v0.2.md`
> 约束：**本阶段禁止编写代码**；本文只定义接口、结构、流程与规范
> 若与架构文档冲突，以本文「设计修正」章节为准，并回写架构

---

## 目录

1. [总体约定](#1-总体约定)
2. [Backend 核心模块](#2-backend-核心模块)
3. [数据库设计](#3-数据库设计)
4. [WebSocket 协议](#4-websocket-协议)
5. [Electron 前端设计](#5-electron-前端设计)
6. [数据库迁移](#6-数据库迁移)
7. [P1 开发顺序](#7-p1-开发顺序)
8. [代码开发规范](#8-代码开发规范)
9. [Implementation Risk Review](#9-implementation-risk-review)
10. [附录：设计修正与开放问题](#10-附录设计修正与开放问题)

---

## 1. 总体约定

### 1.1 职责硬边界

| 组件 | 允许 | 禁止 |
|------|------|------|
| Electron Renderer | UI、Canvas、状态、WS 客户端 | 调用模型、写 DB、直接 FS |
| Electron Main | 窗口、dialog、**Backend 进程生命周期** | 推理业务 |
| TaskManager | 任务生命周期、调度、进度 | 具体推理算法 |
| PipelineEngine | 多模型编排、合并 | 持久化细节、UI |
| InferenceSession | 会话内 Runtime/Model 绑定与缓存 | 跨会话全局策略（交给 ModelManager） |
| Runtime | load / unload / predict / 元数据 | 任务语义、DB |

**推理能力只经：`TaskManager → PipelineEngine → InferenceSession → Runtime`。**  
禁止旁路 `model.predict()`、禁止前端直连 YOLO。

### 1.2 调用链（编码时必须保持）

```
WS Handler
   │  校验 payload (pydantic)
   ▼
TaskManager.create(task_type, params, profile_id, model_ids)
   │
   ▼
Task.run()
   │  按 media 单元循环 (image / folder item / frame)
   ▼
InferenceSession.ensure_loaded(model_ids)   # 复用缓存
   │
   ▼
PipelineEngine.execute(session, image, model_ids)
   │     ├─ NodeRuntime(A) ─┐
   │     ├─ NodeRuntime(B) ─┼─► Merge → FrameResult
   │     └─ NodeRuntime(C) ─┘
   ▼
ResultStore.save(FrameResult)   # SQLite (权威)
   │
   ▼
WS push: detect.result / task.progress / task.done
```

### 1.3 全局 ID 与命名

| 实体 | ID 形态 | 示例 |
|------|---------|------|
| task_id | `t_` + ULID/UUID4 短形 | `t_01J8...` |
| session_id | `s_` + ULID | `s_01J8...` |
| model_id | YAML `id`（短英文） | `person` / `helmet` |
| media_id | `m_` + hash 前 12 位或 ULID | `m_a1b2c3...` |
| profile_id | slug 或 `p_` + ULID | `default` / `p_...` |
| package_id | repository 包名 | `coco-yolov8n` |

ULID：时间有序，便于 SQLite 排序；实现可用 `python-ulid` 或自写。

---

## 2. Backend 核心模块

### 2.1 TaskManager

#### 2.1.1 职责

- 创建 / 入队 / 启动 / 暂停 / 恢复 / 取消 / 完成 / 失败
- 进度聚合与事件推送
- 并发控制（P1：同一时刻 1 个重任务，可配置）
- 与 DB `tasks` 表同步
- 会话引用：任务持有 `session_id`（复用或独占）

#### 2.1.2 状态机

```
                 create
                   │
                   ▼
               PENDING ──────────────cancel────────────┐
                   │                                   │
                 start                                 │
                   │                                   ▼
                   ▼                               CANCELLED
                RUNNING ──complete──► COMPLETED        ▲
                   │  │                               │
                   │  └──fail──► FAILED               │
                   │                                  │
                pause│resume                          │
                   ▼                                  │
                 PAUSED ─────────────cancel───────────┘
```

| 状态 | 含义 | 允许迁移出 |
|------|------|------------|
| `pending` | 已创建未执行 | start / cancel |
| `running` | 执行中 | pause / complete / fail / cancel |
| `paused` | 已暂停（可恢复） | resume / cancel |
| `completed` | 成功结束 | （终态） |
| `failed` | 失败结束 | （终态；可 clone 新任务） |
| `cancelled` | 已取消 | （终态） |

非法迁移抛 `TaskStateError`，WS 返回 `error` 信封。

#### 2.1.3 Task 数据结构（逻辑模型）

```text
Task
├── task_id: str
├── type: TaskType                 # image | folder | video | stream | export | pipeline
├── status: TaskStatus
├── progress: float                # 0.0~1.0
├── progress_detail: dict          # {done, total, current_item, eta_ms}
├── params: dict                   # 见各 Task 子类
├── profile_id: str | null
├── model_ids: list[str]           # 参与 Pipeline 的模型
├── session_id: str | null
├── project_id: str                # 项目目录名/逻辑 id
├── error: str | null
├── result_ref: str | null         # 指向 results/task_id 或 export 路径
├── created_at: datetime
├── updated_at: datetime
├── finished_at: datetime | null
└── cancel_requested: bool         # 协作式取消标志
```

#### 2.1.4 任务子类 params 契约

**ImageTask**

```json
{
  "media_path": "projects/demo/images/a.jpg",
  "save_visualization": true,
  "profile_id": "default"
}
```

**FolderTask**

```json
{
  "folder_path": "projects/demo/images/batch1",
  "glob": "*.jpg;*.png",
  "recursive": true,
  "save_visualization": false,
  "fail_fast": false
}
```

**VideoTask**（P3，结构先定）

```json
{
  "media_path": "projects/demo/videos/demo.mp4",
  "skip_frame": 5,
  "box_persistence": 5,
  "start_frame": 0,
  "end_frame": null
}
```

**StreamTask**（P4）

```json
{
  "source": "rtsp://...",
  "source_type": "rtsp|usb",
  "device_index": 0,
  "skip_frame": 5,
  "box_persistence": 5,
  "record": true
}
```

**ExportTask**（P3）

```json
{
  "source_task_id": "t_...",
  "output_path": "projects/demo/exports/demo_out.mp4",
  "fps": 0,
  "draw": true,
  "codec": "h264"
}
```

**PipelineTask**（可选包装，P1 可用 Image/Folder + model_ids 替代）

```json
{
  "inner": { "type": "image", "media_path": "..." },
  "pipeline": { "model_ids": ["person","helmet"], "mode": "parallel", "merge": "concat" }
}
```

#### 2.1.5 创建任务流程（时序）

```
Client                WS Handler           TaskManager         DB
  │ detect.image          │                    │                │
  │──────────────────────►│                    │                │
  │                       │ validate schema    │                │
  │                       │───────────────────►│ create()       │
  │                       │                    │───────────────►│ INSERT tasks
  │                       │                    │ return task_id │
  │                       │◄───────────────────│                │
  │  task.created         │                    │                │
  │◄──────────────────────│                    │                │
  │                       │                    │ enqueue/start  │
  │  task.progress × N    │◄───────────────────│                │
  │◄──────────────────────│                    │ UPDATE progress│
  │  detect.result × N    │                    │                │
  │◄──────────────────────│                    │ save frames    │
  │  task.done            │                    │                │
  │◄──────────────────────│                    │ finish         │
```

同步接口（P1 允许）：小图 `detect.image` 可 **inline 完成**后直接 `detect.result` + `task.done`（同一 `id` 关联），仍写入 tasks 表以保证审计。

#### 2.1.6 暂停 / 取消机制

| 机制 | 设计 |
|------|------|
| 取消 | 协作式：`cancel_requested=True`；工作循环每 **单元**（图/帧）检查；检查点亦落 DB |
| 暂停 | `pause_requested`；仅对 folder/video 长任务；image 单图一般不暂停 |
| 恢复 | `resume` 清 pause 标志，从 `progress_detail.cursor` 继续 |
| 强制停止 | 进程级仅由 Supervisor 处理 backend 崩溃；任务层不 kill 线程 |

**工作循环伪流程（文档级）**

```
for item in items(cursor):
    if cancel_requested: → CANCELLED; break
    if pause_requested: → PAUSED; persist cursor; wait resume
    result = session.pipeline.execute(item.image)
    result_store.save(result)
    progress = (idx+1)/total
    emit task.progress
complete()
```

#### 2.1.7 任务恢复策略

| 场景 | 策略 |
|------|------|
| 正常暂停/恢复 | 内存态 + DB cursor；P1 同进程内恢复 |
| Backend 崩溃重启 | DB 中 `running` 任务标记为 `failed`（error=process_died）或 `interrupted` 新状态；**P1 选 failed+可重跑** |
| 应用退出 | 退出前 cancel 或持久化 cursor；P1：cancel 并标记 cancelled |
| 重跑 | `task.create` 新任务，可带 `params.retry_of=task_id` |
| 断点续跑 | **P2+**：`resume_from_cursor` 读 DB 继续；P1 不做自动 resume |

新增逻辑状态（写入 DB 仍用兼容枚举）：`interrupted` = 异常中断，界面显示可重跑。P1 可用 `failed` + error code `interrupted` 表达，避免过早扩状态机。

#### 2.1.8 Manager 对外接口（逻辑签名）

```text
create(type, params, profile_id, model_ids) -> Task
start(task_id) -> None
pause(task_id) -> None
resume(task_id) -> None
cancel(task_id) -> None
get(task_id) -> Task
list(status?, type?, limit?) -> list[Task]
on_progress(cb) / on_done(cb)   # 内部事件总线 → WS
```

并发：`max_concurrent_tasks` 默认 1；队列 FIFO。Session 池大小见 §2.3。

---

### 2.2 PipelineEngine

#### 2.2.1 为什么独立于 TaskManager

Task 关心「作业生命周期」；Pipeline 关心「单帧/单图上多模型如何算完」。  
未来级联、ROI、Tracking 节点都应插入 Pipeline，而不改 Task。

#### 2.2.2 结构

```
PipelineEngine
├── PipelineSpec
│   ├── mode: parallel | serial | cascade
│   ├── merge: concat | nms | rule
│   └── nodes: list[NodeSpec]
├── NodeSpec
│   ├── node_id: str
│   ├── kind: model | merge | roi | track | filter | custom
│   ├── model_id: str | null          # kind=model
│   ├── runtime_ref: session+model
│   ├── params: dict
│   ├── inputs: list[node_id]         # 级联用
│   └── enabled: bool
└── execute(image, ctx) -> FrameResult
```

**节点类型**

| kind | P1 | 说明 |
|------|----|------|
| `model` | ✓ | 调 InferenceSession 内 Runtime.predict |
| `merge` | ✓ | 合并多路 ResultObject |
| `filter` | ✓ | conf/class/visible 过滤（可后置） |
| `roi` | 后续 | 裁剪/放大区域推理 |
| `track` | 后续 | ByteTrack 等，写 track_id |
| `cascade` | 后续 | A 结果作为 B 输入 |

#### 2.2.3 并行推理（P1 必须）

```
Input Image
    │
    ├── NodeModel(person)  ──► Objects_A
    ├── NodeModel(helmet)  ──► Objects_B
    └── NodeModel(vest)    ──► Objects_C
    │
    ▼
NodeMerge(concat)
    │  - 扁平化列表
    │  - 帧内重新分配 object_id = 1..N
    │  - 保留 model_id
    │  - （可选）按 confidence 降序
    ▼
FrameResult
```

实现约束（设计层）：

- 并行度 ≤ `min(模型数, max_workers)`；`max_workers` 默认 4，可配
- 每模型独立 Runtime 实例，禁止共享非线程安全句柄
- 单节点异常 → 该节点 `objects=[]` + `meta.errors[node_id]`；默认不失败整帧
- `merge=nms` 仅接口预留，P1 实现 `concat`

#### 2.2.4 级联预留（不在 P1 实现）

```
[detector] → [roi crop] → [helmet_cls] → [merge]
     │                        │
     └──────── track ◄────────┘
```

`NodeSpec.inputs` + `mode=cascade` 已预留；执行器按 DAG 拓扑序运行。

#### 2.2.5 PipelineSpec 与 Profile 关系

Profile 中：

```yaml
pipeline:
  mode: parallel
  merge: concat
models:
  - model_id: person
    enabled: true
  - model_id: helmet
    enabled: true
```

**PipelineEngine.build_from_profile(profile)** → `PipelineSpec`。  
任务 params 可临时覆盖（如只跑单模型）。

#### 2.2.6 对外接口

```text
build_from_profile(profile: Profile) -> PipelineSpec
build_from_model_ids(model_ids: list[str], mode=parallel) -> PipelineSpec
execute(spec: PipelineSpec, image: ndarray, session: InferenceSession) -> FrameResult
estimate_cost(spec) -> dict   # 可选，调试用
```

---

### 2.3 InferenceSession

#### 2.3.1 为什么需要 Session

| 问题 | Session 如何解决 |
|------|------------------|
| 任务与模型生命周期不同 | Session 持有已加载 Runtime，任务结束不一定卸载 |
| 多任务复用同一模型 | Session 缓存 + refcount；避免重复 load（torch 权重加载昂贵） |
| 帧上下文（skip/persistence/ops） | Session 内 FrameContext，不污染全局 |
| 设备/线程亲和 | Session 绑定 device 与 predict 串行锁 |
| 可测试 | Mock Session 注入 Pipeline |

**关系**

```
ModelManager (全局):  扫描配置、仓库、元数据、LRU 池
      ▲
      │ load/unload 策略
InferenceSession (项目/任务级):  绑定 model_id → Runtime 实例、缓存、FrameContext
      ▲
      │
PipelineEngine / Task
```

- **ModelManager**：进程级单例，回答「模型是否可用、class 映射、配置」
- **InferenceSession**：一次推理工作上下文（可跨任务复用，P1 按 project 默认复用）

#### 2.3.2 结构

```text
InferenceSession
├── session_id: str
├── project_id: str
├── device: str                    # cpu / cuda:0 ...
├── bindings: dict[model_id, ModelBinding]
│     ├── runtime: BaseRuntime
│     ├── config: ModelConfig
│     ├── refcount: int
│     └── last_used_at: datetime
├── frame_ctx: FrameContext
├── predict_locks: dict[model_id, Lock]
└── closed: bool
```

```text
FrameContext
├── frame_id: int
├── skip_frame: int
├── box_persistence: int           # clamp 到 skip_frame
├── boxes_cache: dict[model_id, list[ResultObject]]
├── last_detect_frame: dict[model_id, int]
└── ops_overlay: list[Op]          # 视频编辑覆盖层（P3）
```

**boxes_cache 规则（偏好对齐）**

- 仅在 `frame_id % skip_frame == 0` 时 predict
- 其余帧使用 cache 渲染
- `box_persistence > skip_frame` 时自动 = `skip_frame`
- cache 存 ResultObject/结果引用，**不存图像**

#### 2.3.3 生命周期

```
create(project_id, device)
    │
    ▼
bind(model_id) ──► ModelManager.resolve → RuntimeFactory.create → load()
    │
    ▼
predict_ready()   # 所有 bound models 就绪
    │
    ├─► execute 可多次
    ├─► rebind / unbind
    │
    ▼
close()
    │  refcount==0 的 runtime unload
    └─ 释放 frame_ctx
```

| 事件 | 行为 |
|------|------|
| `bind` 已存在 | refcount++，不重复 load |
| `unbind` | refcount--，为 0 可选 idle 卸载 |
| `close` | 全部 unload；标记 closed 后 predict 抛 `SessionClosed` |
| 全局 LRU 压力 | ModelManager 可要求某 Session 释放 idle binding |

P1 默认：**进程内单 Session per project**，简化管理；接口仍按多 Session 设计。

#### 2.3.4 接口

```text
bind(model_ids: list[str]) -> None
unbind(model_ids: list[str]) -> None
predict(model_id, image) -> list[ResultObject]      # 单模型
predict_pipeline(spec, image) -> FrameResult        # 常用快捷方式
reset_frame_context() -> None
snapshot_classes(model_id) -> list[ClassInfo]
close() -> None
stats() -> dict   # load 次数、predict 耗时均值
```

`predict_pipeline` 内部调 PipelineEngine，保证 Task 与交互式单图一致。

---

### 2.4 Runtime 抽象

#### 2.4.1 BaseRuntime 接口

```text
BaseRuntime
├── properties
│   ├── backend_type: BackendType          # yolo|onnx|tensorrt|rknn
│   ├── model_task: ModelTaskType          # detect|segment|pose|ocr|track
│   ├── device: str
│   └── is_loaded: bool
├── methods
│   ├── load_model(model_path, config) -> None
│   ├── unload_model() -> None
│   ├── predict(image: ndarray) -> list[ResultObject]
│   ├── get_classes() -> list[str]         # 原始 class 名
│   ├── get_class_display_map() -> dict    # 可选，也可由 ModelManager 提供
│   └── warmup(iterations=1) -> None       # 可选
└── errors
    ├── ModelLoadError
    ├── PredictError
    └── DeviceUnavailableError
```

**约定**

- `predict` 输入 BGR ndarray（OpenCV 约定），与颜色空间转换封装在 Runtime 内
- `predict` **线程安全**：同实例串行（Session 持锁）；不同实例可并行
- 输出已是 `ResultObject`（含 Geometry），Runtime 内完成原生后处理
- `class_name` 为权重内原始名；`display_name` 可由 ModelManager 注入 config 后填充

#### 2.4.2 各后端实现要点

| 后端 | load_model | predict | get_classes | 设备/备注 |
|------|------------|---------|-------------|-----------|
| **PyTorch / ultralytics** | `YOLO(weights)` 或 `torch.hub`；记录 `model.names` | `model.predict(..., verbose=False)` → 后处理为 ResultObject | `model.names` | `device` cpu/cuda；AMP 可选 |
| **ONNXRuntime** | `InferenceSession(model)`，providers 按 device | 预处理 → `run` → decode（NMS） | 从 config yaml 或 metadata 读 | CPU/CUDA EP；动态 shape |
| **TensorRT** | 加载 `.engine`，create context | 异步/同步 execute + 后处理 | 同 ONNX 侧车文件 | 需 CUDA；engine 与 GPU 架构绑定 |
| **RKNN** | `rknn_lite` / `rknn-toolkit2` load | `inference` → NCHW/NHWC 约定 | 模型侧 meta yaml | RK3588；不跨设备直接跑 |

**扩展检查单（新后端）**

1. 实现 `BaseRuntime`
2. `registry.register(BackendType.XXX, XRuntime)`
3. `requirements/<backend>.txt`
4. 文档补充 device 限制
5. **不改** Task / Pipeline / Session / WS 协议

#### 2.4.3 Factory 与 Registry

```text
RuntimeRegistry
  register(backend_type, factory: Callable[[device], BaseRuntime])
  create(backend_type, device) -> BaseRuntime

RuntimeFactory
  create_from_config(ModelConfig) -> BaseRuntime
  # 内部：registry.create + load_model
```

---

### 2.5 模块文件映射（指导编码落点）

```
backend/app/
├── task/
│   ├── base.py            # Task dataclass / enums / state machine
│   ├── manager.py         # TaskManager
│   ├── image_task.py
│   ├── folder_task.py
│   ├── video_task.py      # P3 可先 stub
│   ├── stream_task.py     # P4 stub
│   └── export_task.py     # P3 stub
├── inference/
│   ├── base.py            # Geometry / ResultObject / BaseRuntime
│   ├── factory.py
│   ├── pipeline.py        # PipelineEngine / NodeSpec
│   ├── session.py         # InferenceSession / FrameContext
│   ├── postprocess.py
│   └── yolo_runtime.py
├── runtime/registry.py
├── model_manager/
│   ├── loader.py
│   ├── scanner.py
│   ├── metadata.py
│   ├── config_schema.py
│   └── repository.py
└── ...
```

---

## 3. 数据库设计

### 3.1 原则

1. **SQLite 为项目权威数据源**；JSON 仅导出/交换/备份
2. 每项目一库：`projects/<project>/database.sqlite`
3. Geometry 用 `geom_type + geom_json`，避免过早分表
4. 所有时间 `TEXT` ISO-8601 UTC（或统一 local，需全局一致；**推荐 UTC**）
5. 布尔用 `INTEGER 0/1`
6. 外键开启：`PRAGMA foreign_keys=ON`
7. WAL 模式

### 3.2 ER 概览

```
project_meta
profiles ────────────┐
                     ▼
tasks ──┬── media
        ├── frames ── objects
        └── ops
models (注册/缓存，可多项目共享副本或每库一份)
```

### 3.3 表定义

#### 3.3.1 `project_meta`

| 字段 | 类型 | 约束 | 用途 |
|------|------|------|------|
| key | TEXT | PK | 配置键 |
| value | TEXT | NOT NULL | JSON 或字符串 |
| updated_at | TEXT | NOT NULL | 更新时间 |

用途：schema 版本、项目名、创建时间、last_task_id 等。

#### 3.3.2 `projects`（可选逻辑表）

> 若「一项目一库」，本表可只存当前项目一行；**仍保留**以便未来单库多项目。

| 字段 | 类型 | 约束 | 用途 |
|------|------|------|------|
| project_id | TEXT | PK | 项目 ID |
| name | TEXT | NOT NULL | 显示名 |
| root_path | TEXT | NOT NULL | 根路径（相对/绝对） |
| created_at | TEXT | NOT NULL | |
| updated_at | TEXT | NOT NULL | |
| description | TEXT | | |

#### 3.3.3 `models`（模型注册）

| 字段 | 类型 | 约束 | 用途 |
|------|------|------|------|
| model_id | TEXT | PK | YAML id |
| name | TEXT | NOT NULL | 显示名 |
| backend | TEXT | NOT NULL | yolo/onnx/tensorrt/rknn |
| task_type | TEXT | NOT NULL | detect/segment/pose/ocr/track |
| model_path | TEXT | NOT NULL | 权重路径 |
| config_path | TEXT | | YAML 路径 |
| package_id | TEXT | | repository 包 |
| version | TEXT | | 版本 |
| class_map_json | TEXT | | class_display 映射 |
| default_params_json | TEXT | | conf/iou/device 等 |
| source | TEXT | | local / repository / user |
| enabled | INTEGER | NOT NULL DEFAULT 1 | |
| created_at | TEXT | NOT NULL | |
| updated_at | TEXT | NOT NULL | |

用途：项目内模型清单快照；Repository 启用时写入；可复现历史任务。

#### 3.3.4 `profiles`

| 字段 | 类型 | 约束 | 用途 |
|------|------|------|------|
| profile_id | TEXT | PK | |
| name | TEXT | NOT NULL | |
| description | TEXT | | |
| payload_json | TEXT | NOT NULL | 完整 Profile JSON |
| is_default | INTEGER | NOT NULL DEFAULT 0 | |
| created_at | TEXT | NOT NULL | |
| updated_at | TEXT | NOT NULL | |

`payload_json` 结构见 ARCHITECTURE §5.6（models/pipeline/runtime/render/export）。

#### 3.3.5 `tasks`

| 字段 | 类型 | 约束 | 用途 |
|------|------|------|------|
| task_id | TEXT | PK | |
| type | TEXT | NOT NULL | image/folder/video/stream/export/pipeline |
| status | TEXT | NOT NULL | pending/running/paused/completed/failed/cancelled |
| progress | REAL | NOT NULL DEFAULT 0 | 0~1 |
| progress_detail_json | TEXT | | done/total/cursor |
| params_json | TEXT | NOT NULL | 任务参数 |
| profile_id | TEXT | FK→profiles | |
| session_id | TEXT | | |
| project_id | TEXT | | |
| error | TEXT | | |
| error_code | TEXT | | 如 interrupted |
| result_ref | TEXT | | |
| parent_task_id | TEXT | | export 的 source |
| created_at | TEXT | NOT NULL | |
| updated_at | TEXT | NOT NULL | |
| finished_at | TEXT | | |

索引：`status`、`type`、`created_at`。

#### 3.3.6 `media`

| 字段 | 类型 | 约束 | 用途 |
|------|------|------|------|
| media_id | TEXT | PK | |
| task_id | TEXT | NOT NULL, FK→tasks | |
| kind | TEXT | NOT NULL | image/video/frame/stream |
| path | TEXT | NOT NULL | 相对项目根 |
| width | INTEGER | | |
| height | INTEGER | | |
| fps | REAL | | 视频 |
| frame_count | INTEGER | | 视频 |
| duration_ms | INTEGER | | |
| sha256 | TEXT | | 去重/校验 |
| created_at | TEXT | NOT NULL | |

索引：`task_id`。

#### 3.3.7 `frames`

| 字段 | 类型 | 约束 | 用途 |
|------|------|------|------|
| task_id | TEXT | PK(1), FK→tasks | |
| frame_id | INTEGER | PK(2) | 图片可用 0；视频为帧号 |
| media_id | TEXT | FK→media | |
| infer_ms | REAL | | |
| pipeline_ms | REAL | | |
| is_detect_frame | INTEGER | | 是否真实推理帧（skip） |
| meta_json | TEXT | | |
| created_at | TEXT | NOT NULL | |

#### 3.3.8 `objects`（VisionObject）

| 字段 | 类型 | 约束 | 用途 |
|------|------|------|------|
| task_id | TEXT | PK(1), FK→frames | |
| frame_id | INTEGER | PK(2) | |
| object_id | INTEGER | PK(3) | 帧内 id |
| model_id | TEXT | PK(4) | 来源模型（合并后区分） |
| class_id | INTEGER | NOT NULL | |
| class_name | TEXT | NOT NULL | **原始名** |
| display_name | TEXT | | 渲染名（可中文） |
| confidence | REAL | NOT NULL | |
| **geom_type** | TEXT | NOT NULL | `bbox` \| `mask` \| `keypoints` \| `polygon` \| `text` |
| **geom_json** | TEXT | NOT NULL | Geometry 序列化 |
| **track_id** | INTEGER | | Tracking；P1 NULL |
| visible | INTEGER | NOT NULL DEFAULT 1 | |
| style_json | TEXT | | color/line_width/label |
| extra_json | TEXT | | OCR 全文、质量分等 |
| created_at | TEXT | NOT NULL | |
| updated_at | TEXT | NOT NULL | | 用户编辑后 |

索引：

- `objects(task_id, frame_id)`
- `objects(model_id)`
- `objects(track_id)`（P6 Tracking 查询）

**Geometry JSON 契约（geom_json）**

```json
// type=bbox
{ "bbox": [x1, y1, x2, y2] }

// type=mask
{ "bbox": [x1,y1,x2,y2], "mask_ref": "results/t_x/masks/f100_o1.png", "rle": null }

// type=polygon
{ "bbox": [...], "points": [[x,y], ...] }

// type=keypoints
{ "bbox": [...], "keypoints": [{"name":"nose","x":1,"y":2,"v":2}, ...] }

// type=text
{ "bbox": [...], "text": "ABC-123", "text_conf": 0.9, "lines": null }
```

设计意图：**加 mask/keypoints/text 不改表结构**，只扩 JSON 契约与渲染。

#### 3.3.9 `ops`（操作记录）

| 字段 | 类型 | 约束 | 用途 |
|------|------|------|------|
| op_id | INTEGER | PK AUTOINCREMENT | |
| task_id | TEXT | NOT NULL, FK→tasks | |
| frame_id | INTEGER | | 可空=任务级 |
| action | TEXT | NOT NULL | hide_object/show_object/modify_bbox/modify_style/modify_class/delete_object/add_object |
| target_type | TEXT | | object/frame/task |
| target_id | TEXT | | object_id 或空 |
| payload_json | TEXT | NOT NULL | 变更前后或 delta |
| actor | TEXT | | user/system/export |
| created_at | TEXT | NOT NULL | |

索引：`(task_id, frame_id)`、`(task_id, created_at)`。

#### 3.3.10 `sessions`（可选，P1 可内存）

| 字段 | 类型 | 约束 | 用途 |
|------|------|------|------|
| session_id | TEXT | PK | |
| project_id | TEXT | | |
| device | TEXT | | |
| state | TEXT | | open/closed |
| created_at | TEXT | | |
| closed_at | TEXT | | |

### 3.4 推荐 PRAGMA / 连接

```text
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
PRAGMA synchronous=NORMAL;
busy_timeout=5000
```

写路径串行（单写队列），读可多连接。

---

## 4. WebSocket 协议

### 4.1 连接建立

**URL**：`ws://127.0.0.1:{port}/ws`  
**握手后（S→C）**：

```json
{
  "type": "system.hello",
  "id": null,
  "data": {
    "server_version": "0.1.0",
    "protocol_version": 1,
    "pid": 12345,
    "features": ["image", "folder", "pipeline", "profile"]
  },
  "ts": 1711526400123
}
```

**客户端应答（可选）**

```json
{ "type": "system.hello_ack", "id": "c1", "data": { "client_version": "0.1.0" }, "ts": 0 }
```

### 4.2 信封规范

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| type | string | 是 | `domain.action` |
| id | string\|null | 否 | 请求关联；响应带同一 id |
| data | object | 是 | 负载 |
| ts | number | 是 | epoch ms |
| error | object\|null | 否 | 失败时：`{code,message,detail}` |

**响应约定**：`type` = 请求 type 或 `*.ok` / `*.error`；推荐 **同 type + error 字段** 或显式 `task.done`。

统一成功/失败示例：

```json
{ "type": "model.load", "id": "r1", "data": { "ok": true, "model": { "...": "..." } }, "ts": 1 }
{ "type": "model.load", "id": "r1", "data": { "ok": false }, "error": { "code": "MODEL_NOT_FOUND", "message": "..." }, "ts": 2 }
```

### 4.3 心跳

```json
// C→S
{ "type": "ping", "id": "p1", "data": {}, "ts": 1711526400000 }

// S→C
{ "type": "pong", "id": "p1", "data": { "server_ts": 1711526400001 }, "ts": 1711526400001 }
```

客户端每 15s ping；30s 无 pong 视为断线并重连。

### 4.4 模型加载

**Request**

```json
{
  "type": "model.load",
  "id": "r10",
  "data": {
    "model_ids": ["person", "helmet"],
    "device": "cpu",
    "project_id": "demo"
  },
  "ts": 1711526400000
}
```

**Response**

```json
{
  "type": "model.load",
  "id": "r10",
  "data": {
    "ok": true,
    "models": [
      {
        "model_id": "person",
        "backend": "yolo",
        "task": "detect",
        "classes": [
          { "class_id": 0, "class_name": "person", "display_name": "人员" }
        ],
        "render": { "color": "#FF3B30", "line_width": 2, "label_template": "{id}:{class}" }
      }
    ]
  },
  "ts": 1711526400800
}
```

**model.list**

```json
// Req
{ "type": "model.list", "id": "r1", "data": { "include_repository": true }, "ts": 1 }

// Resp
{
  "type": "model.list",
  "id": "r1",
  "data": {
    "ok": true,
    "models": [
      {
        "model_id": "person",
        "name": "人员检测",
        "backend": "yolo",
        "task": "detect",
        "source": "local",
        "enabled": true
      }
    ]
  },
  "ts": 2
}
```

### 4.5 图片推理（单图 / 多模型）

**Request**

```json
{
  "type": "detect.image",
  "id": "r20",
  "data": {
    "project_id": "demo",
    "media_path": "images/a.jpg",
    "model_ids": ["person", "helmet"],
    "profile_id": "default",
    "overrides": { "conf": 0.5 },
    "inline": true
  },
  "ts": 1711526400000
}
```

**Response（inline=true，完成后一次回）**

```json
{
  "type": "detect.result",
  "id": "r20",
  "data": {
    "ok": true,
    "task_id": "t_01J8",
    "frame": {
      "frame_id": 0,
      "media_path": "images/a.jpg",
      "objects": [
        {
          "id": 1,
          "model_id": "person",
          "class_id": 0,
          "class_name": "person",
          "display_name": "人员",
          "confidence": 0.95,
          "geom_type": "bbox",
          "geom": { "bbox": [120.5, 80.2, 340.0, 520.8] },
          "track_id": null,
          "visible": true,
          "style": { "color": "#FF3B30", "line_width": 2 }
        },
        {
          "id": 2,
          "model_id": "helmet",
          "class_id": 0,
          "class_name": "helmet",
          "display_name": "安全帽",
          "confidence": 0.88,
          "geom_type": "bbox",
          "geom": { "bbox": [200.0, 40.0, 260.0, 100.0] },
          "track_id": null,
          "visible": true,
          "style": { "color": "#34C759", "line_width": 2 }
        }
      ],
      "meta": { "infer_ms": 42.1, "models": ["person", "helmet"] }
    }
  },
  "ts": 1711526400400
}
```

**Folder 异步**：先 `task.created`，再 `detect.result` 多条，最后 `task.done`。

### 4.6 视频任务（协议先定，P3 实现）

```json
// C→S
{
  "type": "video.start",
  "id": "r30",
  "data": {
    "project_id": "demo",
    "media_path": "videos/demo.mp4",
    "model_ids": ["person"],
    "skip_frame": 5,
    "box_persistence": 5,
    "profile_id": "default"
  },
  "ts": 1
}

// S→C 进度与结果
{
  "type": "task.progress",
  "id": null,
  "data": {
    "task_id": "t_vid",
    "progress": 0.25,
    "detail": { "frame_id": 150, "total_frames": 600 }
  },
  "ts": 2
}

{
  "type": "detect.result",
  "id": null,
  "data": {
    "task_id": "t_vid",
    "frame": {
      "frame_id": 150,
      "is_detect_frame": true,
      "objects": [ ... ]
    }
  },
  "ts": 3
}
```

**控制**

```json
{ "type": "task.pause", "id": "r31", "data": { "task_id": "t_vid" }, "ts": 4 }
{ "type": "task.resume", "id": "r32", "data": { "task_id": "t_vid" }, "ts": 5 }
{ "type": "task.cancel", "id": "r33", "data": { "task_id": "t_vid" }, "ts": 6 }
{ "type": "video.seek", "id": "r34", "data": { "task_id": "t_vid", "frame_id": 100 }, "ts": 7 }
```

### 4.7 摄像头任务（协议先定，P4 实现）

```json
{
  "type": "camera.open",
  "id": "r40",
  "data": {
    "project_id": "demo",
    "source_type": "usb",
    "device_index": 0,
    "model_ids": ["person"],
    "skip_frame": 3,
    "box_persistence": 3
  },
  "ts": 1
}

// 流式帧（可节流）
{
  "type": "stream.frame",
  "id": null,
  "data": {
    "task_id": "t_cam",
    "frame_id": 12,
    "jpeg_b64": "<optional preview>",
    "objects": [ ... ]
  },
  "ts": 2
}

{ "type": "camera.record_start", "id": "r41", "data": { "task_id": "t_cam" }, "ts": 3 }
{ "type": "camera.close", "id": "r42", "data": { "task_id": "t_cam" }, "ts": 4 }
```

P1 只保证 type 预留与文档；不实现。

### 4.8 任务进度

```json
{
  "type": "task.progress",
  "id": null,
  "data": {
    "task_id": "t_01J8",
    "status": "running",
    "progress": 0.5,
    "detail": { "done": 5, "total": 10, "current_item": "images/005.jpg" }
  },
  "ts": 1711526400500
}
```

```json
{
  "type": "task.done",
  "id": null,
  "data": {
    "task_id": "t_01J8",
    "status": "completed",
    "progress": 1.0,
    "summary": { "images": 10, "objects": 35 },
    "error": null
  },
  "ts": 1711526400900
}
```

### 4.9 日志推送

```json
{
  "type": "log.message",
  "id": null,
  "data": {
    "level": "INFO",
    "message": "model person loaded",
    "logger": "model_manager",
    "extra": { "model_id": "person" },
    "ts_text": "2026-03-27 12:00:00.123"
  },
  "ts": 1711526400123
}
```

级别：`DEBUG|INFO|WARNING|ERROR|CRITICAL`。高频可采样（例如 DEBUG 合并）。

### 4.10 错误处理

| code | HTTP 类比 | 场景 |
|------|-----------|------|
| `BAD_REQUEST` | 400 | schema 失败 |
| `UNAUTHORIZED` | 401 | 本地 token（若启用） |
| `NOT_FOUND` | 404 | 模型/任务/项目不存在 |
| `MODEL_NOT_FOUND` | 404 | |
| `MODEL_LOAD_FAILED` | 500 | |
| `TASK_STATE_ERROR` | 409 | 非法状态迁移 |
| `TASK_NOT_FOUND` | 404 | |
| `MEDIA_NOT_FOUND` | 404 | |
| `INFERENCE_ERROR` | 500 | predict 失败 |
| `DEVICE_UNAVAILABLE` | 503 | |
| `INTERNAL` | 500 | 未知 |

```json
{
  "type": "detect.image",
  "id": "r20",
  "data": { "ok": false },
  "error": {
    "code": "MODEL_LOAD_FAILED",
    "message": "failed to load weights",
    "detail": { "model_id": "person", "path": "..." }
  },
  "ts": 1
}
```

**WS 断线**：客户端指数退避重连；重连后 `system.hello`，UI 显示 backend 状态；进行中任务由 Backend 继续，客户端可 `task.list` 对齐状态（P1 用本地缓存 + hello 后全量 query）。

---

## 5. Electron 前端设计

### 5.1 全局 Layout

```
┌──────────────────────────────────────────────────────────┐
│ TitleBar / AppHeader          [Backend: 就绪 ●] [项目名]  │
├───────────┬──────────────────────────────────┬───────────┤
│ Sidebar   │ Main Workspace                   │ Inspector │
│           │  （路由页 + 画布/表格）            │ (可选右栏) │
│ · 项目    │                                  │ 属性/参数 │
│ · 图片    │                                  │           │
│ · 视频    │                                  │           │
│ · 摄像头  │                                  │           │
│ · 模型    │                                  │           │
│ · 设置    │                                  │           │
├───────────┴──────────────────────────────────┴───────────┤
│ Console：Logs / Tasks  （可折叠）                          │
└──────────────────────────────────────────────────────────┘
```

**布局组件**

| 组件 | 职责 |
|------|------|
| `AppShell.vue` | 整体栅格 |
| `AppHeader.vue` | 项目切换、Backend 状态、连接延迟 |
| `SideNav.vue` | 路由导航 |
| `ConsoleDock.vue` | 日志/任务 Tab，可折叠 |
| `Workspace.vue` | `<router-view>` 主区 |

### 5.2 页面

#### 5.2.1 项目管理 `views/project/`

| 组件 | 说明 |
|------|------|
| `ProjectListView.vue` | 最近项目列表 |
| `ProjectCreateDialog.vue` | 新建（名称/路径） |
| `ProjectOpenPanel.vue` | 打开/切换 |

- **Store**：`projectStore`（current、recent、dirty）
- **API**：`project.open` / `project.create` / `project.save` / `project.list`
- **状态**：打开后写入 localStorage 最近列表；切换时 `session` 重置

#### 5.2.2 图片检测 `views/image/`

| 组件 | 说明 |
|------|------|
| `ImageWorkbench.vue` | 页容器 |
| `MediaPicker.vue` | 选图/文件夹 |
| `ModelSelectPanel.vue` | 多模型勾选、conf、classes |
| `ProfileBar.vue` | Profile 选择/保存 |
| `CanvasStage.vue` | Konva 底图+overlay |
| `ResultList.vue` | 对象列表 |
| `InferToolbar.vue` | 开始/进度 |

- **Store**：`modelStore` / `detectStore`（currentResult、selection、visibility）/ `profileStore` / `taskStore`
- **API**：`model.list` `model.load` `detect.image` `detect.folder` `profile.*`
- **交互**：列表点击 → 高亮；眼睛图标 → `visible` 同步（本地优先，P1 可暂不写回 DB，P2 写回 ops）

#### 5.2.3 视频检测 `views/video/`（P3）

`VideoWorkbench.vue` / `Timeline.vue` / `VideoPlayer.vue`（Video.js）/ `OpsList.vue`  
Store：`videoStore`；API：`video.start` `task.pause` `video.seek`。

#### 5.2.4 摄像头 `views/camera/`（P4）

`CameraWorkbench.vue` / `SourceConfig.vue` / `PreviewCanvas.vue`。

#### 5.2.5 模型管理 `views/models/`

| 组件 | 说明 |
|------|------|
| `ModelListPage.vue` | 本地 + repository |
| `ModelDetailDrawer.vue` | class 映射、render、路径 |
| `RepositoryPanel.vue` | 官方包（P1 只读） |

- **API**：`model.list` `model.load` `model.unload`（repository 下载 P2+）

#### 5.2.6 设置 `views/settings/`

`SettingsPage.vue`：Backend 路径、端口、日志级别、设备、主题。  
存 `settingsStore` + 本地配置文件（经主进程 IPC 或 backend config API）。

### 5.3 状态管理（Pinia 模块）

| Store | State（摘要） | Actions |
|-------|---------------|---------|
| `backendStatus` | connecting/ready/error, latency, restarts | bind WS events |
| `projectStore` | currentProject, recent | open/create |
| `modelStore` | models[], loaded[], classesByModel | list/load/unload |
| `profileStore` | profiles[], activeId | list/save/apply |
| `taskStore` | tasks[], activeTask | create/progress/cancel |
| `detectStore` | resultByMedia, selection, visibility | setResult/toggleVisible |
| `logStore` | entries[], filterLevel | append/clear |
| `uiStore` | layout, consoleOpen | — |

### 5.4 与 Backend 通信接口（前端 API 层）

```
src/api/
├── ws.ts           # 连接、重连、心跳、request(type,data)->Promise
├── protocol.ts     # TS 类型（与 §4 对齐）
├── methods/
│   ├── models.ts
│   ├── detect.ts
│   ├── tasks.ts
│   ├── profiles.ts
│   ├── project.ts
│   └── system.ts
└── events.ts       # onDetectResult / onProgress / onLog
```

约定：所有 request 带 `id`，Promise 在响应 `id` 匹配时 resolve/reject；事件型消息走 `events.ts` 订阅。

### 5.5 主进程相关

```
electron/
├── main.ts
├── preload.ts          # contextBridge: dialog, app paths, backend status
├── backend/supervisor.ts
└── ipc/dialog.ts       # openImage / openFolder / openVideo / savePath
```

---

## 6. 数据库迁移

### 6.1 机制

| 项 | 设计 |
|----|------|
| 版本表 | `schema_migrations (version INTEGER PK, name TEXT, applied_at TEXT)` |
| 当前版本 | `project_meta.key = 'schema_version'` 同步冗余（便于日志） |
| 文件 | `backend/app/database/migrations/0001_init.sql`, `0002_xxx.sql` |
| 执行 | 打开项目时 head-upgrade：比较 `user_version` / migrations 表 |
| 校验 | 每份 migration 附 `CHECK` 说明；失败回滚事务 |
| 兼容 | **只向前迁移**；旧库升级不丢数据；不支持降级（文档写明） |

**PRAGMA `user_version`** 作为快速版本号，与 `schema_migrations` 一致。

### 6.2 策略

```
open_project()
  → connect sqlite
  → read user_version
  → if 0 and empty: apply all migrations
  → if 0 < v < latest: apply pending in order
  → if v > latest: 明确报错（应用过旧）
  → sanity check: 必要表存在
```

### 6.3 示例迁移脚本（文档级，非代码交付）

**0001_init**：创建 §3 全部表 + 索引 + version=1。

**0002_add_tracking_fields**（未来 v2）

```text
-- 目标：Tracking 支持
ALTER TABLE objects ADD COLUMN track_id INTEGER;
CREATE INDEX idx_objects_track ON objects(track_id);
-- frames 可增加 track 字段：ALTER TABLE frames ADD COLUMN track_meta_json TEXT;
-- user_version = 2
```

旧项目：列默认 NULL，查询兼容；**无需重建 objects**。

**0003_mask_storage**（未来）

```text
-- mask 已在 geom_json.mask_ref；若需独立表：
CREATE TABLE object_masks (
  task_id TEXT, frame_id INTEGER, object_id INTEGER, model_id TEXT,
  encoding TEXT,      -- png_path | rle
  data TEXT,
  PRIMARY KEY (task_id, frame_id, object_id, model_id),
  FOREIGN KEY ... REFERENCES objects ...
);
-- user_version = 3
```

**0004_indexes_perf** 等按需。

### 6.4 兼容规则（编码强制）

1. 新增列必须 **可空或有默认值**
2. 禁止改列语义导致旧数据误读；改语义用新列 + 双写过渡
3. 枚举值只追加
4. geom_json 契约只增不改必填
5. 每个 release 记录 migration 编号

---

## 7. P1 开发顺序

> 将 `PHASE1_v0.2.md` 18 卡收敛为 **5 个开发阶段**，每阶段有目标/输入/输出/验收。

### Phase A · 基础通信与骨架

| 项 | 内容 |
|----|------|
| **目标** | 双端可启动、可连通、可看日志 |
| **输入** | ARCHITECTURE_v0.2、IMPLEMENTATION_DESIGN_v0.1、空仓库 |
| **输出** | 目录骨架；backend `/health`；WS hello/ping；loguru 双通道；Electron 壳 + Supervisor 拉起 backend |
| **覆盖卡** | P1-01, P1-02, P1-04, P1-05, P1-12, P1-17(部分) |
| **验收** | ① 仅启 Electron 后 Backend 自动就绪 ② WS ping/pong ③ UI 日志有输出 ④ 杀 python 能自动重启 ⑤ 退出无残留进程 |

### Phase B · 数据与模型底座

| 项 | 内容 |
|----|------|
| **目标** | SQLite + Model 体系可编程调用 |
| **输入** | Phase A |
| **输出** | migrations 0001；DAO；Model YAML；Repository 只读；Runtime 抽象 + YOLORuntime；ModelManager；InferenceSession 基础 |
| **覆盖卡** | P1-03, P1-06, P1-07, P1-11(部分) |
| **验收** | ① 建库建表 ② DAO 单测通过 ③ load 模型返回 class 映射 ④ 上层无 `model.predict` ⑤ Session bind/predict/close 单测 |

### Phase C · Pipeline / Profile / Task

| 项 | 内容 |
|----|------|
| **目标** | 多模型推理闭环（无 UI） |
| **输入** | Phase B |
| **输出** | PipelineEngine parallel+merge；Inference Profile CRUD；TaskManager + Image/Folder；结果写 frames/objects |
| **覆盖卡** | P1-08, P1-09, P1-10, P1-11 |
| **验收** | ① 2 模型合并 FrameResult ② Profile 保存/应用 ③ Folder 进度/取消 ④ DB 可查询对象 ⑤ 非法状态迁移被拒绝 |

### Phase D · 前端工作台

| 项 | 内容 |
|----|------|
| **目标** | 图片检测完整 UI 闭环 |
| **输入** | Phase C |
| **输出** | 项目/图片/模型/设置页；WS API 层；Konva；结果列表；Profile 条 |
| **覆盖卡** | P1-13, P1-14, P1-15, P1-16 |
| **验收** | ① 选多模型选图推理出框 ② 列表高亮/隐藏 ③ 标签 `{id}:{class}` 中文 ④ 断线重连 UI 状态正确 |

### Phase E · 联调与验收

| 项 | 内容 |
|----|------|
| **目标** | DoD 全绿、文档回收 |
| **输入** | Phase D |
| **输出** | 集成脚本/检查单；验收记录；已知限制；P2 backlog |
| **覆盖卡** | P1-18 |
| **验收** | IMPLEMENTATION §7 + PHASE1 DoD 全部满足；风险表更新 |

**阶段出口门禁**：未验收不得进入下一 Phase。

---

## 8. 代码开发规范

### 8.1 Python

| 项 | 规范 |
|----|------|
| 版本 | 3.12 |
| 类型 | 全面 type hints；`mypy` 或 `pyright` 零错误（配置随仓库） |
| 格式 | ruff format + ruff lint；行长 100 |
| 导入 | 绝对导入 `app.`；禁止跨层逆向 import |
| 命名 | 模块 snake_case；类 PascalCase；常量 UPPER；私有 `_` |
| 文件 | 单文件建议 ≤ 400 行；超则拆分 |
| 入口 | `main.py` 只装配 |
| 路径 | `pathlib`；禁止硬编码盘符 |
| 异常 | 自定义 `AppError` 层级；WS 层映射 `error.code` |
| 并发 | 模型 predict 同实例串行；写 DB 单队列 |
| 测试 | pytest；Runtime 可 mock；DAO 必测 |

### 8.2 TypeScript / Vue

| 项 | 规范 |
|----|------|
| TS | `strict: true` |
| 组件 | `<script setup lang="ts">`；单文件组件 PascalCase |
| 命名 | 文件 kebab 或 Pascal（团队统一 **PascalCase.vue**）；composables `useXxx` |
| 状态 | 业务在 Pinia；组件局部用 ref |
| API | 不在组件直接 `websocket.send`；走 `api/methods` |
| 样式 | scss/css modules 或 Uno；全局变量集中 |
| 禁止 | `any` 无注释；渲染层 `require('fs')` |

### 8.3 目录规范

- 新功能先进对应层目录；禁止 `utils/dump.py` 杂物堆
- 禁止跨 `desktop/src` 与 `backend/app` 复制粘贴业务
- 协议变更：**先改本文 §4，再改 pydantic + TS type**

### 8.4 命名规范（跨语言）

| 对象 | 规则 | 示例 |
|------|------|------|
| 消息 type | `domain.action` | `detect.image` |
| 错误 code | UPPER_SNAKE | `MODEL_NOT_FOUND` |
| DB 表 | snake_case 复数 | `objects` `tasks` |
| DB 列 | snake_case | `model_id` |
| 模型 id | 小写短英文 | `person` |
| Profile id | slug | `default` `night_shift` |

### 8.5 异常处理

```
底层 RuntimeError
  → wrap: ModelLoadError / PredictError
  → Task: 捕获 → status=failed, error 写 DB
  → Handler: 映射 error.code → WS
  → 前端: toast + 控制台 detail
```

- 不吞异常；至少 log warning
- 用户可见 message 中文；`detail` 可英文技术信息
- 禁止用异常做正常分支

### 8.6 日志规范

| 项 | 规范 |
|----|------|
| 库 | loguru |
| 格式 | `time \| level \| logger \| message` |
| logger 名 | `app.task` `app.pipeline` `app.model_manager` ... |
| 级别 | INFO 默认；predict 细节 DEBUG；可恢复 WARNING；失败 ERROR |
| 禁止 | print；log 整帧 base64；循环内 INFO 刷屏（用 DEBUG 或进度事件） |
| 敏感 | 不记绝对用户隐私路径时可相对化；不记密钥 |

---

## 9. Implementation Risk Review

### 9.1 Tracking 是否需要改数据库？

| 问题 | 结论 |
|------|------|
| 现设计 | `objects.track_id INTEGER` + 索引已预留 |
| 加 Tracking | **无需改表结构**；若需轨迹表再 migration（可选 `tracks`） |
| 接口 | `ResultObject.track_id` 已一等；label `{track_id}` 已预留 |
| 风险 | 低。P6 只需实现 track 节点/后处理 + 可选 `tracks` 表 |

### 9.2 Segmentation 是否改接口？

| 问题 | 结论 |
|------|------|
| 现设计 | Geometry 多态 + `geom_json.mask_ref` |
| 加 Segment | **不改 BaseRuntime 签名**；Runtime 返回 mask 类 Geometry |
| 风险 | 中：mask 大对象 IO。需 P6 前定 RLE/png 规范与缩放；**不阻塞接口** |
| 缓解 | mask 不进 WebSocket 默认 payload（用 ref 或缩略） |

### 9.3 RK3588 是否改 Runtime？

| 问题 | 结论 |
|------|------|
| 现设计 | BaseRuntime + registry + 分 backend requirements |
| 加 RKNN | **新增 RKNNRuntime 类**，不改上层 |
| 风险 | 中：设备检测、量化工具链、NPU 依赖装机 |
| 缓解 | device 字段与错误码 `DEVICE_UNAVAILABLE`；文档化 Linux/ARM 部署 |

### 9.4 视频大文件性能风险

| 风险 | 影响 | 缓解（设计） |
|------|------|----------------|
| 整段读入内存 | OOM | 流式逐帧；禁止 list 全帧 ndarray |
| 每帧 JSON 落盘 | 磁盘/延迟 | 批量事务；仅 detect 帧写 objects；cache 帧只渲染 |
| 4K 高帧率 | CPU 不足 | skip_frame；预览降采样；导出再全尺寸 |
| WS 推送全帧结果 | 带宽/卡 UI | 节流 progress；result 可配置抽帧推送 |
| 导出双倍 IO | 时间长 | ExportTask 后台 + 进度；ffmpeg 管道 |
| 封面/缩略 | 重复解码 | 预生成索引关键帧 |

### 9.5 多模型并行资源管理

| 风险 | 影响 | 缓解 |
|------|------|------|
| 多份 torch 权重 | 内存爆炸 | Session refcount + ModelManager LRU + 显式 unload |
| 线程池过大 | 争用 GIL/设备 | `max_workers` 限制；GPU 串行队列 |
| 同模型并行 predict | 崩溃/脏数据 | 每 binding 一把锁 |
| 加载风暴 | UI 卡顿 | load 放线程；task 异步 |
| 设备不一致 | 报错 | Session.device 统一；不支持则拒绝 load |
| 任务取消 | 半结果 | 单元边界检查；DB 事务按帧提交 |

### 9.6 其他实现风险

| 项 | 风险 | 缓解 |
|----|------|------|
| TensorRT engine 迁移 | 换 GPU 失效 | engine 缓存目录带 GPU 架构指纹 |
| OCR 协议 | 文本框+全文 | geom_type=text + extra_json |
| 前后端类型漂移 | 运行时错误 | protocol 单源；CI 校验或生成 TS |
| Windows 路径 | 中文/空格 | pathlib + 集成用例 |
| Supervisor 端口冲突 | 起不来 | 端口扫描 + env 注入 |

---

## 10. 附录：设计修正与开放问题

### 10.1 相对 ARCHITECTURE_v0.2 的修正（需回写）

| # | 修正 | 原因 |
|---|------|------|
| C1 | 明确 **InferenceSession** 为一等模块（§2.3） | 架构仅隐含；实现需要缓存/生命周期归属 |
| C2 | Pipeline 引入 **NodeSpec/DAG**，P1 只用 parallel | 为级联预留，避免后改 |
| C3 | DB 增加 **`models` 表**、可选 **`projects`/`sessions`** | 任务需要模型快照与复现 |
| C4 | `objects` 主键含 **model_id** | 多模型合并后同 object_id 需区分来源 |
| C5 | Task 增加 **`error_code` / `parent_task_id` / `progress_detail`** | 中断区分、导出溯源、断点 |
| C6 | 协信封增加 **`error` 对象与错误码表** | v0.2 未穷尽 |
| C7 | 恢复策略：P1 **不自动 resume**，interrupted→failed+可重跑 | 降低 P1 复杂度 |

### 10.2 开放问题（默认按括号内决策）

1. Profile 覆盖模型 YAML conf 的优先级？（**Profile > Model YAML 默认**）
2. 显式 unload vs LRU 自动卸载阈值？（P1 **仅显式 unload**）
3. 前端 visible 修改是否 P1 写回 DB？（P1 **本地**；P2 写 `ops`）
4. 单库多项目还是每项目一库？（**每项目一库**，`projects` 表可选）
5. 是否启用 WS 本地 token？（P1 **否**，绑 127.0.0.1）

### 10.3 开发时文档义务

- 实现与本文不一致 → 先改本文再改代码
- Phase 出口更新 `docs/PHASE1_v0.2.md` 勾选与 README 进度

---

## 完成定义（本文档）

交付 `IMPLEMENTATION_DESIGN_v0.1.md`，覆盖：TaskManager / PipelineEngine / InferenceSession / Runtime、完整 SQLite、WS 协议示例、前端页面与状态、迁移机制、P1 分阶段开发顺序、编码规范、风险审查。  
**不含业务代码。**
