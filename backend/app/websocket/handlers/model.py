"""Model management WebSocket handlers."""

from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger

from app.websocket.protocol import MessageType, make_error, make_message
from app.websocket.server import ConnectionContext, WebSocketHub


def register_model_handlers(hub: WebSocketHub, model_manager) -> None:
    async def on_list(msg: dict[str, Any], ctx: ConnectionContext) -> dict[str, Any]:
        models = model_manager.list_models()
        return make_message(
            "model.list",
            {"ok": True, "models": models},
            id_=msg.get("id"),
        )

    async def on_load(msg: dict[str, Any], ctx: ConnectionContext) -> dict[str, Any]:
        data = msg.get("data") or {}
        model_ids = data.get("model_ids")
        single = data.get("model_id")
        external_path = data.get("external_path")
        if external_path:
            try:
                item = model_manager.load_external(
                    str(external_path),
                    backend=str(data.get("backend") or "yolo"),
                    name=data.get("name"),
                )
                return make_message("model.load", {"ok": True, "models": [item], "errors": []}, id_=msg.get("id"))
            except Exception as exc:  # noqa: BLE001
                return make_error(
                    "model.load",
                    "MODEL_LOAD_FAILED",
                    str(exc),
                    id_=msg.get("id"),
                    detail={"external_path": external_path},
                )
        if not model_ids and single:
            model_ids = [single]
        if not model_ids or not isinstance(model_ids, list):
            return make_error(
                "model.load",
                "BAD_REQUEST",
                "model_ids is required",
                id_=msg.get("id"),
            )

        loaded: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        for mid in model_ids:
            try:
                loaded.append(model_manager.load(str(mid), model_path=data.get("model_path")))
            except Exception as exc:  # noqa: BLE001
                logger.warning("model.load failed {}: {}", mid, exc)
                errors.append({"model_id": mid, "message": str(exc)})

        if errors and not loaded:
            return make_error(
                "model.load",
                "MODEL_LOAD_FAILED",
                "all models failed to load",
                id_=msg.get("id"),
                detail={"errors": errors},
            )
        return make_message(
            "model.load",
            {"ok": True, "models": loaded, "errors": errors},
            id_=msg.get("id"),
        )

    async def on_unload(msg: dict[str, Any], ctx: ConnectionContext) -> dict[str, Any]:
        model_id = msg.get("data", {}).get("model_id")
        if not model_id:
            return make_error(
                "model.unload",
                "BAD_REQUEST",
                "model_id is required",
                id_=msg.get("id"),
            )
        model_manager.unload(str(model_id))
        return make_message(
            "model.unload",
            {"ok": True, "model_id": model_id},
            id_=msg.get("id"),
        )

    async def on_refresh(msg: dict[str, Any], ctx: ConnectionContext) -> dict[str, Any]:
        model_manager.refresh()
        return make_message(
            "model.list",
            {"ok": True, "models": model_manager.list_models()},
            id_=msg.get("id"),
        )

    async def on_class_display(msg: dict[str, Any], ctx: ConnectionContext) -> dict[str, Any]:
        data = msg.get("data") or {}
        model_id = data.get("model_id")
        mapping = data.get("class_display") or {}
        class_colors = data.get("class_colors")
        class_color_mode = data.get("class_color_mode")
        if not model_id:
            return make_error("model.classDisplay", "BAD_REQUEST", "model_id required", id_=msg.get("id"))
        cfg = model_manager.get_config(str(model_id))
        if cfg is None:
            return make_error("model.classDisplay", "NOT_FOUND", f"model not found: {model_id}", id_=msg.get("id"))
        from app.model_manager.display import update_class_display

        try:
            result = update_class_display(
                cfg,
                dict(mapping),
                class_colors=dict(class_colors) if class_colors is not None else None,
                class_color_mode=class_color_mode,
            )
        except Exception as exc:  # noqa: BLE001
            return make_error("model.classDisplay", "INTERNAL", str(exc), id_=msg.get("id"))
        return make_message(
            "model.classDisplay",
            {"ok": True, "model_id": model_id, **result},
            id_=msg.get("id"),
        )

    async def on_import(msg: dict[str, Any], ctx: ConnectionContext) -> dict[str, Any]:
        data = msg.get("data") or {}
        weight_path = data.get("weight_path")
        if not weight_path:
            return make_error("model.import", "BAD_REQUEST", "weight_path required", id_=msg.get("id"))
        try:
            from app.model_manager.importer import import_local_model

            result = import_local_model(
                str(weight_path),
                models_dir=model_manager._models_dir,
                name=data.get("name"),
                backend=str(data.get("backend") or "yolo"),
                task=str(data.get("task") or "detect"),
            )
            model_manager.refresh()
            model_manager.init_class_lists()
        except Exception as exc:  # noqa: BLE001
            logger.exception("model.import failed")
            return make_error("model.import", "INTERNAL", str(exc), id_=msg.get("id"))
        item = model_manager.get_config(result["model_id"])
        payload = item.public_dict() if item else result
        payload["class_list"] = model_manager.list_models()
        # prefer fresh class_list from list_models
        for m in model_manager.list_models():
            if m["model_id"] == result["model_id"]:
                payload = m
                break
        return make_message("model.import", {"ok": True, "model": payload}, id_=msg.get("id"))


    async def on_download(msg: dict[str, Any], ctx: ConnectionContext) -> dict[str, Any]:
        data = msg.get("data") or {}
        from app.model_manager.downloader import HUB_NAME, download_weight

        raw_model_ids = data.get("model_ids")
        model_ids = raw_model_ids if raw_model_ids is not None else list(HUB_NAME)
        if not isinstance(model_ids, list) or not model_ids:
            return make_error(
                "model.downloadBuiltin",
                "BAD_REQUEST",
                "model_ids must be a non-empty list",
                id_=msg.get("id"),
            )
        model_ids = list(dict.fromkeys(str(mid) for mid in model_ids))
        if len(model_ids) > len(HUB_NAME):
            return make_error(
                "model.downloadBuiltin",
                "BAD_REQUEST",
                f"at most {len(HUB_NAME)} builtin models can be downloaded at once",
                id_=msg.get("id"),
            )

        loop = asyncio.get_running_loop()
        results = []
        for mid in model_ids:
            cfg = model_manager.get_config(mid)
            if mid not in HUB_NAME or cfg is None or cfg.backend != "yolo":
                results.append({"model_id": mid, "ok": False, "error": "没有可下载的内置模型权重"})
                continue

            dest = model_manager.resolve_weight(cfg)

            def report_progress(message: str, model_id: str = mid) -> None:
                event = make_message(
                    "model.download.progress",
                    {"model_id": model_id, "message": message},
                )
                try:
                    asyncio.run_coroutine_threadsafe(hub.broadcast(event), loop)
                except RuntimeError:
                    logger.debug("download progress skipped after backend shutdown")

            try:
                path = await asyncio.to_thread(download_weight, mid, dest, progress=report_progress)
                results.append({"model_id": mid, "ok": True, "path": str(path)})
            except Exception as exc:  # noqa: BLE001
                results.append({"model_id": mid, "ok": False, "error": str(exc)})
        model_manager.refresh()
        model_manager.init_class_lists()
        return make_message("model.downloadBuiltin", {"ok": True, "results": results}, id_=msg.get("id"))

    hub.register("model.list", on_list)
    hub.register("model.downloadBuiltin", on_download)
    hub.register("model.load", on_load)
    hub.register("model.unload", on_unload)
    hub.register("model.refresh", on_refresh)
    hub.register("model.classDisplay", on_class_display)
    hub.register("model.import", on_import)
