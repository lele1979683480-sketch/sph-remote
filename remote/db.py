# -*- coding: utf-8 -*-
"""orders.json 数据读写(workflow 内使用,简单 JSON 数据库)
订单模型: 每个订单含总体状态 + 各项目(播放/转发/赞/爱心)独立状态
"""
import json
import os
import time

import config

ITEM_KEYS = ("play", "share", "like", "heart")

# 状态常量
ST_PENDING = "pending"          # 排队中
ST_PROCESSING = "processing"    # 处理中
ST_SUCCESS = "success"          # 全部成功
ST_FAILED = "failed"            # 全部失败
ST_PARTIAL = "partial_success"  # 部分成功


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def load() -> dict:
    if not os.path.exists(config.ORDERS_FILE):
        return {"orders": [], "counter": {}}
    try:
        with open(config.ORDERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"orders": [], "counter": {}}


def save(data: dict) -> None:
    os.makedirs(config.DATA_DIR, exist_ok=True)
    with open(config.ORDERS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def next_order_no(date: str) -> str:
    """生成业务订单编号:MMDD+当日流水"""
    data = load()
    key = date
    data["counter"][key] = data["counter"].get(key, 0) + 1
    seq = data["counter"][key]
    mmdd = date[2:4] + date[5:7]
    no = f"{mmdd}{seq:02d}"
    save(data)
    return no


def new_item() -> dict:
    return {
        "status": "wait",          # wait/processing/success/failed
        "step": "等待中",
        "error": "",
        "platform": "",            # juzi / imt
        "goods_ref": "",           # 商品编号
        "platform_order_no": "",   # 平台订单号(如返回)
        "result": "",
    }


def add_order(url: str, targets: dict) -> dict:
    """新增订单记录。targets 各项目数量(>0 才下单)。"""
    data = load()
    date = time.strftime("%Y-%m-%d")
    no = next_order_no(date)
    items = {k: new_item() for k in ITEM_KEYS}
    for k in ITEM_KEYS:
        items[k]["qty"] = int(targets.get(k) or 0)
    order = {
        "order_no": no,
        "url": url,
        "video_name": "",
        "title": "",
        "targets": {k: int(v or 0) for k, v in targets.items()},
        "init": {"like": 0, "heart": 0, "comment": 0, "share": 0, "play": 0},
        "cur": {"like": 0, "heart": 0, "comment": 0, "share": 0, "play": 0},
        "items": items,            # 各项目独立状态
        "status": config.ST_PENDING,
        "step": "订单已创建,排队等待处理",
        "error": "",
        "created_at": _now(),
        "updated_at": _now(),
        "completed": False,
    }
    data["orders"].append(order)
    save(data)
    return order


def get_order(order_no: str) -> dict | None:
    data = load()
    for o in data["orders"]:
        if o["order_no"] == order_no:
            return o
    return None


def update_order(order_no: str, **fields) -> None:
    data = load()
    for o in data["orders"]:
        if o["order_no"] == order_no:
            o.update(fields)
            o["updated_at"] = _now()
            break
    save(data)


def update_item(order_no: str, key: str, **fields) -> None:
    """更新订单内某个项目(播放/转发/赞/爱心)的状态"""
    data = load()
    for o in data["orders"]:
        if o["order_no"] == order_no:
            item = o["items"].setdefault(key, new_item())
            item.update(fields)
            o["updated_at"] = _now()
            break
    save(data)


def active_orders() -> list:
    """未完成订单(用于达标检查)"""
    data = load()
    return [o for o in data["orders"] if not o.get("completed")]


def add_log(kind: str, message: str) -> None:
    """追加一条运行日志(网页「日志」页显示),最多保留300条"""
    data = load()
    logs = data.setdefault("logs", [])
    logs.append({"time": _now(), "kind": str(kind), "message": str(message)[:300]})
    if len(logs) > 300:
        del logs[: len(logs) - 300]
    save(data)
