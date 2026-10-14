# YOLO Vision Workbench · V1 可用版本说明

> 日期：2026-10-13  
> 状态：**第一版可正常使用**

---

## 1. 现在能做什么

| 模块 | 能力 |
|------|------|
| 启动 | 桌面端自动拉起 Python 后端，中文系统菜单 |
| 项目 | 新建 / 打开 / 切换，独立 SQLite |
| 模型 | YAML 扫描、中文类别映射、加载/卸载；**演示 mock** + **真实 YOLO yolov8n** |
| 图片 | 单图推理、画布叠加、结果列表高亮/隐藏 |
| 文件夹 | 批量推理 + 进度 |
| 配置方案 | Profile 保存/应用（conf、标签模板、跳帧、框持续） |
| 视频 | 跳帧检测、框持续、时间轴帧回放、**导出叠加框 mp4** |
| 摄像头 | USB / RTSP 实时预览 + 检测叠加 |
| 任务 | 列表、进度、取消；结果与操作记入 SQLite |
| 日志 | 文件 + 界面实时 |

---

## 2. 启动

```powershell
# 首次
cd backend
uv venv
uv pip install -r requirements/base.txt -r requirements/yolo.txt

# 日常
cd ..\desktop
npm install
npm run dev
```

模型目录：`models/examples/`（demo / coco_yolov8n / person）  
项目数据：`projects/<名称>/`

---

## 3. 冒烟（全部通过）

`smoke_ws` `model` `detect` `profile` `task_persist` `project` `video` `export` `replay` `ops` `camera` `yolo`

---

## 4. 已知限制

- 画布为 Canvas2D（非 Konva）
- 中文标签 OpenCV 字体，非系统 TTF
- 摄像头录制生成 VideoTask 未做
- ONNX / TensorRT / RKNN 未接（接口已预留）
- 长视频进度消息偏密

---

## 5. 文档索引

`docs/ARCHITECTURE_v0.2.md` · `IMPLEMENTATION_DESIGN_v0.1.md` · `UI_DESIGN_SPEC.md` · `LOCALIZATION.md` · `IA.md` · `P1_ACCEPTANCE.md` · 各 `P*_CHECKLIST.md`
