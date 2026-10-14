# YOLO Vision Workbench · P1 阶段验收与评估

> 日期：2026-10-13
> 产品名：**YOLO Vision Workbench**
> 范围：Phase A–D 主体（基础通信 / 数据与模型 / Pipeline·Task·Profile / UI 壳与工作台）

---

## 1. 里程碑完成情况

| 里程碑 | 内容 | 状态 |
|--------|------|------|
| M01 | Electron+Vue3+TS、Python Backend、Supervisor、WS、loguru | 完成 |
| — | UI 设计规范 / 中文化 / IA 文档 | 完成 |
| M02 | 中文化 UI 壳层、五区布局、七模块导航、主题 | 完成 |
| M03 | 更名 YOLO Vision Workbench、中文系统菜单、模型管理底座 | 完成 |
| M04 | Task / Pipeline / Session、图片推理画布闭环、mock 演示模型 | 完成 |
| M05 | SQLite schema/DAO、任务与帧结果持久化、任务页 | 完成 |
| M06 | Inference Profile 保存/应用、跳帧/框持续参数 | 完成 |
| M07 | 项目新建/打开/列表、DB 切换、菜单联动 | 完成 |
| 收尾 | 项目切换刷新、文件夹推理 UI、**真实 YOLO(yolov8n)** | 完成 |

---

## 2. 核心能力（已可演示）

1. 启动桌面端自动拉起 Python 后端（中文状态栏）
2. 中文工作台：选图/选文件夹、多模型、conf、标签模板、配置方案
3. 推理结果画布叠加 + 列表高亮/隐藏
4. 模型管理：YAML 扫描、中文类别映射、加载/卸载
5. 项目管理：新建/打开，任务库按项目隔离
6. 推理任务页：进度、状态、取消
7. **真实推理**：`coco_yolov8n`（ultralytics / torch CPU）+ `demo` mock
8. 日志双通道、统一 WS JSON 协议

---

## 3. 验证摘要

| 脚本/检查 | 结果 |
|-----------|------|
| smoke_ws.py | OK |
| smoke_model.py | OK（显示名中文） |
| smoke_detect.py | OK（mock 多对象） |
| smoke_profile.py | OK |
| smoke_task_persist.py | OK |
| smoke_project.py | OK |
| smoke_yolo.py | OK（真实 YOLO 加载+推理） |
| npm build / vue-tsc | 通过 |

---

## 4. 已知限制（P1）

- 画布为 Canvas2D（非 Konva），渲染契约已对齐，可替换
- 视频 / 摄像头 / 导出未做（属 P3/P4）
- 跨模型 NMS、级联 Pipeline 未做
- 结果编辑 ops 写库未做
- 日志偶发重复
- 文件夹任务在工作台仅提示 task_id，完整结果在任务页/DB

---

## 5. 下一步评估（建议）

| 优先级 | 方向 | 理由 |
|--------|------|------|
| **P2-A** | 工作台结果回放与项目媒体库 | 用好已有 SQLite 结果，形成日常闭环 |
| **P2-B** | 视频任务 + 跳帧/框缓存 + 时间轴 | 产品差异化核心 |
| **P2-C** | 视频导出（原视频+JSON+ops） | 工程交付场景 |
| P3 | USB/RTSP 摄像头实时 | 现场能力 |
| P4 | ONNX/TensorRT/RKNN | 硬件扩展（接口已预留） |

**推荐下一批：P2-B 视频检测（含跳帧与框持续）→ 顺带做导出。**

---

## 6. 启动方式（汇总）

```powershell
# 后端依赖（已含 ultralytics）
cd backend
uv venv
uv pip install -r requirements/base.txt -r requirements/yolo.txt

# 桌面端
cd ../desktop
npm install
npm run dev
```

模型：`models/examples/`（demo / coco_yolov8n / person）
