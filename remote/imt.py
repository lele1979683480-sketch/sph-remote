# -*- coding: utf-8 -*-
"""imt 悬赏平台自动下单(赞/爱心) —— 纯 API 方案
imt 是"悬赏"模式: 发布任务(链接+要求+样图), 平台投手接单执行后按量结算。
流程: 登录 -> 生成并上传样图 -> createOrder。
每步输出详细日志(step_cb)。凭证来自 GitHub Secrets(localStorage 或 账号密码)。
"""
import base64
import io
import json
import time
import urllib.error
import urllib.request

import config

BASE = "https://imt.tiankongfeiji.cn/capi"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/120.0.0.0 Safari/537.36")
_LOGIN_TRIES = 3


def _rep(step_cb, s):
    if step_cb:
        step_cb(s)


def _http(path: str, params: dict, creds: dict | None = None,
          timeout: int = 30) -> dict:
    """底层 JSON POST 请求。creds: {un, token, uid}"""
    body = json.dumps(params).encode()
    headers = {
        "User-Agent": UA,
        "Content-Type": "application/json; charset=utf-8",
        "Referer": "https://imt.tiankongfeiji.cn/customer/order_add.html",
        "login-un": (creds or {}).get("un", "0"),
        "login-token": (creds or {}).get("token", "0"),
        "login-uid": str((creds or {}).get("uid", 0)),
        "platform": "0",
    }
    req = urllib.request.Request(BASE + path, data=body, method="POST", headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def _creds_from_localstorage() -> dict | None:
    """从 IMT_LOCALSTORAGE 凭证提取 {un, token, uid}"""
    data = config.parse_localstorage(config.IMT_LOCALSTORAGE)
    un = str(data.get("un_customer") or "").strip()
    token = str(data.get("token_customer") or "").strip()
    uid = str(data.get("uid") or "").strip()
    if not (un and token and uid):
        return None
    return {"un": un, "token": token, "uid": uid}


def login(step_cb=None) -> dict | None:
    """获取 imt 登录凭证。优先级: localStorage凭证 > 账号密码。"""
    # 1) localStorage 凭证(手机导出, 最可靠)
    creds = _creds_from_localstorage()
    if creds:
        # 验证凭证有效性
        try:
            r = _http("/customer/info", {}, creds)
            if r.get("code") == 0:
                _rep(step_cb, f"imt 登录成功(本地凭证) 余额:{r['result'].get('moneyCurrent')}元")
                return creds
            _rep(step_cb, f"imt 本地凭证失效({r.get('msg')}),尝试账号密码")
        except Exception as e:
            _rep(step_cb, f"imt 本地凭证验证异常:{e}")

    # 2) 账号密码登录
    account = config.IMT_ACCOUNT.strip()
    pwd = config.IMT_PASSWORD.strip()
    if not (account and pwd):
        _rep(step_cb, "imt 登录失败:未配置本地凭证或账号密码")
        return None
    last_err = ""
    for i in range(_LOGIN_TRIES):
        try:
            r = _http("/login/pwdLogin", {"un": account, "pwd": pwd})
            res = r.get("result") or {}
            if r.get("code") == 0 and res.get("token"):
                _rep(step_cb, f"imt 登录成功(账号密码,第{i + 1}次)")
                return {"un": account, "token": str(res["token"]),
                        "uid": str(res.get("uid", 0))}
            last_err = str(r.get("msg") or r)
        except Exception as e:
            last_err = str(e)
        if i < _LOGIN_TRIES - 1:
            time.sleep(2)
    _rep(step_cb, f"imt 登录失败:{last_err}")
    return None


def _make_sample_img(qty_label: str) -> str:
    """生成样图(JPEG dataURL, 与前端一致: 宽500 质量20%)"""
    try:
        from PIL import Image, ImageDraw
        img = Image.new("RGB", (500, 660), (255, 255, 255))
        d = ImageDraw.Draw(img)
        d.text((20, 30), "SHP Task Sample", fill=(0, 0, 0))
        d.text((20, 60), "Open the link", fill=(80, 80, 80))
        d.text((20, 90), qty_label, fill=(80, 80, 80))
        d.text((20, 120), "then screenshot as proof", fill=(80, 80, 80))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=20)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception:
        # 无 PIL 时用一张 1x1 的合法 JPEG
        b64 = ("/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0a"
               "HBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAALCAABAAEBAREA/8QAFAABAAAAAAAAAAAAAAAA"
               "AAAACf/EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEAAD8AKp//2Q==")
        return "data:image/jpeg;base64," + b64


def order(url: str, quantity: int, title: str = "点赞", goods_ref: str = "",
          step_cb=None) -> dict:
    """在 imt 平台发布悬赏任务(赞/爱心)。
    title: "点赞" 或 "爱心" 区分任务描述。
    返回 {"ok": bool, "message": str, "platform_order_no": str}
    """
    def rep(s):
        _rep(step_cb, s)

    try:
        quantity = int(quantity or 0)
    except Exception:
        quantity = 0
    if not url or quantity <= 0:
        return {"ok": False, "message": f"链接/数量无效:{url},{quantity}"}

    rep(f"开始处理(imt 平台 API 下单) 任务={title} 数量={quantity}")

    # 1. 登录
    creds = login(rep)
    if not creds:
        return {"ok": False, "message": "imt 平台登录失败"}

    # 2. 下单配置(单价/数量范围)
    try:
        cfg = _http("/order/getOrderConfig", {}, creds)
        oc = (cfg.get("result") or {}).get("orderConfig") or {}
    except Exception as e:
        rep(f"获取 imt 下单配置失败:{e}")
        oc = {}
    price = float(oc.get("customerPrice") or 0.06)
    try:
        min_qty = int(oc.get("minCount") or 10)
        max_qty = int(oc.get("maxCount") or 5000)
    except Exception:
        min_qty, max_qty = 10, 5000
    if quantity < min_qty:
        rep(f"数量 {quantity} 小于 imt 最小发布量 {min_qty}, 自动调整为 {min_qty}")
        quantity = min_qty
    if quantity > max_qty:
        return {"ok": False, "message": f"数量 {quantity} 超过 imt 上限 {max_qty}"}
    to_examine_price = float(oc.get("toExaminePrice") or 0.01)

    # 3. 样图: 优先用已配置的样图地址(与电脑版一致), 没有则自动生成上传
    act = "点赞截图" if title == "点赞" else "点爱心截图"
    fp = (config.IMT_SAMPLE_IMG or "").strip()
    if fp:
        rep("使用已配置样图")
    else:
        rep("生成样图并上传")
        sample = _make_sample_img(title + " 任务")
        try:
            up = _http("/customer/uploadImgBase64",
                       {"base64Str": sample, "isWatermark": True}, creds)
            fp = (up.get("result") or {}).get("filePath")
            if not fp:
                return {"ok": False, "message": f"样图上传失败:{up.get('msg')}"}
            rep("样图上传成功")
        except Exception as e:
            return {"ok": False, "message": f"样图上传异常:{e}"}

    # 4. 发布悬赏任务
    task_req = act
    params = {
        "url": url,
        "title": "视频号" + title + "任务",
        "taskRequire": task_req,
        "rateLimit": 0,
        "buyNum": quantity,
        "dailyVote": 0,
        "toExamine": 0,
        "toExaminePrice": to_examine_price,
        "price": price,
        "tags": [],
        "modelFile": fp,
        "modelFileCount": 1,
        "qrContent": "",
        "sourceOrderId": "",
        "sync": True,
    }
    rep(f"发布悬赏任务: {title} x {quantity}, 单价{price}元")
    try:
        r = _http("/order/createOrder", params, creds)
    except Exception as e:
        return {"ok": False, "message": f"imt 下单请求异常:{e}"}

    if r.get("code") == 0:
        msg = str(r.get("msg") or "下单成功")
        rep(f"imt 下单成功: {msg}")
        return {"ok": True, "message": msg, "platform_order_no": ""}
    return {"ok": False, "message": f"imt 下单失败:{r.get('msg')}"}
