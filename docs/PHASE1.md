# YOLO Vision Workbench · 第一阶段任务拆解

> 依赖：`docs/ARCHITECTURE.md`
> 原则：阶段开发，P1 完成并验收后再进入下一阶段。不一次生成全部代码。

---

## 0. P1 目标（一句话）

**打通「选模型 → 选图 → 推理 → Canvas 画框」最小闭环**，并把日志、协议、模型抽象、任务骨架做成可扩展底座。

### 验收标准（DoD）

- [ ] `backend` 可独立启动，WS 可连接
- [ ] `desktop` 可独立启动，能连上 backend
- [ ] 能扫描 `models/` 并加载 YOLO 权重，返回 class 列表（含中文显示名）
- [ ] 能选择单张图片推理，Konva 叠加显示 bbox / 标签
- [ ] 能选择文件夹批量推理，进度可推送
- [ ] 结果列表可点击高亮、可隐藏单框
- [ ] 日志同时落盘并显示在 UI
- [ ] 无 `model.predict()` 泄漏到上层；无硬编码绝对路径

---

## 1. 任务总览

| ID | 任务 | 产出 | 依赖 |
|----|------|------|------|
| P1-01 | 仓库骨架与文档 | 目录、README、配置约定 | — |
| P1-02 | Python 后端骨架 | FastAPI 入口、config、loguru | P1-01 |
| P1-03 | WebSocket 协议层 | protocol + 连接管理 + 心跳 | P1-02 |
| P1-04 | 日志双通道 | 文件 sink + WS sink | P1-03 |
| P1-05 | Runtime 抽象 + YOLORuntime | BaseRuntime / factory / yolo | P1-02 |
| P1-06 | Model Manager + YAML | 扫描/加载/缓存/class 映射 | P1-05 |
| P1-07 | Task 骨架 + Image/FolderTask | TaskManager + 两类任务 | P1-03, P1-06 |
| P1-08 | 推理结果模型 + 保存 | DetectObject / FrameResult / JSON | P1-05 |
| P1-09 | Electron + Vue3 初始化 | 可运行桌面壳、路由、Pinia | P1-01 |
| P1-10 | 前端 WS API 层 | 类型化客户端、消息编解码 | P1-03, P1-09 |
| P1-11 | 图片推理 UI 流程 | 选图/选模型/参数/发起推理 | P1-10, P1-06 |
| P1-12 | Konva 画布渲染 | 叠加框、样式、模板标签 | P1-11, P1-08 |
| P1-13 | 结果列表交互 | 列表/高亮/隐藏 | P1-12 |
| P1-14 | 日志面板 UI | 级别展示、过滤 | P1-04, P1-09 |
| P1-15 | 集成联调 + 验收 | 端到端 DoD | 全部 |

建议并行：`P1-02~08`（后端）与 `P1-09~10`（前端壳）可并行，`P1-11` 起汇合。

---

## 2. 详细任务卡

### P1-01 仓库骨架与文档

**内容**

- 创建 `YOLO-Studio/` 顶层结构（desktop / backend / models / projects / docs）
- `README.md`：启动方式、目录说明、P1 范围
- `.gitignore`、基础 `config` 约定（根路径可覆盖）
- 示例模型配置 `models/examples/person.yaml`（可先不带真实权重）

**验收**

- 目录与 ARCHITECTURE §4 一致
- 文档可指导新人启动

---

### P1-02 Python 后端骨架

**内容**

- `uv` 初始化 `backend/pyproject.toml` + `requirements/base.txt`
- `setup_env.py`（创建 venv、按 requirements 安装）
- `app/main.py`：仅装配 FastAPI / 路由 / 启动事件
- `app/config.py`：端口、主机、models/projects/logs 目录解析
- `app/utils/paths.py`：项目根解析，禁止硬编码

**验收**

- `python -m app.main` 或 `uv run` 可启动 HTTP `/health`
- 路径均来自配置

---

### P1-03 WebSocket 协议层

**内容**

- `app/websocket/protocol.py`：消息信封、pydantic 模型、type 枚举
- `app/websocket/server.py`：连接注册、鉴权（本地）、心跳
- `app/websocket/handlers/`：按域挂载（model / detect / task / project / system）
- 前置消息校验，非法消息返回错误信封

**验收**

- 用 wscat/脚本可 `ping`/`pong`
- 未知 type 返回结构化错误

---

### P1-04 日志双通道

**内容**

- `app/utils/logging.py`：loguru 配置
- 文件：按日滚动，`logs/`
- WS sink：推送 `log.message`（可限流/级别过滤）
- 请求/任务关键路径打点

**验收**

- 日志文件生成且格式稳定
- UI 能收到实时日志（P1-14 联调）

---

### P1-05 Runtime 抽象 + YOLORuntime

**内容**

- `BackendType` / `BaseRuntime` / `DetectObject` / `FrameResult`
- `factory.py` + `runtime/registry.py` 注册表
- `yolo_runtime.py`：ultralytics 加载、predict、names
- `postprocess.py`：统一输出 DetectObject（含原始 class_name）

**验收**

- 通过工厂创建 YOLORuntime 完成一次预测
- **上层零 `model.predict()`**
- 单元测试：mock 图片 → 合法 FrameResult

---

### P1-06 Model Manager + YAML

**内容**

- 模型 YAML schema（pydantic）：id / backend / model_path / conf / class_display / render
- `scanner.py`：扫描 models 目录
- `loader.py`：加载/卸载/LRU 或显式缓存
- `metadata.py`：class names + **显示名映射**（渲染用中文，逻辑用原名）
- WS：`model.list` / `model.load` / `model.unload` / `model.loaded`

**验收**

- 加载后返回：`[{class_name, display_name, color...}]`
- 二次推理不重复加载模型
- 多模型配置文件可并行加载（内存允许）

---

### P1-07 Task 骨架 + Image/FolderTask

**内容**

- `Task` / `TaskStatus` / `TaskType`
- `manager.py`：创建、start、pause、cancel、进度回调
- `image_task.py`：单图
- `folder_task.py`：遍历图片、进度、可取消
- WS：`task.*` 消息

**验收**

- 任务状态机转移正确
- 文件夹任务进度按张推送
- 取消后不再继续推理

---

### P1-08 推理结果模型 + 保存

**内容**

- 结果 JSON schema（见 ARCHITECTURE §6）
- 按 `task_id` 写入 `projects/<name>/results/`
- 保留 style 字段（前端渲染用）
- 与 sqlite 索引预留（P1 可仅文件）

**验收**

- 结果可完整反序列化
- 原始图片路径被记录，未画死框

---

### P1-09 Electron + Vue3 初始化

**内容**

- electron-vite（或等价）脚手架：desktop/
- 主进程窗口、preload 安全桥
- Vue3 + TS + Pinia + Element Plus + Router
- 基础布局：侧栏导航（项目 / 图片 / 设置 / 日志）
- 开发脚本：`dev` / `build`

**验收**

- `npm run dev` 出窗口
- 页面路由可切换

---

### P1-10 前端 WS API 层

**内容**

- `src/api/ws.ts`：连接、重连、心跳
- `src/api/protocol.ts`：与后端一致的 TS 类型
- `src/api/methods.ts`：loadModel / detectImage / detectFolder / taskControl
- Pinia：`modelStore` / `taskStore` / `logStore` / `projectStore`

**验收**

- 类型安全收发消息
- 断线提示与自动重连

---

### P1-11 图片推理 UI 流程

**内容**

- 选择图片 / 文件夹（Electron dialog）
- 模型多选、conf 滑条、classes 多选（加载后填充）
- 发起 ImageTask / FolderTask
- 进度条与状态展示

**验收**

- 一次完整点选 → 出结果
- 模型加载后自动显示 class 列表与显示名

---

### P1-12 Konva 画布渲染

**内容**

- `CanvasStage.vue`：底图 + 独立 overlay 层
- bbox 绘制、颜色/线宽、标签模板
- 标签：`{id}:{class}` 默认；支持 `{confidence}` 等
- 中文标签字体处理
- 不修改原始像素，结果与底图分离

**验收**

- 框位置与 JSON bbox 一致
- 模板变量替换正确

---

### P1-13 结果列表交互

**内容**

- 右侧结果列表：class / conf / bbox
- 点击列表 → 对应框高亮（描边/放大）
- 隐藏/显示单个框（同步 `visible`）
- 保存当前视图样式到项目结果（可选写回）

**验收**

- 列表与画布双向同步
- 隐藏后导出/保存尊重 visible

---

### P1-14 日志面板 UI

**内容**

- 日志面板：级别颜色、自动滚动、级别过滤
- 接收 `log.message`

**验收**

- ERROR 可见且突出
- 不阻塞主 UI

---

### P1-15 集成联调 + 验收

**内容**

- 端到端脚本化检查（启动 backend → desktop → 推理样例图）
- 对照 DoD 清单勾选
- 记录已知限制与 P2 待办

**验收**

- DoD 全部满足
- 输出《P1 验收记录》

---

## 3. 建议实施顺序（串行关键路径）

```
P1-01 骨架
  ├─► P1-02 后端骨架 ─► P1-03 协议 ─► P1-04 日志
  │         └─► P1-05 Runtime ─► P1-06 ModelManager
  │                   └─► P1-08 结果 ─► P1-07 Task
  └─► P1-09 前端壳 ─► P1-10 WS API
            └─► P1-11 图片流程 ─► P1-12 Canvas ─► P1-13 列表
                                      └─► P1-14 日志 UI
                                              └─► P1-15 联调
```

---

## 4. P1 明确不包含

| 项 | 归属阶段 |
|----|----------|
| 视频文件 / 时间轴 / 操作记录 | P3 |
| USB Camera / RTSP / 录制 | P4 |
| 多模型 Pipeline 级联 | P2（并行合并）/ 更后 |
| ONNX / TensorRT / RKNN | P5 |
| Segment / Pose / OCR / Tracking / SAM | P2+ / P6 |
| 完整项目管理 UI（新建/切换/最近） | P2 |
| 打包安装程序 | 发布阶段 |

---

## 5. 技术债与风险（P1 需关注）

| 风险 | 缓解 |
|------|------|
| ultralytics/torch 体积大、安装慢 | `requirements/yolo.txt` 隔离；wheels 缓存 |
| Windows 路径/中文路径 | 全程 pathlib；集成用例含中文路径 |
| WebSocket 粘包/大结果 | 压缩或分片策略预留；P1 结果限图尺寸 |
| 主进程与后端生命周期 | 明确谁拉起 backend；崩溃重启策略写文档 |
| Konva 与大图性能 | overlay 分层；P1 限制分辨率展示 |

---

## 6. 开发规范（P1 起强制）

- 模块化，禁止巨型文件 / 业务进 `main.py`
- Python 全面 type hints；TS `strict`
- 路径不硬编码，走 config
- 模型配置独立 YAML
- 推理必须走 `BaseRuntime`
- 结果 JSON 化，不在图片上画死
- 注释只写非显而易见的 WHY

---

## 7. 确认后立即执行的编码顺序

用户确认架构与任务拆解后，按下列顺序开工（仍保持小步提交节奏）：

1. **P1-01 → P1-02 → P1-03**：先能跑起来的后端与协议
2. **P1-05 → P1-06**：模型抽象与管理（核心资产）
3. **P1-07 → P1-08**：任务与结果
4. **P1-09 → P1-10**：前端壳与通信
5. **P1-11 → P1-12 → P1-13**：图片闭环 UI
6. **P1-04 / P1-14**：日志贯通
7. **P1-15**：验收

每完成一个任务卡，在对应清单勾选并更新 README 进度。
