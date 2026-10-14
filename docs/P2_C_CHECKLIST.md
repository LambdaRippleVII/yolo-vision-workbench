# P2-C 验收要点

视频导出：原视频 + 检测结果 → 叠加框 mp4

## 后端

- [x] `export/draw.py`：bbox + 标签模板 + 颜色（与 UI 同源字段）
- [x] `export/video_exporter.py`：读结果（SQLite）→ 逐帧绘制 → 写出
- [x] ExportTask + `export.video` 协议
- [x] 任务进度与取消标志

## 前端

- [x] 导出视频按钮 + 保存对话框
- [x] 绑定上次视频检测 task_id

## 验证

- [x] smoke_export.py → EXPORT_SMOKE_OK
- [x] 30 帧 / drawn_frames=30 / 输出 mp4 可读
- [x] build + typecheck 通过

## 修复

- Task 增加 `parent_task_id`（导出溯源）
