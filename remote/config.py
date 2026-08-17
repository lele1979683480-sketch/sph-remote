# -*- coding: utf-8 -*-
"""SPH 远程下单配置(GitHub Actions 运行)"""
import os

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE, "..", "data")
ORDERS_FILE = os.path.join(DATA_DIR, "orders.json")

# 商品编号(橘子平台, 可用 GitHub Secrets 覆盖: 改 secret 即可切换商品)
JUZI_PLAY_GOODS = os.environ.get("JUZI_PLAY_GOODS", "6862")       # 视频号-独家作品播放
JUZI_FORWARD_GOODS = os.environ.get("JUZI_FORWARD_GOODS", "9044") # SPH-独家作品转发(标题下单)

# 订单状态
ST_PENDING = "pending"
ST_PROCESSING = "processing"
ST_SUBMITTED = "submitted"
ST_FAILED = "failed"
ST_COMPLETED = "completed"

# 登录橘子平台(从环境变量读取,由 GitHub Secrets 注入)
JUZI_ACCOUNT = os.environ.get("JUZI_ACCOUNT", "")
JUZI_PASSWORD = os.environ.get("JUZI_PASSWORD", "")

# 登录 imt 悬赏平台(赞/爱心, 由 GitHub Secrets 注入)
IMT_ACCOUNT = os.environ.get("IMT_ACCOUNT", "")
IMT_PASSWORD = os.environ.get("IMT_PASSWORD", "")
