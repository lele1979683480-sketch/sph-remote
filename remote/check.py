# -*- coding: utf-8 -*-
"""达标检查:抓取未完成订单的最新数据,判断是否达到目标"""
import config
import db
import scraper


def run(order_no: str = "") -> dict:
    """对未完成订单(或指定订单)抓取数据并判断达标。返回汇总。
    达标定义: 每个有预期的项目 当前 >= 初始 + 预期。
    """
    if order_no:
        o = db.get_order(order_no)
        orders = [o] if o else []
        if not orders:
            db.add_log("warn", f"达标检查: 未找到订单{order_no}")
            return {"checked": 0, "completed": 0, "failed": 0}
    else:
        orders = db.active_orders()
    report = {"checked": 0, "completed": 0, "failed": 0}
    if not orders:
        db.add_log("info", "达标检查: 暂无未完成订单")
        return report
    db.add_log("info", f"达标检查开始: {len(orders)} 单")
    for o in orders:
        targets = o.get("targets") or {}
        items = o.get("items") or {}
        active = [k for k, v in targets.items() if int(v or 0) > 0]
        # 下单失败的订单(所有目标项目均失败)直接完结,不再检查
        if active and all((items.get(k) or {}).get("status") == config.IT_FAILED
                          for k in active):
            db.update_order(o["order_no"], completed=True, step="下单失败,不再检查")
            report["failed"] += 1
            continue
        data = scraper.scrape(o["url"])
        if not data:
            report["failed"] += 1
            db.add_log("warn", f"订单{o['order_no']} 数据抓取失败")
            continue
        cur = {k: data.get(k, 0) for k in ("like", "heart", "comment", "share", "play")}
        init = o.get("init") or {}
        # 达标:每个有目标的项目 当前 >= 初始 + 目标
        need = {k: v for k, v in targets.items() if int(v or 0) > 0}
        all_done = bool(need) and all(
            cur.get(k, 0) >= (init.get(k, 0) + int(v)) for k, v in need.items())
        fields = {"cur": cur}
        if all_done:
            fields["status"] = config.ST_SUCCESS
            fields["completed"] = True
            fields["step"] = "已达标"
        db.update_order(o["order_no"], **fields)
        report["checked"] += 1
        if all_done:
            report["completed"] += 1
            db.add_log("ok", f"订单{o['order_no']} 已达标 ✅ (当前={cur})")
        else:
            db.add_log("info", f"订单{o['order_no']} 检查中: 当前={cur}")
    db.add_log("info", f"达标检查完成: 检查{report['checked']}单, 新达标{report['completed']}, 抓取失败{report['failed']}")
    return report
