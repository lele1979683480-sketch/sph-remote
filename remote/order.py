# -*- coding: utf-8 -*-
"""订单处理: 创建 -> 解析视频 -> 分项目下单(播放/转发/赞/爱心) -> 汇总状态
规则:
  - 视频解析失败 -> 整个订单失败,不继续下单
  - 各项目独立执行、独立状态; 单项目失败不影响其他项目
  - 总体状态: 全部成功=success, 全部失败=failed, 部分成功=partial_success
"""
import time

import config
import db
import imt
import juzi
import scraper

ITEM_LABEL = {
    "play": "播放",
    "share": "转发",
    "like": "点赞",
    "heart": "爱心",
}


def _target_items(targets: dict) -> list:
    """返回数量>0的项目列表 [(key, qty)]"""
    return [(k, int(v)) for k, v in (targets or {}).items()
            if int(v or 0) > 0 and k in ITEM_LABEL]


def _normalize_targets(targets: dict) -> dict:
    """赞+爱心同时填时,合并为同一个 imt 任务,数量取较小值(与电脑版一致)。
    例: 赞15 爱心10 -> 赞10 爱心10(一次任务同时做两个动作)。
    """
    t = {k: int(v or 0) for k, v in (targets or {}).items()}
    like = t.get("like", 0)
    heart = t.get("heart", 0)
    if like > 0 and heart > 0:
        m = min(like, heart)
        t["like"] = m
        t["heart"] = m
        t["_combined_imt"] = True
    return t


def _step(no: str, text: str, log_kind: str = "info"):
    """更新订单当前步骤 + 追加日志"""
    db.update_order(no, step=text)
    db.add_log(log_kind, f"订单{no} {text}")


def _goods_ref(key: str) -> str:
    """取项目对应的商品编号(全部来自配置,不硬编码)"""
    if key == "play":
        return config.JUZI_PLAY_GOODS
    if key == "share":
        return config.JUZI_FORWARD_GOODS
    if key == "like":
        return config.IMT_LIKE_GOODS
    if key == "heart":
        return config.IMT_HEART_GOODS
    return ""


def _run_item(no: str, key: str, qty: int, url: str, video: dict,
              combined: bool = False) -> dict:
    """执行单个项目下单,返回该项目的最终字段(用于 update_item)
    combined: 赞+爱心已合并为同一个 imt 任务(在 like 项目执行, heart 标记并入)
    """
    label = ITEM_LABEL[key]
    goods = _goods_ref(key)

    def rep(text):
        db.update_item(no, key, step=text)
        db.add_log("order", f"订单{no} [{label}] {text}")

    db.update_item(no, key, status=config.IT_PROCESSING,
                   step=f"{label}开始处理", qty=qty, goods_ref=goods)
    db.add_log("order", f"订单{no} [{label}] 开始下单 数量={qty}")

    if key in ("play", "share"):
        platform = config.PLATFORM_JUZI
        if not goods:
            return _item_fail(no, key, label, "未配置播放/转发商品编号")
        result = juzi.order(goods, video, qty, step_cb=rep)
    elif key == "heart" and combined:
        # 爱心已并入点赞任务,不再单独下单
        fields = {
            "status": config.IT_SUCCESS,
            "step": "已并入点赞+爱心任务",
            "result": "与点赞合并为同一任务",
            "platform": config.PLATFORM_IMT,
            "platform_order_no": "",
            "error": "",
        }
        db.update_item(no, key, **fields)
        db.add_log("ok", f"订单{no} [爱心] 已并入点赞+爱心任务(数量={qty})")
        return fields
    else:
        platform = config.PLATFORM_IMT
        title = "点赞爱心" if (key == "like" and combined) else \
            ("点赞" if key == "like" else "爱心")
        result = imt.order(url, qty, title=title, goods_ref=goods, step_cb=rep)

    if result.get("ok"):
        fields = {
            "status": config.IT_SUCCESS,
            "step": f"{label}下单成功",
            "result": result.get("message", ""),
            "platform": platform,
            "platform_order_no": result.get("platform_order_no", ""),
            "error": "",
        }
        db.update_item(no, key, **fields)
        db.add_log("ok", f"订单{no} [{label}] 下单成功: {result.get('message')}")
        return fields
    return _item_fail(no, key, label, result.get("message", "下单失败"))


def _item_fail(no: str, key: str, label: str, err: str) -> dict:
    fields = {
        "status": config.IT_FAILED,
        "step": f"{label}下单失败",
        "error": err,
        "result": err,
    }
    db.update_item(no, key, **fields)
    db.add_log("error", f"订单{no} [{label}] 下单失败: {err}")
    return fields


def _overall_status(no: str) -> tuple:
    """根据各项目下单结果汇总, 返回 (status, completed, step)。
    只表达"是否已提交下单", 不判定达标(达标由 check 抓取后判定)。
    - 至少一个项目下单成功 -> processing(执行中,等数据达标), completed=False
    - 全部项目下单失败     -> failed, completed=True
    """
    order = db.get_order(no)
    items = order.get("items") or {}
    active = [k for k, v in (order.get("targets") or {}).items() if int(v or 0) > 0]
    if not active:
        return config.ST_FAILED, True, "无有效下单项目"
    statuses = {items.get(k, {}).get("status") for k in active}
    if statuses == {config.IT_FAILED} or statuses == {None} or not statuses:
        return config.ST_FAILED, True, "下单失败"
    return config.ST_PROCESSING, False, "已下单，等待数据达标"


def process_order(url: str, targets: dict) -> dict:
    """创建订单并自动下单。返回订单记录。"""
    # 归一化:赞+爱心合并为同一任务,数量取较小值
    targets = _normalize_targets(targets)
    combined = bool(targets.pop("_combined_imt", False))

    # 幂等:同链接+同目标且未完成的订单已存在,则拒绝重复下单
    for exist in db.active_orders():
        if exist.get("url") == url and (exist.get("targets") or {}) == targets:
            db.add_log("warn", f"已有相同订单({exist['order_no']})处理中,拒绝重复下单")
            return exist

    order = db.add_order(url, targets)
    no = order["order_no"]
    _step(no, "订单已创建,开始处理")
    db.add_log("order", f"订单{no} 创建: {url} 目标={targets}")

    # 1. 解析视频链接(失败即整单失败,不继续下单)
    _step(no, "正在解析视频链接")
    data = scraper.scrape(url)
    if not data:
        err = f"视频链接解析失败,无法获取视频数据: {url}"
        db.update_order(no, status=config.ST_FAILED, step="解析视频失败", error=err)
        db.add_log("error", f"订单{no} {err}")
        return db.get_order(no)
    db.update_order(no, video_name=data.get("author") or "",
                    title=data.get("title") or "",
                    init={k: data.get(k, 0) for k in ("like", "heart", "comment", "share", "play")},
                    cur={k: data.get(k, 0) for k in ("like", "heart", "comment", "share", "play")},
                    step=f"视频解析成功: {data.get('author') or ''}")
    db.add_log("info", f"订单{no} 视频解析成功: 博主={data.get('author')} "
                       f"赞{data.get('like')} 爱心{data.get('heart')} "
                       f"评论{data.get('comment')} 转发{data.get('share')}")

    # 2. 分项目下单
    db.update_order(no, status=config.ST_PROCESSING)
    video = {"author": data.get("author") or "",
             "title": data.get("title") or "",
             "url": url}
    for key, qty in _target_items(targets):
        _run_item(no, key, qty, url, video, combined=combined)

    # 3. 汇总状态(只表达下单结果,达标由后续抓取判定)
    overall, completed, step = _overall_status(no)
    db.update_order(no, status=overall, completed=completed, step=step)
    db.add_log("ok" if overall != config.ST_FAILED else "error",
               f"订单{no} 处理完成: {step} (status={overall})")
    return db.get_order(no)


def pending_processes() -> list:
    """供测试/手动触发的待处理项(空实现,保持接口)"""
    return []
