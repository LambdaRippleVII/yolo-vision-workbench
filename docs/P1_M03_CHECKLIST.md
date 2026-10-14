# P1-M03 验收要点

产品名：**YOLO Vision Workbench**（全局更名）

## 更名

- [x] 界面 / 窗口标题 / README / 文档 / Backend title
- [x] package 名 `yolo-vision-workbench-desktop`
- [x] 日志文件前缀 `yolo-vision-workbench_`

## 中文系统菜单

- [x] 文件 / 编辑 / 视图 / 窗口 / 帮助
- [x] 菜单项中文（重新加载、开发者工具、退出…）

## 模型管理底座

- [x] Model YAML schema（class_display 中文映射）
- [x] 扫描 models/ 与 repository
- [x] model.list / model.load / model.unload / model.refresh
- [x] BaseRuntime + YOLORuntime（权重缺失时明确报错；ultralytics 可选）
- [x] 模型管理页显示列表与类别显示名

## 验证

- [x] /health 含 product=YOLO Vision Workbench
- [x] smoke_model.py → person / 人员检测 / display 人员
- [x] build + typecheck 通过
