# P2-B 验收要点

视频检测：跳帧 + 框持续

## 后端

- [x] VideoTask：每 skip_frame 推理一次
- [x] box_persistence ≤ skip_frame，超出自动钳制
- [x] 窗口外清空框；检测帧/缓存帧写入 SQLite
- [x] video.start / video.cancel
- [x] 进度含 detect_count / fps / 帧数

## 前端

- [x] 选择视频、跳帧/框持续参数
- [x] video.start 启动任务，进度推送
- [x] 视频预览控件

## 验证

- [x] smoke_video.py → VIDEO_SMOKE_OK
- [x] 30 帧 / detect_count=6（skip=5）符合预期
- [x] build + typecheck 通过
