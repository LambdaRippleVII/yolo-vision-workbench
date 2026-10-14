# P1-M04 验收要点

图片推理闭环：Task + Pipeline + Session + 画布叠加

## 后端

- [x] InferenceSession（绑定 Runtime、predict 计数）
- [x] PipelineEngine（多模型并行 + merge 重编号）
- [x] TaskManager + ImageTask / FolderTask + 取消
- [x] detect.image / detect.folder 协议
- [x] MockRuntime（无权重可联调 UI）
- [x] models/examples/demo.yaml（class_display 中文）
- [x] smoke_detect.py → 人员/安全帽/反光衣

## 前端

- [x] CanvasStage：bbox / 标签模板 / 中文 / 点击选中
- [x] 工作台：选图、多模型、conf、开始推理、结果列表、隐藏框
- [x] Electron 对话框：选图片/文件夹、读图 base64

## 验证

- [x] detect.image 返回合并对象
- [x] build + typecheck 通过

## 说明

- 画布暂用原生 Canvas2D（渲染契约与 Konva 版一致，可后续替换）
- 真实 YOLO 权重：backend=yolo + ultralytics；当前 mock 可演示闭环
