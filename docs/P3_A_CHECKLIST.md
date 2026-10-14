# P3-A 验收要点

视频结果时间轴 / 帧回放

## 后端

- [x] `database/results.py`：list_task_frames / get_frame_objects / extract_video_frame_jpeg
- [x] `result.frames` / `result.frame` / `result.preview`

## 前端

- [x] 检测完成后时间轴滑条
- [x] 选帧加载预览 + 框叠加 + 结果列表

## 验证

- [x] smoke_replay.py → REPLAY_SMOKE_OK
- [x] 30 帧索引 / 对象中文 / jpeg 预览
- [x] build + typecheck 通过
