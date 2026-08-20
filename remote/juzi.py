# -*- coding: utf-8 -*-
"""橘子平台自动下单(真实窗口模式,规避反自动化)
流程: 登录 -> 进入收藏 -> 按商品编号搜索商品 -> 打开商品页 -> 填链接/数量 -> 提交 -> 验证结果
每步输出详细日志(step_cb), 找不到商品/登录失败时明确失败, 不继续下单。
"""
import time

from playwright.sync_api import sync_playwright

import config

# 收藏页候选路由(SPA hash),依次尝试
_COLLECT_ROUTES = (
    "#/collect",
    "#/collection",
    "#/mycollect",
    "#/collectList",
    "#/user/collect",
    "#/goodsCollect",
)


def _new_context(p):
    return p.chromium.launch_persistent_context(
        "", headless=False,  # 橘子反自动化:必须真实窗口模式
        args=["--window-position=-32000,-32000", "--disable-gpu"],
        user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"),
    )


def _is_visible(el) -> bool:
    try:
        return bool(el.is_visible())
    except Exception:
        return False


def _close_popups(page):
    try:
        for t in ("我知道了", "我知道了!", "取消", "关闭", "好的"):
            try:
                btn = page.get_by_text(t, exact=True).first
                if btn.count() and _is_visible(btn):
                    btn.click(timeout=1500)
                    time.sleep(1)
                    break
            except Exception:
                continue
    except Exception:
        pass


def _body(page) -> str:
    try:
        return page.inner_text("body") or ""
    except Exception:
        return ""


def _is_logged_in(page) -> bool:
    body = _body(page)
    return "退出登录" in body or "我的订单" in body


def ensure_login(page, step_cb=None) -> bool:
    """确认已登录。
    优先级: 已有登录态 > 配置的Cookie注入 > 账号密码(Playwright可能被平台风控)
    """
    def rep(s):
        if step_cb:
            step_cb(s)

    page.goto("https://juzi00.com/", timeout=30000)
    time.sleep(6)
    _close_popups(page)
    if _is_logged_in(page):
        rep("登录状态检查:已登录")
        return True

    # 方式1: 使用手机导出的登录 Cookie
    if config.JUZI_COOKIE:
        rep("尝试使用已保存的登录Cookie")
        try:
            cookies = config.parse_cookie(config.JUZI_COOKIE, ".juzi00.com")
            if not cookies:
                rep("登录失败:Cookie 内容为空")
                return False
            page.context.add_cookies(cookies)
            page.reload()
            time.sleep(6)
            _close_popups(page)
            if _is_logged_in(page):
                rep("Cookie 登录成功")
                return True
            rep("Cookie 登录失败(可能已过期,请重新在手机导出)")

        except Exception as e:
            rep(f"Cookie 注入异常:{e}")
        return False

    # 方式2: 账号密码登录(平台可能对自动化环境风控)
    if not (config.JUZI_ACCOUNT and config.JUZI_PASSWORD):
        rep("登录失败:未配置橘子账号密码或Cookie")
        return False
    rep("未登录,开始账号密码登录")
    try:
        vis = [el for el in page.query_selector_all("input") if _is_visible(el)]
        if len(vis) < 2:
            rep("登录失败:找不到账号/密码输入框")
            return False
        vis[0].fill(config.JUZI_ACCOUNT)
        vis[1].fill(config.JUZI_PASSWORD)
        for b in page.query_selector_all("button"):
            if _is_visible(b) and (b.inner_text() or "").strip() == "登录":
                b.click(timeout=3000)
                break
        time.sleep(7)
        if _is_logged_in(page):
            rep("登录成功")
            return True
        # 可能弹了验证码/其他提示,读页面提示
        body = _body(page)
        rep(f"登录失败:提交后仍未登录,页面:{body[:80]!r}")
        return False
    except Exception as e:
        rep(f"登录异常:{e}")
        return False


def _enter_collect(page, step_cb=None) -> bool:
    """进入收藏页面。返回是否进入。"""
    def rep(s):
        if step_cb:
            step_cb(s)

    # 1) 优先点击导航中的"收藏"入口
    try:
        for el in page.query_selector_all("text=我的收藏"):
            if _is_visible(el):
                rep("进入收藏:点击「我的收藏」")
                el.click(timeout=3000)
                time.sleep(5)
                if _looks_like_collect(page):
                    return True
    except Exception:
        pass
    try:
        for el in page.query_selector_all("text=商品收藏"):
            if _is_visible(el):
                rep("进入收藏:点击「商品收藏」")
                el.click(timeout=3000)
                time.sleep(5)
                if _looks_like_collect(page):
                    return True
    except Exception:
        pass
    # 2) 依次尝试候选路由
    for route in _COLLECT_ROUTES:
        rep(f"进入收藏:尝试路由 {route}")
        try:
            page.goto("https://juzi00.com/indexPc.html" + route, timeout=15000)
            time.sleep(4)
            if _looks_like_collect(page):
                rep(f"进入收藏成功:路由 {route}")
                return True
        except Exception:
            continue
    return False


def _looks_like_collect(page) -> bool:
    """粗略判断当前页面是否收藏/商品列表页"""
    body = _body(page)
    # 未登录跳登录页 -> 不是收藏页
    if "登录" in body[:60] and "退出登录" not in body:
        return False
    # 有"收藏"字样或出现"商品"列表特征
    if "收藏" in body or "已收藏" in body:
        return True
    return False


def _search_goods(page, goods_ref: str, step_cb=None) -> bool:
    """在收藏页搜索商品编号,找到并进入商品页。返回是否成功进入。"""
    def rep(s):
        if step_cb:
            step_cb(s)

    # 搜索输入框: placeholder 含 搜索/商品/编号
    search_input = None
    for el in page.query_selector_all("input"):
        if not _is_visible(el):
            continue
        ph = (el.get_attribute("placeholder") or "") + (el.get_attribute("class") or "")
        if any(k in ph for k in ("搜索", "商品", "编号", "search")):
            search_input = el
            break
    if search_input is not None:
        rep(f"搜索商品编号:{goods_ref}")
        try:
            search_input.fill(goods_ref)
            time.sleep(0.5)
            search_input.press("Enter")
            time.sleep(5)
        except Exception:
            pass
    # 在页面中匹配商品编号:找包含编号的可点击卡片
    rep(f"匹配商品编号:{goods_ref}")
    try:
        candidates = page.query_selector_all(f"text={goods_ref}")
        for c in candidates:
            if not _is_visible(c):
                continue
            # 向上找可点击的卡片容器
            card = c.evaluate(
                """(e) => {
                    let n = e;
                    for (let i = 0; i < 6; i++) {
                        n = n.parentElement;
                        if (!n) break;
                        if (n.querySelector('a, button, [class*="card"], [class*="item"]')) return n;
                    }
                    return e;
                }""")
            try:
                # 点击商品卡片
                if card:
                    card.click(timeout=3000)
                else:
                    c.click(timeout=3000)
                time.sleep(5)
                # 验证已进入商品详情页
                body = _body(page)
                if "商品编号" in body and goods_ref in body:
                    rep(f"已找到并进入商品 {goods_ref}")
                    return True
                # 可能进入了新标签页
                if len(page.context.pages) > 1:
                    page2 = page.context.pages[-1]
                    time.sleep(5)
                    body2 = _body(page2)
                    if "商品编号" in body2 and goods_ref in body2:
                        rep(f"已找到并进入商品 {goods_ref}(新标签页)")
                        return True
            except Exception:
                continue
    except Exception:
        pass
    return False


def _fill_and_submit(page, goods_ref: str, video_name: str, link: str,
                     quantity: int, step_cb=None) -> dict:
    """在商品页填链接/数量并提交。返回结果 dict。"""
    def rep(s):
        if step_cb:
            step_cb(s)

    body = _body(page)
    if "商品编号" not in body:
        return {"ok": False, "message": f"未进入商品下单页(商品:{goods_ref})"}
    rep("开始填写订单")
    # 昵称 + 链接
    text_inputs = [el for el in page.query_selector_all("input") if _is_visible(el)
                   and (el.get_attribute("type") in (None, "text", ""))]
    num_inputs = [el for el in page.query_selector_all("input") if _is_visible(el)
                  and el.get_attribute("type") == "number"]
    if len(text_inputs) < 2:
        return {"ok": False, "message": "找不到昵称/链接输入框"}
    try:
        text_inputs[0].fill(video_name or "")
        text_inputs[1].fill(link or "")
        rep("已填写视频链接")
    except Exception as e:
        return {"ok": False, "message": f"填链接失败:{e}"}
    time.sleep(0.5)
    # 数量
    num_input = num_inputs[0] if num_inputs else None
    if num_input is None:
        for el in text_inputs:
            try:
                v = el.input_value()
                if v and v.strip().isdigit():
                    num_input = el
                    break
            except Exception:
                continue
    if num_input is None:
        return {"ok": False, "message": "找不到数量输入框"}
    try:
        num_input.fill(str(quantity))
        rep(f"填写数量:{quantity}")
    except Exception as e:
        return {"ok": False, "message": f"填数量失败:{e}"}
    time.sleep(0.5)
    actual = num_input.input_value().strip()
    if not actual.isdigit() or int(actual) != int(quantity):
        return {"ok": False, "message": f"数量校验失败!订单={quantity},表单={actual}"}
    rep("数量校验通过")
    # 提交
    body_before = _body(page)
    clicked = False
    for b in page.query_selector_all("button"):
        if _is_visible(b):
            t = (b.inner_text() or "").strip()
            if "立即" in t or "提交" in t:
                rep(f"点击提交按钮:{t[:20]}")
                b.click(timeout=5000)
                clicked = True
                break
    if not clicked:
        return {"ok": False, "message": "找不到提交按钮(立即购买)"}
    time.sleep(3)
    # 确认弹窗
    confirm_clicked = ""
    for _ in range(3):
        hit = False
        for t in ("确认支付", "确认订单", "去支付", "确认", "确定", "提交订单",
                  "提交", "支付", "立即支付", "知道了", "完成"):
            try:
                btn = page.locator(f"button:has-text('{t}')").first
                if btn.count() and _is_visible(btn):
                    btn.click(timeout=2000)
                    confirm_clicked += f"[{t}]"
                    rep(f"确认弹窗:{t}")
                    time.sleep(2)
                    hit = True
                    break
            except Exception:
                continue
        if not hit:
            break
    time.sleep(2)
    body_after = _body(page)
    rep("等待平台返回结果")
    return _verify_result(body_before, body_after, goods_ref, confirm_clicked)


def _verify_result(before: str, after: str, goods_ref: str, confirm: str) -> dict:
    """提交后结果验证:成功文案 + 订单号提取,多信号组合"""
    ok_kws = ("提交成功", "下单成功", "购买成功", "支付成功", "订单已提交",
              "成功提交", "已提交订单", "提交订单成功")
    fail_kws = ("提交失败", "下单失败", "购买失败", "操作失败")
    for kw in ok_kws:
        if kw in after and kw not in before:
            # 尝试提取平台订单号
            order_no = ""
            import re
            for m in re.finditer(r"(订单号|订单编号)[:：\s]*([A-Za-z0-9\-]+)", after):
                order_no = m.group(2)
                break
            return {"ok": True, "message": f"提交成功(商品:{goods_ref}){confirm}",
                    "platform_order_no": order_no}
    for kw in fail_kws:
        if kw in after and kw not in before:
            return {"ok": False, "message": f"提交失败(商品:{goods_ref}){confirm}"}
    # URL 变化(如跳转到订单列表/支付页)
    return {"ok": False,
            "message": f"已点击提交但未确认成功(商品:{goods_ref}){confirm},请到平台核实"}


def order(goods_ref: str, video_name: str, link: str, quantity: int,
          step_cb=None) -> dict:
    """在橘子平台对指定商品下单(登录->收藏->搜索编号->填表->提交)。
    返回 {"ok": bool, "message": str, "platform_order_no": str}
    """
    if not goods_ref or not quantity or quantity <= 0:
        return {"ok": False, "message": f"商品/数量无效:{goods_ref},{quantity}"}

    def rep(s):
        if step_cb:
            step_cb(s)

    rep("开始处理(橘子平台)")
    p = sync_playwright().start()
    ctx = None
    try:
        ctx = _new_context(p)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        # 1. 登录
        if not ensure_login(page, rep):
            return {"ok": False, "message": "橘子平台登录失败(请检查账号密码/验证码)"}
        rep("进入我的收藏")
        if not _enter_collect(page, rep):
            return {"ok": False,
                    "message": f"无法进入收藏页,无法查找商品编号 {goods_ref}"}
        # 2. 搜索商品编号
        rep(f"搜索商品编号:{goods_ref}")
        if not _search_goods(page, goods_ref, rep):
            return {"ok": False,
                    "message": f"未找到商品编号 {goods_ref} (收藏中未匹配到该商品)"}
        # 3. 填表提交
        result = _fill_and_submit(page, goods_ref, video_name, link, quantity, rep)
        rep(f"下单结果:{result['message']}")
        return result
    except Exception as e:
        return {"ok": False, "message": f"下单异常:{e}"}
    finally:
        try:
            if ctx:
                ctx.close()
        except Exception:
            pass
        try:
            p.stop()
        except Exception:
            pass
