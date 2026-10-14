# P3-C 验收要点

操作记录：隐藏/显示框持久化

## 后端

- [x] dao：append_op / list_ops / set_object_visible / set_object_style
- [x] ops.setVisible / ops.setStyle / ops.list
- [x] objects.visible 更新 + ops 表记账

## 前端

- [x] 结果列表「隐藏/显示」写回 DB
- [x] 图片任务 frame_id=0；视频任务当前帧

## 导出

- [x] draw 跳过 visible=false（沿用）

## 验证

- [x] smoke_ops.py → OPS_SMOKE_OK
- [x] build + typecheck 通过
