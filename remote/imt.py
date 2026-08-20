# -*- coding: utf-8 -*-
"""imt 悬赏平台自动下单(赞/爱心)
赞和爱心为独立订单项,分别调用下单(goods_ref 可配置区分)。
流程: 登录 -> 打开下单页 -> 填链接/数量 -> 提交 -> 验证结果
"""
import time

from playwright.sync_api import sync_playwright

import config


def _new_context(p):
    return p.chromium.launch_persistent_context(
        "", headless=False,  # 与橘子一致,真实窗口模式,规避反自动化
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


def _body(page) -> str:
    try:
        return page.inner_text("body") or ""
    except Exception:
        return ""


def ensure_login(page, step_cb=None) -> bool:
    """确认已登录。
    优先级: 已有登录态 > 配置的Cookie注入 > 账号密码
    """
    def rep(s):
        if step_cb:
            step_cb(s)

    try:
        body = _body(page)
        if "提交订单" in body or "退出" in body:
            rep("登录状态检查:已登录")
            return True
    except Exception:
        pass

    # 方式1: 使用手机导出的登录 Cookie
    if config.IMT_COOKIE:
        rep("尝试使用已保存的登录Cookie")
        try:
            cookies = config.parse_cookie(config.IMT_COOKIE, "imt.tiankongfeiji.cn")
            if not cookies:
                rep("登录失败:Cookie 内容为空")
                return False
            page.context.add_cookies(cookies)
            page.goto("https://imt.tiankongfeiji.cn/customer/order_add.html", timeout=30000)
            time.sleep(5)
            body = _body(page)
            if "提交订单" in body or "退出" in body:
                rep("Cookie 登录成功")
                return True
            rep("Cookie 登录失败(可能已过期,请重新在手机导出)")
        except Exception as e:
            rep(f"Cookie 注入异常:{e}")
        return False

    # 方式2: 账号密码登录
    if not (config.IMT_ACCOUNT and config.IMT_PASSWORD):
        rep("登录失败:未配置 imt 账号密码或Cookie")
        return False
    rep("未登录,开始账号密码登录")
    try:
        page.goto("https://imt.tiankongfeiji.cn/customer/login.html", timeout=30000)
        time.sleep(5)
        vis = [el for el in page.query_selector_all("input") if _is_visible(el)]
        if len(vis) < 2:
            rep("登录失败:找不到账号/密码输入框")
            return False
        vis[0].fill(config.IMT_ACCOUNT)
        vis[1].fill(config.IMT_PASSWORD)
        for b in page.query_selector_all("button"):
            if _is_visible(b) and (b.inner_text() or "").strip() == "登录":
                b.click(timeout=3000)
                break
        time.sleep(6)
        body = _body(page)
        if "提交订单" in body or "退出" in body:
            rep("登录成功")
            return True
        rep(f"登录失败:提交后仍未登录,页面:{body[:80]!r}")
        return False
    except Exception as e:
        rep(f"登录异常:{e}")
        return False


def order(url: str, quantity: int, title: str = "点赞➕爱心",
          goods_ref: str = "", step_cb=None) -> dict:
    """在 imt 平台发布任务。返回 {"ok","message","platform_order_no"}"""
    if not url or not quantity or quantity <= 0:
        return {"ok": False, "message": f"参数无效(url={url}, 数量={quantity})"}

    def rep(s):
        if step_cb:
            step_cb(s)

    rep(f"开始处理(imt平台) 商品编号:{goods_ref or '默认'}")
    p = sync_playwright().start()
    ctx = None
    try:
        ctx = _new_context(p)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto("https://imt.tiankongfeiji.cn/customer/order_add.html", timeout=30000)
        time.sleep(5)
        if not ensure_login(page, rep):
            return {"ok": False, "message": "imt 平台登录失败(请检查账号密码)"}
        # 重新打开下单页(登录后)
        page.goto("https://imt.tiankongfeiji.cn/customer/order_add.html", timeout=30000)
        time.sleep(5)
        body = _body(page)
        if "提交订单" not in body:
            return {"ok": False, "message": f"未进入 imt 下单页。页面:{body[:100]}"}
        rep("进入 imt 下单页")
        # 填表
        try:
            page.fill('input[name=url]', url)
            rep("已填写视频链接")
        except Exception as e:
            return {"ok": False, "message": f"填链接失败:{e}"}
        try:
            page.fill('input[name=title]', title[:80])
        except Exception:
            pass
        try:
            page.fill('textarea[name=taskRequire]', "请完成后提交截图,谢谢")
        except Exception:
            pass
        try:
            page.fill('input[name=buyNum]', str(quantity))
            rep(f"填写数量:{quantity}")
        except Exception as e:
            return {"ok": False, "message": f"填数量失败:{e}"}
        try:
            actual = page.input_value('input[name=buyNum]').strip()
            if actual != str(quantity):
                return {"ok": False, "message": f"数量校验失败!订单={quantity},表单={actual}"}
        except Exception:
            pass
        rep("数量校验通过")
        # 提交
        body_before = _body(page)
        clicked = False
        for b in page.query_selector_all("button"):
            if _is_visible(b):
                t = (b.inner_text() or "").strip()
                if "提交" in t:
                    rep(f"点击提交:{t[:20]}")
                    b.click(timeout=5000)
                    clicked = True
                    break
        if not clicked:
            return {"ok": False, "message": "找不到提交按钮"}
        time.sleep(4)
        body_after = _body(page)
        rep("等待平台返回结果")
        ok_kws = ("提交成功", "下单成功", "发布成功", "任务已发布", "审核中", "待审核")
        fail_kws = ("提交失败", "下单失败", "发布失败", "操作失败")
        for kw in ok_kws:
            if kw in body_after and kw not in body_before:
                return {"ok": True, "message": f"imt 提交成功,等待审核(数量{quantity})"}
        for kw in fail_kws:
            if kw in body_after and kw not in body_before:
                return {"ok": False, "message": f"imt 提交失败:页面提示:{kw}"}
        return {"ok": False,
                "message": f"已点击提交但未确认成功。页面:{body_after[:120]}"}
    except Exception as e:
        return {"ok": False, "message": f"imt 下单异常:{e}"}
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
