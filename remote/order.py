# -*- coding: utf-8 -*-
"""处理一个新订单:记录 -> 抓取 -> 下单"""
import re
import time

import config
import db
import juzi
import scraper

_URL_RE = re.compile(r"https?://[^\s]+")


def parse_order_text(text: str) -> dict | None:
    """从网页提交的文本解析订单:链接 + 赞/爱心/评论/转发/播放 + 数量"""
    m = _URL_RE.search(text or "")
    if not m:
        return None
    url = m.group(0).rstrip("。，,；;")
    rest = (text or "")[m.end():]
    targets = {"like": 0, "heart": 0, "comment": 0, "share": 0, "play": 0}
    # 形式1: 赞30 爱心20 播放2500 (数字在指标前,如"播放2500")
    front = re.findall(r"(赞|点赞|爱心|爱|评论|评|转发|转|播放|播)\s*[:：]?\s*(\d+)", rest)
    # 形式2: 30赞 20爱心 (数字在指标后)
    back = re.findall(r"(\d+)\s*(赞|点赞|爱心|爱|评论|评|转发|转|播放|播)", rest)
    hits = back if (len(back) >= len(front) and back) else front
    if not hits:
        return None
    key_map = {"赞": "like", "点赞": "like", "爱心": "heart", "爱": "heart",
               "评论": "comment", "评": "comment", "转发": "share", "转": "share",
               "播放": "play", "播": "play"}
    for a, b in hits:
        kw, num = (a, b) if front and a in key_map else (b, a)
        try:
            targets[key_map[kw]] = int(num)
        except Exception:
            continue
    if sum(targets.values()) <= 0:
        return None
    return {"url": url, "targets": targets}


def process_order(url: str, targets: dict) -> dict:
    """创建订单并自动下单。返回订单记录。"""
    order = db.add_order(url, targets)
    no = order["order_no"]
    # 1. 抓取视频数据(博主名/标题/初始数据)
    data = scraper.scrape(url)
    if data:
        db.update_order(no, video_name=data.get("author") or "",
                        title=data.get("title") or "",
                        init={k: data.get(k, 0) for k in ("like", "heart", "comment", "share", "play")},
                        cur={k: data.get(k, 0) for k in ("like", "heart", "comment", "share", "play")},
                        status=config.ST_PROCESSING)
    else:
        db.update_order(no, status=config.ST_PROCESSING)
    # 2. 自动下单
    results = []
    ok_all = True
    video_name = data.get("author") if data else ""
    if targets.get("play"):
        r = juzi.order(config.JUZI_PLAY_GOODS, video_name, url, targets["play"])
        results.append(f"播放:{r['message']}")
        if not r["ok"]:
            ok_all = False
    if targets.get("share"):
        r = juzi.order(config.JUZI_FORWARD_GOODS, video_name, url, targets["share"])
        results.append(f"转发:{r['message']}")
        if not r["ok"]:
            ok_all = False
    if targets.get("like") or targets.get("heart"):
        results.append("赞/爱心:imt平台暂未接入,请手动下单")
        ok_all = False
    db.update_order(no, status=config.ST_SUBMITTED if ok_all else config.ST_FAILED,
                    platform="juzi" if (targets.get("play") or targets.get("share")) else "",
                    result=";".join(results),
                    error="" if ok_all else ";".join(results))
    return db.get_order(no)
