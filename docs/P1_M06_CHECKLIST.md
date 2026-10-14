# P1-M06 验收要点

Inference Profile + 多模型参数

## 后端

- [x] `project/profile.py`：ProfilePayload / ProfileStore（SQLite profiles 表）
- [x] profile.list / save / apply / delete
- [x] 启动时 ensure_default（默认配置）

## 前端

- [x] 工作台配置方案：下拉切换、命名保存
- [x] 应用配置恢复：模型勾选、conf、标签模板、跳帧、框持续
- [x] 结果列表显示 model_id 来源

## 验证

- [x] smoke_profile.py → PROFILE_SMOKE_OK
- [x] build + typecheck 通过
