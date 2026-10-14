# YOLO Vision Workbench · 第一阶段任务拆解

> 版本：**v0.2**（与 `ARCHITECTURE_v0.2.md` 对齐）
> 原则：阶段开发，P1 验收后再进入下一阶段。不一次生成全部代码。

---

## 0. P1 目标（v0.2）

**打通「启动应用 → 加载多模型 → 选图 → 合并推理 → Canvas 画框」最小闭环**，并把生命周期、SQLite、Profile、协议、日志做成可扩展底座。

### 验收标准（DoD）

- [ ] 双击/启动 desktop 后 **Electron 自动拉起 Python Backend**，`/health` 就绪
- [ ] Backend 异常退出时可自动重启（有限次数）；退出应用无残留进程
- [ ] `backend` 亦可独立启动调试；支持 attach 已有进程（开发模式）
- [ ] 能扫描 `models/` 与 `models/repository` 并加载 YOLO，返回 class 列表（含中文显示名）
- [ ] **可同时选择多个模型**，一次推理输出合并结果（objects 带 `model_id`）
- [ ] 单图 / 文件夹推理，Konva 叠加 bbox / 标签（`{id}:{class}`）
- [ ] 结果列表点击高亮、隐藏单框；结果写入 **SQLite**
- [ ] 可保存/应用 **Inference Profile**（模型集合、conf、样式等）
- [ ] 日志落盘 + UI 面板
- [ ] 无 `model.predict()` 泄漏到上层；无硬编码绝对路径；**JSON 非唯一存储**

---

## 1. 任务总览

| ID | 任务 | 产出 | 依赖 |
|----|------|------|------|
| P1-01 | 仓库骨架与文档 | 目录、README、config 约定 | — |
| P1-02 | Python 后端骨架 | FastAPI、config、paths、loguru | P1-01 |
| P1-03 | SQLite 基础层 | schema.sql、connection、DAO、migrations | P1-02 |
| P1-04 | WebSocket 协议层 | protocol、server、handlers、心跳 | P1-02 |
| P1-05 | 日志双通道 | 文件 sink + WS sink | P1-04 |
| P1-06 | Runtime 抽象 + YOLORuntime | BaseRuntime、Geometry、factory、registry | P1-02 |
| P1-07 | Model Manager + YAML + Repository 骨架 | 扫描/加载/缓存/映射/catalog 读取 | P1-06 |
| P1-08 | 多模型 Pipeline（基础） | parallel 执行 + Result Merge | P1-06, P1-07 |
| P1-09 | Inference Profile | schema、保存/应用、与 Task 绑定 | P1-03, P1-07 |
| P1-10 | Task 骨架 + Image/Folder（多模型） | TaskManager、进度、取消 | P1-04, P1-08, P1-09 |
| P1-11 | 结果持久化 | FrameResult → SQLite + 可选 JSON 导出 | P1-03, P1-06 |
| P1-12 | Electron 初始化 + Process Supervisor | 自动拉起/健康/重启/退出 | P1-01 |
| P1-13 | 前端 WS API 层 | 类型化客户端、stores | P1-04, P1-12 |
| P1-14 | 图片推理 UI | 选图、多模型、参数、Profile | P1-13, P1-10 |
| P1-15 | Konva 画布 | bbox/样式/模板/中文 | P1-14, P1-11 |
| P1-16 | 结果列表交互 | 列表/高亮/隐藏 | P1-15 |
| P1-17 | 日志面板 + Backend 状态 UI | 级别过滤、连接/进程状态 | P1-05, P1-12 |
| P1-18 | 集成联调 + 验收 | DoD 勾选、P2 待办 | 全部 |

**并行建议**：`P1-02~11`（后端）∥ `P1-12~13`（前端壳+生命周期），在 `P1-14` 汇合。

---

## 2. 详细任务卡

### P1-01 仓库骨架与文档

**内容**

- 顶层结构：`desktop/ backend/ models/ projects/ docs/`
- `README.md`、`.gitignore`、config 约定（`YOLO_STUDIO_ROOT`）
- 示例：`models/examples/person.yaml`（可暂无权重）
- 文档占位：`PROTOCOL.md` / `DATABASE.md` / `MODEL_CONFIG.md`

**验收**：目录与 ARCHITECTURE_v0.2 §4 一致。

---

### P1-02 Python 后端骨架

**内容**

- uv + `pyproject.toml` + `requirements/base.txt`、`yolo.txt`
- `setup_env.py` + `wheels/` 约定
- `app/main.py` 装配；`GET /health`、`GET /ready`（可选）
- `config.py` / `utils/paths.py`：端口、目录、解释器无关路径

**验收**：`uv run` 可启动；路径全部来自配置。

---

### P1-03 SQLite 基础层（新增）

**内容**

- `database/schema.sql`：`project_meta / profiles / tasks / media / frames / objects / ops`（见 ARCHITECTURE §6.2）
- `connection.py`：连接工厂、PRAGMA（WAL、foreign_keys）
- `dao/`：tasks、profiles、frames、objects、ops（禁止业务层裸 SQL）
- `migrations/`：版本表 + 初始迁移
- 打开项目时初始化/挂载 `projects/<name>/database.sqlite`

**验收**

- 空项目可自动建库建表
- DAO 单测：任务/帧/对象/profile CRUD
- **不以 JSON 为唯一存储**

---

### P1-04 WebSocket 协议层

**内容**

- 信封：`type / id / data / ts`
- pydantic 校验；错误信封
- handlers：system / model / detect / task / profile / project
- 心跳 `ping/pong`；`system.health` / `system.shutdown`

**验收**：脚本可 ping；未知 type 返回结构化错误。

---

### P1-05 日志双通道

**内容**

- loguru：按日文件 + WS sink（级别/限流）
- Supervisor 捕获的 backend stdout 并入

**验收**：文件稳定生成；UI 可收到实时日志。

---

### P1-06 Runtime 抽象 + YOLORuntime

**内容**

- `BackendType` / `ModelTaskType` / `GeometryType` / `Geometry` / `ResultObject` / `FrameResult`
- `BaseRuntime`：load / predict / class_names / unload
- `factory` + `registry`
- `yolo_runtime`：detect 路径完整
- `postprocess`：统一 ResultObject（`model_id` 填充由 Pipeline 层完成亦可）

**验收**

- 工厂创建 YOLORuntime 完成预测
- **上层零 `model.predict()`**
- 单测：mock 图 → 合法 FrameResult（含 geometry）

---

### P1-07 Model Manager + YAML + Repository 骨架

**内容**

- Model YAML schema（id/backend/task/conf/class_display/render）
- 扫描 `models/examples` 与 `models/repository/packages`
- catalog.yaml / manifest.yaml **只读合并**进 `model.list`
- loader：缓存、卸载、class 映射（渲染中文 / 逻辑原名）
- WS：`model.list` / `model.load` / `model.unload` / `model.loaded`

**验收**

- 列表含本地示例与 repository 包（若存在）
- 二次推理不重复加载
- 显示名映射生效

---

### P1-08 多模型 Pipeline（基础）（P1 新增）

**内容**

- `inference/pipeline.py`：`PipelineExecutor(mode=parallel)`
- 输入：`model_ids[]` + 图像；输出：合并 `FrameResult`
- Merge：帧内统一 object id、保留 `model_id`、可保留 conf 排序
- 单模型失败：记 warning，其余继续（可配置 fail-fast）
- 跨模型 NMS：**P1 不做**（接口预留 `merge=concat`）

**验收**

- 同时 load 2+ 模型，一次 `detect.image` 返回多 `model_id` 对象
- 合并结果可被后续持久化/渲染

---

### P1-09 Inference Profile（P1 新增）

**内容**

- Profile schema（models/pipeline/runtime/render/export）— 见 ARCHITECTURE §5.6
- 存 SQLite `profiles`；可选导出 yaml 到 `projects/<n>/profiles/`
- 默认 profile：项目创建时写入
- WS：`profile.list` / `profile.save` / `profile.apply` / `profile.delete`
- `task.params` 或 `task.profile_id` 绑定，保证可复现

**验收**

- 保存当前多模型+参数 → 切换后应用生效
- 新任务记录 profile_id

---

### P1-10 Task 骨架 + Image/Folder（多模型）

**内容**

- Task 状态机；`TaskManager` 队列/并发度（P1 可串行）
- ImageTask / FolderTask：支持 `model_ids[]` + profile
- 进度、取消、失败
- WS：`task.*`

**验收**：状态转移正确；文件夹进度推送；取消即停。

---

### P1-11 结果持久化

**内容**

- FrameResult → `frames` + `objects`（geom_json）
- media 索引
- 可选：`results/<task_id>/export.json` 交换文件
- style/visible 写回路径预留

**验收**：DB 可查询某帧对象；JSON 导出可反序列化；原图路径入 media。

---

### P1-12 Electron 初始化 + Process Supervisor（强化）

**内容**

- electron-vite 脚手架；安全 preload
- `electron/backend/supervisor.ts`：
  - spawn backend（venv/python 路径可配）
  - 端口选择/注入 env
  - `/health` 轮询 ready
  - 崩溃指数退避重启（上限 N）
  - 退出优雅 shutdown → 超时 kill 进程树
- 开发模式 attach 已有 backend
- UI 暴露 backend 状态（连接中/就绪/重启中/失败）

**验收**

- 仅启动 desktop 即可用
- kill python 后应用内可见重启并恢复连接
- 退出后任务管理器无残留 python

---

### P1-13 前端 WS API 层

**内容**

- ws 客户端、重连、心跳、请求-响应关联
- protocol TS 类型与后端对齐
- Pinia：model / task / profile / log / project / backendStatus

**验收**：类型安全收发；断线提示与重连。

---

### P1-14 图片推理 UI

**内容**

- 选图/文件夹（dialog）
- **多模型勾选**、conf、classes
- Profile：下拉切换、保存当前参数
- 发起任务、进度

**验收**：多模型选图 → 出合并结果；Profile 保存/应用可用。

---

### P1-15 Konva 画布

**内容**

- 底图 + overlay；bbox / 颜色 / 线宽
- 标签模板 `{id}:{class}`（`class`=display_name），支持 `{confidence}` 等
- 中文标签
- 多模型不同颜色（model_id → 默认色板）

**验收**：框与 DB/JSON bbox 一致；模板替换正确。

---

### P1-16 结果列表交互

**内容**

- 列表：model / class / conf / bbox
- 点击高亮；隐藏/显示（同步 DB visible）
- 按模型过滤（基础）

**验收**：列表与画布双向同步。

---

### P1-17 日志面板 + Backend 状态 UI

**内容**

- 日志级别颜色、过滤、自动滚动
- 顶栏：Backend 状态、延迟、重启次数

**验收**：错误可见；状态真实反映 supervisor。

---

### P1-18 集成联调 + 验收

**内容**

- 脚本：启动 desktop → 自动 backend → 多模型样例图
- 对照 DoD；输出《P1 验收记录》与 P2 待办

**验收**：DoD 全绿；已知限制成文。

---

## 3. 实施顺序（关键路径）

```
P1-01 骨架
  ├─► P1-02 后端 ─► P1-03 SQLite ─► P1-11 结果持久化
  │        └─► P1-04 协议 ─► P1-05 日志
  │        └─► P1-06 Runtime ─► P1-07 ModelManager
  │                   └─► P1-08 Pipeline ─► P1-09 Profile ─► P1-10 Task
  └─► P1-12 Electron Supervisor ─► P1-13 WS API
            └─► P1-14 图片 UI ─► P1-15 Canvas ─► P1-16 列表
                              └─► P1-17 日志/状态 UI
                                      └─► P1-18 联调
```

**建议开工批次**

| 批次 | 任务 |
|------|------|
| A | P1-01 → 02 → 03 → 04 |
| B | P1-06 → 07 → 08 → 09 → 10 → 11 |
| C | P1-12 → 13 |
| D | P1-14 → 15 → 16 |
| E | P1-05 / 17 → 18 |

---

## 4. P1 明确不包含

| 项 | 归属 |
|----|------|
| 视频检测、时间轴、ops UI | P3 |
| **视频导出实现**（类型/表/draw 预留） | P3 |
| USB Camera / RTSP / 录制 | P4 |
| Pipeline 级联 / 跨模型 NMS | P2+ |
| ONNX / TensorRT / RKNN 实现 | P5 |
| Segment / Pose / OCR / Tracking / SAM | P6 |
| Model Repository **下载/校验** | P2+（P1 只读本地包） |
| 完整项目管理 UI | P2 |
| 安装包打包 | 发布 |

---

## 5. 风险与缓解（P1）

| 风险 | 缓解 |
|------|------|
| torch 首次启动慢导致 health 超时 | 超时可配；ready 前 UI 显示「模型系统加载中」 |
| Windows 杀进程树不彻底 | `taskkill /T /F`；退出钩子 + 单测 |
| 多模型内存 | loader 缓存上限/显式 unload；文档写清 |
| SQLite 并发 | WAL；写入串行队列（P1） |
| 中文路径/标签 | pathlib + 集成用例；字体 fallback |
| 协议前后端漂移 | 单一 protocol 源（pydantic + TS 类型生成或手写对照表） |

---

## 6. 开发规范（强制）

- 模块化；禁止巨型文件 / 业务进 `main.py`
- 类型提示全覆盖
- 路径不硬编码
- 模型配置独立 YAML
- 推理必须 `BaseRuntime`；多模型必须 `Pipeline`
- **SQLite 权威**；JSON 仅交换/导出
- 结果不画死进原图
- 注释只写非显而易见的 WHY

---

## 7. 确认后编码顺序

1. **P1-01 → 02 → 03 → 04**（底座 + 存储 + 协议）
2. **P1-06 → 07 → 08**（Runtime / Model / Pipeline）
3. **P1-09 → 10 → 11**（Profile / Task / 持久化）
4. **P1-12 → 13**（生命周期 + 前端通信）
5. **P1-14 → 15 → 16**（图片闭环 UI）
6. **P1-05 / 17 / 18**（日志贯通与验收）

每完成一卡勾选 DoD 分项并更新 README。
