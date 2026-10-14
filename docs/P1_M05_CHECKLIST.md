# P1-M05 验收要点

SQLite 持久化 + 推理任务页绑定

## 后端

- [x] `database/schema.sql`：tasks / media / frames / objects / ops / models / profiles
- [x] `connection.py`：WAL、foreign_keys、migrate（schema_migrations）
- [x] `dao.py`：upsert_task / list_tasks / save_frame_result
- [x] Task 生命周期写入 SQLite
- [x] detect 结果写入 frames + objects（geom_json / track_id 预留）
- [x] `task.list` / `task.get` / `task.cancel`

## 前端

- [x] 推理任务页：列表、中文状态、进度条、取消
- [x] 实时 `task.progress` / `task.done` 合并进列表

## 验证

- [x] `smoke_task_persist.py` → TASK_PERSIST_OK
- [x] `projects/default/database.sqlite` 生成
- [x] build + typecheck 通过
