# -*- coding: utf-8 -*-
"""Workflow 入口
用法:
  python main.py order <url> <targets_json>   # 新订单并自动下单
  python main.py check                         # 达标检查(定时任务)
"""
import json
import sys

import check
import order


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
        try:
            targets = json.loads(args[2])
        except Exception:
            print("RESULT: targets 不是合法 JSON")
            sys.exit(1)
        o = order.process_order(url, targets)
        print(f"RESULT: 订单{o['order_no']} status={o['status']}")
        print(f"详情: {o.get('result') or o.get('error') or '-'}")
        sys.exit(0 if o["status"] == "submitted" else 1)
    elif cmd == "check":
        rep = check.run()
        print(f"RESULT: 检查{rep['checked']}单, 新达标{rep['completed']}, 抓取失败{rep['failed']}")
        sys.exit(0)
    else:
        print(f"未知命令:{cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
