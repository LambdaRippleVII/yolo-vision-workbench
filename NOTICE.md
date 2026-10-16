# NOTICE — 第三方组件与许可

## Ultralytics YOLO

本软件（YOLO Vision Workbench）使用了 [Ultralytics](https://github.com/ultralytics/ultralytics)
提供的 YOLO 推理框架与预训练模型权重，**致敬并感谢 Ultralytics 团队**。

- 项目地址：https://github.com/ultralytics/ultralytics
- 许可协议：**AGPL-3.0**（GNU Affero General Public License v3.0）
- 预训练权重来源：Ultralytics 官方发布（COCO / Objects365 / OpenImagesV7 等）

### 合规说明

1. 本软件后端依赖 `ultralytics` 包进行 YOLO 推理；预训练 `.pt` 权重均来自 Ultralytics 发行渠道。
2. **AGPL-3.0 具有传染性**：若你分发本软件（含安装包）或对外提供基于 Ultralytics/本软件的服务，
   须遵守 AGPL-3.0，包括向用户提供完整对应源代码。
3. 数据集（COCO、Objects365、Open Images V7）的版权归各自权利人所有；本软件仅引用其作为预训练权重的训练集名称。

### 内置模型一览

| 显示名 | 模型 | 数据集 | 权重文件 | 上游 |
|--------|------|--------|----------|------|
| COCO · YOLO26n | YOLO26n | COCO | `weights/yolo26n.pt` | Ultralytics |
| COCO · YOLO11n | YOLO11n | COCO | `weights/yolo11n.pt` | Ultralytics |
| Objects365 · YOLO26n | YOLO26n | Objects365 | `weights/objects365_yolo26n.pt` | Ultralytics |
| OpenImagesV7 · YOLOv8n | YOLOv8n | OpenImagesV7 | `weights/openimages_yolov8n.pt` | Ultralytics |

详见 `models/examples/*.yaml` 中的 `source` 字段与 `models/repository/catalog.yaml`。

## 其他依赖

Electron、Vue、FastAPI、OpenCV 等遵循各自开源许可。
