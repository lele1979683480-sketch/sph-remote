# -*- coding: utf-8 -*-
"""SPH 远程下单配置(GitHub Actions 运行)
商品编号全部由环境变量/Secrets 注入,不硬编码。
"""
import os

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE, "..", "data")
ORDERS_FILE = os.path.join(DATA_DIR, "orders.json")

# ---- 橘子平台商品编号(由 Secrets 覆盖) ----
JUZI_PLAY_GOODS = os.environ.get("JUZI_PLAY_GOODS", "6862")       # 播放
JUZI_FORWARD_GOODS = os.environ.get("JUZI_FORWARD_GOODS", "9044") # 转发

# ---- imt 平台商品编号(由 Secrets 覆盖,赞/爱心独立) ----
IMT_LIKE_GOODS = os.environ.get("IMT_LIKE_GOODS", "")
IMT_HEART_GOODS = os.environ.get("IMT_HEART_GOODS", "")

# ---- 订单状态 ----
ST_PENDING = "pending"          # 排队中
ST_PROCESSING = "processing"    # 处理中
ST_SUCCESS = "success"          # 全部成功
ST_FAILED = "failed"            # 全部失败
ST_PARTIAL = "partial_success"  # 部分成功

# 项目状态
IT_WAIT = "wait"                # 等待中
IT_PROCESSING = "processing"    # 处理中
IT_SUCCESS = "success"          # 成功
IT_FAILED = "failed"            # 失败

# 平台
PLATFORM_JUZI = "juzi"
PLATFORM_IMT = "imt"

# ---- 登录凭据(Secrets 注入) ----
JUZI_ACCOUNT = os.environ.get("JUZI_ACCOUNT", "")
JUZI_PASSWORD = os.environ.get("JUZI_PASSWORD", "")
IMT_ACCOUNT = os.environ.get("IMT_ACCOUNT", "")
IMT_PASSWORD = os.environ.get("IMT_PASSWORD", "")
