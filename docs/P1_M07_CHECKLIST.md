# P1-M07 验收要点

项目管理：新建 / 打开 / 列表与 DB 切换

## 后端

- [x] `project/store.py`：create / open / list / current / save_meta
- [x] 打开项目切换 SQLite（reconnect + migrate）
- [x] project.list / create / open / current / save
- [x] 项目目录：images/videos/models/results/profiles

## 前端

- [x] 项目管理页：新建、列表、打开、当前标记
- [x] 顶栏显示当前项目名
- [x] 系统菜单「打开/新建项目…」跳转项目页

## 验证

- [x] smoke_project.py → PROJECT_SMOKE_OK（工地一期）
- [x] build + typecheck 通过
