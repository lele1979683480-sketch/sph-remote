# -*- coding: utf-8 -*-
"""橘子平台自动下单 —— 纯 API 方案
背景: 平台对 Playwright/浏览器自动化有 TLS 指纹风控, 传统浏览器方案不可靠。
本模块直接调用平台 HTTP API: login -> goodsDetail(取参数模板) -> createOrder。
每步输出详细日志(step_cb)。账号密码来自 GitHub Secrets。
"""
import datetime
import json
import urllib.error
import urllib.parse
import urllib.request

import config

BASE = "https://juzi00.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/120.0.0.0 Safari/537.36")
_LOGIN_TRIES = 3


def _rep(step_cb, s):
    if step_cb:
        step_cb(s)


def _http(method: str, path: str, token: str, form: dict | None = None,
          timeout: int = 30):
    """底层 HTTP 请求, 统一处理错误"""
    url = BASE + path
    headers = {
        "User-Agent": UA,
        "Referer": BASE + "/indexPc.html",
        "Accept": "application/json, text/plain, */*",
    }
    if token:
        headers["Authorization"] = "Bearer " + token
    body = None
    if form:
        body = urllib.parse.urlencode(form).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded;charset=UTF-8"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def login(step_cb=None) -> str | None:
    """账号密码登录, 返回 JWT。平台风控只针对浏览器, API 不受影响。"""
    account = config.JUZI_ACCOUNT.strip()
    pwd = config.JUZI_PASSWORD.strip()
    if not account or not pwd:
        _rep(step_cb, "登录失败:未配置橘子账号密码(请检查 GitHub Secrets)")
        return None
    last_err = ""
    for i in range(_LOGIN_TRIES):
        try:
            r = _http("POST", "/api/login", "", {"UserName": account, "Pwd": pwd})
            if r.get("error") == 0 and r.get("info"):
                _rep(step_cb, f"API 登录成功(第{i + 1}次)")
                return str(r["info"])
            last_err = str(r.get("info", "登录接口返回异常"))
        except Exception as e:
            last_err = str(e)
        if i < _LOGIN_TRIES - 1:
            import time
            time.sleep(2)
    _rep(step_cb, f"API 登录失败:{last_err}")
    return None


def _goods_detail(token: str, goods_ref: str, step_cb=None) -> dict | None:
    """取商品详情(含 ParamsTemplate / MinOrderNum)"""
    try:
        r = _http("GET", f"/api/goodsDetail?Id={goods_ref}", token)
    except Exception as e:
        _rep(step_cb, f"获取商品{goods_ref}详情失败:{e}")
        return None
    if not r or not r.get("Id"):
        _rep(step_cb, f"未找到商品 {goods_ref}(详情接口返回空)")
        return None
    return r


def _match_value(name: str, video: dict) -> str:
    """根据参数名匹配填写值(视频号作品参数命名混乱,按关键词匹配)"""
    n = name or ""
    link = str(video.get("url") or "").strip()
    title = str(video.get("title") or "").strip()
    author = str(video.get("author") or "").strip()
    if "链接" in n or "url" in n.lower():
        return link
    if ("标题" in n or "title" in n.lower() or "作品" in n) and "昵称" not in n:
        return title or author or link
    # 昵称/名称/博主/名字/feedID 一律用博主昵称
    return author or title or link


def order(goods_ref: str, video: dict, quantity: int, step_cb=None) -> dict:
    """在橘子平台对指定商品下单(纯 API)。
    video: {"author": 博主名, "title": 视频标题, "url": 作品链接}
    返回 {"ok": bool, "message": str, "platform_order_no": str}
    """
    def rep(s):
        _rep(step_cb, s)

    try:
        quantity = int(quantity or 0)
    except Exception:
        quantity = 0
    if not goods_ref or quantity <= 0:
        return {"ok": False, "message": f"商品/数量无效:{goods_ref},{quantity}"}

    rep(f"开始处理(橘子平台 API 下单) 商品#{goods_ref} 数量={quantity}")

    # 1. 登录
    token = login(rep)
    if not token:
        return {"ok": False, "message": "橘子平台登录失败"}

    # 2. 商品详情 -> 参数模板
    detail = _goods_detail(token, goods_ref, rep)
    if not detail:
        return {"ok": False, "message": f"获取商品 {goods_ref} 详情失败"}
    tpl = detail.get("ParamsTemplate") or "[]"
    try:
        tpl = json.loads(tpl) if isinstance(tpl, str) else tpl
    except Exception:
        tpl = []
    rep(f"商品参数模板: {[t.get('name') or t.get('key') for t in tpl]}")
    if not tpl:
        return {"ok": False, "message": f"商品 {goods_ref} 无参数模板, 无法下单"}

    # 3. 数量下限检查(自动提升到最小购买量)
    try:
        min_qty = int(detail.get("MinOrderNum") or 0)
    except Exception:
        min_qty = 0
    if min_qty > 0 and quantity < min_qty:
        rep(f"购买数量 {quantity} 小于该商品最小购买量 {min_qty}, 自动调整为 {min_qty}")
        quantity = min_qty

    # 4. 构造 paramsList: [{name, alias, value}]
    params_list = []
    for item in tpl:
        name = item.get("name") or item.get("key") or ""
        key = item.get("key") or name
        params_list.append({
            "name": name,
            "alias": key,
            "value": _match_value(name, video),
        })
    missing = [p["name"] for p in params_list if not p["value"]]
    if missing:
        return {"ok": False, "message": f"缺少下单参数值:{missing}"}
    rep(f"参数值: {json.dumps(params_list, ensure_ascii=False)}")

    # 5. createOrder
    exp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    payload = {
        "GoodsIds": str(goods_ref),
        "OrderNum": str(quantity),
        "OrderParams": json.dumps([params_list], ensure_ascii=False),
        "CfCount": "1",
        "ExpTime": exp,
        "ExeTime": "0",
        "ZxType": "1",
    }
    try:
        r = _http("POST", "/api/createOrder", token, payload, timeout=60)
    except Exception as e:
        return {"ok": False, "message": f"下单请求异常:{e}"}

    # 6. 解析结果: {"error":0,"info":"[{...}]"}
    if r.get("error") != 0:
        return {"ok": False, "message": f"平台返回:{r.get('info', r)}"}
    try:
        inner = json.loads(r.get("info") or "[]")
    except Exception:
        inner = []
    if isinstance(inner, list) and inner:
        first = inner[0] if isinstance(inner[0], dict) else {}
        if first.get("error") == 0:
            msg = str(first.get("msg") or "下单成功")
            rep(f"下单成功: {msg}")
            return {"ok": True, "message": msg, "platform_order_no": ""}
        return {"ok": False, "message": f"下单失败:{first.get('msg')}"}
    rep(f"下单成功: {r.get('info')}")
    return {"ok": True, "message": str(r.get("info") or "下单成功"),
            "platform_order_no": ""}
