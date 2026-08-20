# -*- coding: utf-8 -*-
"""Workflow 入口
用法:
  python main.py order <url> <targets_json>   # 新订单并自动下单
  python main.py check                         # 达标检查(定时任务)
"""
import json
import re
import sys

import check
import config
import order

_KEY_MAP = {
    "play": "play", "播放": "play", "播": "play",
    "share": "share", "转发": "share", "转": "share",
    "like": "like", "赞": "like", "点赞": "like",
    "heart": "heart", "爱心": "heart", "爱": "heart",
    "comment": "comment", "评论": "comment", "评": "comment",
}


def parse_targets(text: str) -> dict | None:
    """解析 targets: 支持 'play:1;share:50' 文本格式(网页提交) 和 JSON 格式"""
    text = (text or "").strip()
    if not text:
        return None
    if text.startswith("{"):
        try:
            d = json.loads(text)
            if isinstance(d, dict):
                return d
        except Exception:
            pass
        text = text.strip("{}")  # 兼容引号被剥离的 {play:1} 格式
    targets = {}
    for part in re.split(r"[;；,，\s]+", text):
        if not part:
            continue
        m = re.match(r"([A-Za-z\u4e00-\u9fa5]+)\s*[:：=]?\s*(\d+)", part)
        if not m:
            continue
        key = _KEY_MAP.get(m.group(1).strip().lower())
        if key:
            targets[key] = int(m.group(2))
    if not targets:
        return None
    return targets


def main():
    args = sys.argv[1:]
    if not args:
        print("用法: python main.py order <url> <json> | check")
        sys.exit(1)
    cmd = args[0]
    if cmd == "order":
        if len(args) < 3:
            print("RESULT: 参数不足(url + targets json)")
            sys.exit(1)
        url = args[1].strip()
        targets = parse_targets(args[2])
        if targets is None:
            print("RESULT: 无法解析目标参数")
            sys.exit(1)
        o = order.process_order(url, targets)
        status = o.get("status", "")
        print(f"RESULT: 订单{o['order_no']} status={status}")
        for key, it in (o.get("items") or {}).items():
            if int((o.get("targets") or {}).get(key, 0) or 0) > 0:
                print(f"  [{key}] {it.get('status')} - {it.get('step')} "
                      f"{('- ' + it.get('error', '')) if it.get('error') else ''}")
        if status in (config.ST_SUCCESS, config.ST_PARTIAL):
            sys.exit(0)
        sys.exit(1)
    elif cmd == "check":
        rep = check.run()
        print(f"RESULT: 检查{rep['checked']}单, 新达标{rep['completed']}, 抓取失败{rep['failed']}")
        sys.exit(0)
    else:
        print(f"未知命令:{cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
