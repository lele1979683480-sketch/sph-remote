# -*- coding: utf-8 -*-
"""达标检查:抓取未完成订单的最新数据,判断是否达到目标"""
import config
import db
import scraper


def run() -> dict:
    """对所有未完成订单抓取数据并判断达标。返回汇总。"""
    orders = db.active_orders()
    report = {"checked": 0, "completed": 0, "failed": 0}
    if not orders:
        db.add_log("info", "达标检查: 暂无未完成订单")
        return report
    db.add_log("info", f"达标检查开始: {len(orders)} 单")
    for o in orders:
        data = scraper.scrape(o["url"])
        if not data:
            report["failed"] += 1
            db.add_log("warn", f"订单{o['order_no']} 数据抓取失败")
            continue
        cur = {k: data.get(k, 0) for k in ("like", "heart", "comment", "share", "play")}
        init = o.get("init") or {}
        targets = o.get("targets") or {}
        # 达标:每个有目标的项目 当前 >= 初始 + 目标
        need = {k: v for k, v in targets.items() if v > 0}
        all_done = bool(need) and all(
            cur.get(k, 0) >= (init.get(k, 0) + v) for k, v in need.items())
        fields = {"cur": cur}
        if all_done:
            fields["status"] = config.ST_COMPLETED
            fields["completed"] = True
        db.update_order(o["order_no"], **fields)
        report["checked"] += 1
        if all_done:
            report["completed"] += 1
            db.add_log("ok", f"订单{o['order_no']} 已达标 ✅ (当前={cur})")
        else:
            db.add_log("info", f"订单{o['order_no']} 检查中: 当前={cur}")
    db.add_log("info", f"达标检查完成: 检查{report['checked']}单, 新达标{report['completed']}, 抓取失败{report['failed']}")
    return report
