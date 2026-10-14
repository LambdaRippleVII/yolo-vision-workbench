# YOLO Vision Workbench · 中文化与本地化方案

> 版本：v0.1 · 2026-10
> 目标：所有**用户可见文本默认中文**；代码标识符保持英文
> 配套：`UI_DESIGN_SPEC.md`

---

## 1. 原则

| 层 | 语言 | 示例 |
|----|------|------|
| UI 文案、菜单、按钮、状态、提示、错误、空状态 | **中文** | 「开始推理」「模型加载失败」 |
| 技术专名 | **保留英文** | YOLO、ONNX、TensorRT、RKNN、CUDA、FPS、WebSocket、RTSP、IoU、NMS、API、JSON、SQLite、PyTorch |
| 代码变量、函数、类、字段、消息 `type` | **英文** | `model_id`、`detect.image`、`backendStatus` |
| 日志 message（写入文件） | 中文优先 | 「模型 person 加载完成」 |
| 日志级别名展示 | 中文 | 调试/信息/警告/错误/严重 |
| 开发者文档 | 中文 | docs/*.md |

**禁止**：界面残留 Dashboard / Health / Logs / Settings / Project / Model Manager 等英文标题。

---

## 2. 术语表（锁定）

| 英文/概念 | 标准中文 | 备注 |
|-----------|----------|------|
| Dashboard | 工作台 | 不用仪表盘 |
| Health | 系统状态 | 页/面板名 |
| Logs | 日志 | |
| Settings / Preferences | 系统设置 / 设置 | 导航用「系统设置」 |
| Project | 项目 | 「项目管理」 |
| Model / Model Manager | 模型 / 模型管理 | |
| Dataset | 数据集 | |
| Inference / Detect | 推理 / 检测 | 动作用「推理」 |
| Task | 任务 | 「推理任务」 |
| Device | 设备 | 「设备管理」 |
| Backend | 后端服务 | 状态用「后端服务」 |
| Frontend / UI | 界面 | |
| Pipeline | 管线 | 或保留 Pipeline 于技术面板 |
| Session | 会话 | |
| Runtime | 运行时 | 专名可保留 |
| Profile | 配置方案 | 或「推理配置」 |
| Confidence | 置信度 | |
| Bounding box / bbox | 检测框 | |
| Mask | 掩码 | |
| Keypoint | 关键点 | |
| Track / Tracking | 跟踪 | |
| Frame | 帧 | |
| Skip frame | 跳帧 | |
| Box persistence | 框持续 | |
| Export | 导出 | |
| Record | 录制 | |
| Pause / Resume / Cancel | 暂停 / 继续 / 取消 | |
| Load / Unload | 加载 / 卸载 | |
| Ready | 就绪 | |
| Connecting | 连接中 | |
| Unhealthy | 状态异常 | |
| Failed | 失败 | |
| Restarting | 重启中 | |
| PENDING | 等待中 | 任务状态 |
| RUNNING | 进行中 | |
| PAUSED | 已暂停 | |
| COMPLETED | 已完成 | |
| CANCELLED | 已取消 | |
| FAILED | 失败 | |
| YES/NO 确认 | 确定 / 取消 | |

### 2.1 保留英文的技术词

`YOLO` `Segment` `Pose` `OCR` `SAM` `ONNX` `TensorRT` `RKNN` `RK3588` `RDK` `CUDA` `CPU` `GPU` `NPU` `FPS` `WebSocket` `HTTP` `RTSP` `USB` `UUID` `JSON` `YAML` `SQL` `SQLite` `PNG` `JPEG` `MP4` `H.264` `FPS` `FPS` `IoU` `NMS` `mAP` `UUID` `ULID` `WebSocket` `loguru` `FastAPI` `Electron` `Vue` `TypeScript`

---

## 3. 消息 `type` 与展示名映射

协议 `type` 保持英文（见 IMPLEMENTATION_DESIGN §4）。UI 展示用中文映射表（前端 locales）：

| type | 日志/界面展示 |
|------|----------------|
| `system.hello` | 连接握手 |
| `ping` / `pong` | 心跳检测 |
| `model.load` | 加载模型 |
| `model.list` | 获取模型列表 |
| `detect.image` | 图片推理 |
| `detect.folder` | 文件夹批量推理 |
| `task.progress` | 任务进度 |
| `log.message` | 系统日志 |
| `error` | 错误 |

---

## 4. 错误码中文文案

| code | 用户可见文案 | 建议动作 |
|------|----------------|----------|
| `BAD_REQUEST` | 请求格式不正确 | 请重试或检查参数 |
| `MODEL_NOT_FOUND` | 未找到模型 | 请在「模型管理」中检查模型路径 |
| `MODEL_LOAD_FAILED` | 模型加载失败 | 请检查权重文件与运行依赖 |
| `TASK_STATE_ERROR` | 任务状态不允许该操作 | 请刷新任务状态后重试 |
| `TASK_NOT_FOUND` | 任务不存在 | 任务可能已清理 |
| `MEDIA_NOT_FOUND` | 找不到媒体文件 | 请确认文件是否已移动或删除 |
| `INFERENCE_ERROR` | 推理失败 | 请查看日志详情 |
| `DEVICE_UNAVAILABLE` | 计算设备不可用 | 请在设置中更换设备 |
| `INTERNAL` | 内部错误 | 请查看日志并重试 |

**文案模式**：`{发生了什么}。{建议动作}`。技术 `detail` 放「详细信息」折叠区，不直接展示裸栈。

---

## 5. 前端实现结构（i18n）

> 可选 vue-i18n，或轻量自研 `t('key')`。P1-M02 建议 **轻量字典**，避免过早引重框架；结构对齐 i18n，便于以后替换。

```
desktop/src/locales/
├── index.ts          # t(), setLocale, getLocale
├── zh-CN.ts          # 默认，必填且全量
└── en-US.ts          # 可选，后续再补；缺 key 时回落 zh-CN
```

```ts
// 使用方式（示意）
t('nav.workbench')      // => 工作台
t('action.startInfer')  // => 开始推理
t('status.ready')       // => 就绪
```

**约定**

1. **禁止**在 `.vue` 模板里写死用户可见中文以外的英文标题；组件文案一律 `t()`
2. key 命名：`域.语义` 如 `nav.models`、`error.modelLoadFailed`、`empty.noProject`
3. 单复数：中文无复数；数值插值用 `{count}`
4. 默认 `zh-CN`；设置中可留语言项（UI 仍中文优先）
5. **专名不进翻译**：模板中直接写 `YOLO` / `ONNX`，不参与替换

### 5.1 示例字典片段（zh-CN）

```ts
export default {
  'app.name': 'YOLO Vision Workbench',
  'app.tagline': '专业 AI 视觉工程平台',

  'nav.workbench': '工作台',
  'nav.projects': '项目管理',
  'nav.models': '模型管理',
  'nav.datasets': '数据集',
  'nav.tasks': '推理任务',
  'nav.devices': '设备管理',
  'nav.settings': '系统设置',

  'action.openProject': '打开项目',
  'action.newProject': '新建项目',
  'action.startInfer': '开始推理',
  'action.pause': '暂停',
  'action.resume': '继续',
  'action.cancel': '取消',
  'action.save': '保存',
  'action.loadModel': '加载模型',
  'action.unloadModel': '卸载模型',
  'action.restartBackend': '重启后端服务',

  'status.ready': '就绪',
  'status.starting': '启动中',
  'status.connecting': '连接中',
  'status.restarting': '重启中',
  'status.failed': '失败',
  'status.unhealthy': '状态异常',

  'panel.health': '系统状态',
  'panel.logs': '日志',
  'panel.properties': '属性',
  'panel.parameters': '参数',
  'panel.results': '识别结果',

  'log.level.DEBUG': '调试',
  'log.level.INFO': '信息',
  'log.level.WARNING': '警告',
  'log.level.ERROR': '错误',
  'log.level.CRITICAL': '严重',

  'empty.noProject': '打开或新建项目以开始',
  'empty.noResult': '选择模型与图片，点击「开始推理」',
  'empty.noModel': '在「模型管理」中添加模型配置',
  'empty.noTask': '暂无推理任务',

  'error.INTERNAL': '内部错误。请查看日志并重试',
  'error.MODEL_LOAD_FAILED': '模型加载失败。请检查权重文件与运行依赖'
}
```

---

## 6. 日志中文化

| 项 | 规范 |
|----|------|
| 落盘日志 | 中文 message，模块名可英文 `model_manager` |
| 推送到 UI | 级别经术语表翻译后展示 |
| 避免 | 中英夹杂短句堆砌；能中文则中文 |
| 调试信息 | 可含英文标识符 |

示例：

- ✅ `模型 person 加载完成，耗时 123ms`
- ✅ `后端服务已在 127.0.0.1:8765 启动`
- ❌ `model load OK`（用户日志面板）
- ❌ `Health check failed`（用户可见）

---

## 7. 后端返回与前端展示分离

| 数据 | 语言 | 说明 |
|------|------|------|
| `error.code` | 英文 | 稳定协议 |
| `error.message` | 可中文 | 给开发者；UI 优先用 code 映射 |
| 任务 `status` | 英文枚举 | `running` |
| UI 状态 | 中文 | `t('status.running')` → 进行中 |
| `class_name` | 模型原始 | 逻辑/过滤 |
| `display_name` | 渲染 | 可中文映射 |

---

## 8. 迁移策略（自 P1-M01）

1. P1-M02 重做壳层时 **直接落地** `locales/zh-CN.ts`，不在旧文案上打补丁
2. 新组件禁止写死英文 UI 词
3. 历史 `App.vue` 中 Health/Logs/Ping 等改为：系统状态 / 日志 / 心跳
4. 每增加页面，同步补充字典与术语表
5. 代码评审检查项：扫用户可见字符串是否走 `t()`

---

## 9. 验收清单（中文化）

- [ ] 七导航全中文
- [ ] 无 Dashboard/Health/Logs/Settings 等英文 UI 标题
- [ ] 任务状态全中文
- [ ] 错误提示含「现象 + 建议」
- [ ] 日志级别中文
- [ ] 专名保留英文
- [ ] 字典目录存在且 key 规范
