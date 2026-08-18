# -*- coding: utf-8 -*-
"""orders.json 数据读写(workflow 内使用,简单 JSON 数据库)"""
import json
import os
import time

import config


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


def add_order(url: str, targets: dict) -> dict:
    """新增订单记录"""
    data = load()
    date = time.strftime("%Y-%m-%d")
    no = next_order_no(date)
    order = {
        "order_no": no,
        "url": url,
        "video_name": "",
        "title": "",
        "targets": {k: int(v or 0) for k, v in targets.items()},
        "init": {"like": 0, "heart": 0, "comment": 0, "share": 0, "play": 0},
        "cur": {"like": 0, "heart": 0, "comment": 0, "share": 0, "play": 0},
        "status": config.ST_PENDING,
        "platform": "",
        "result": "",
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


def active_orders() -> list:
    """未完成订单(用于达标检查)"""
    data = load()
    return [o for o in data["orders"] if not o.get("completed")]


def add_log(kind: str, message: str) -> None:
    """追加一条运行日志(网页「日志」页显示),最多保留200条"""
    data = load()
    logs = data.setdefault("logs", [])
    logs.append({"time": _now(), "kind": str(kind), "message": str(message)[:300]})
    if len(logs) > 200:
        del logs[: len(logs) - 200]
    save(data)
