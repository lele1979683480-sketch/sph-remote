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

# ---- 登录 Cookie(手机导出后粘贴到网页配置, 优先于账号密码) ----
JUZI_COOKIE = os.environ.get("JUZI_COOKIE", "")
IMT_COOKIE = os.environ.get("IMT_COOKIE", "")

# ---- 登录凭证 localStorage(橘子/imt 实际把登录态存 localStorage, 优先于 Cookie) ----
JUZI_LOCALSTORAGE = os.environ.get("JUZI_LOCALSTORAGE", "")
IMT_LOCALSTORAGE = os.environ.get("IMT_LOCALSTORAGE", "")


def parse_localstorage(s: str) -> dict:
    """解析 localStorage JSON(登录凭证通常以 {key: value} 形式存这里)"""
    import json
    s = (s or "").strip()
    if not s:
        return {}
    try:
        d = json.loads(s)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def parse_cookie(cookie_str: str, default_domain: str) -> list:
    """解析 Cookie: 支持 JSON 数组(Cookie-Editor导出) 和 'k=v; k2=v2' 两种格式"""
    import json
    s = (cookie_str or "").strip()
    if not s:
        return []
    if s.startswith("["):
        try:
            arr = json.loads(s)
            out = []
            for c in arr:
                if not c.get("name"):
                    continue
                out.append({
                    "name": str(c["name"]).strip(),
                    "value": str(c.get("value", "")).strip(),
                    "domain": str(c.get("domain") or default_domain),
                    "path": str(c.get("path") or "/"),
                })
            return out
        except Exception:
            pass
    # k=v; k2=v2 格式
    out = []
    for part in s.split(";"):
        part = part.strip()
        if "=" in part:
            k, v = part.split("=", 1)
            out.append({"name": k.strip(), "value": v.strip(),
                        "domain": default_domain, "path": "/"})
    return out
