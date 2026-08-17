# -*- coding: utf-8 -*-
"""imt 悬赏平台无头登录+发布任务(赞/爱心) —— 支持账号密码登录"""
import time

from playwright.sync_api import sync_playwright

import config


def _new_context(p):
    return p.chromium.launch_persistent_context(
        "", headless=True,
        args=["--disable-gpu", "--no-sandbox"],
        user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"),
    )


def _is_visible(el) -> bool:
    try:
        return bool(el.is_visible())
    except Exception:
        return False


def ensure_login(page) -> bool:
    try:
        body = page.inner_text("body")
        if "提交订单" in body or "退出" in body:
            return True
    except Exception:
        return False
    if not (config.IMT_ACCOUNT and config.IMT_PASSWORD):
        return False
    try:
        page.goto("https://imt.tiankongfeiji.cn/customer/login.html", timeout=30000)
        time.sleep(5)
        vis = [el for el in page.query_selector_all("input") if _is_visible(el)]
        if len(vis) < 2:
            return False
        vis[0].fill(config.IMT_ACCOUNT)
        vis[1].fill(config.IMT_PASSWORD)
        for b in page.query_selector_all("button"):
            if _is_visible(b) and (b.inner_text() or "").strip() == "登录":
                b.click(timeout=3000)
                break
        time.sleep(6)
        body = page.inner_text("body")
        return "提交订单" in body or "退出" in body
    except Exception:
        return False


def order(url: str, quantity: int, title: str = "点赞➕爱心") -> dict:
    """在 imt 平台发布赞/爱心任务。返回 {"ok": bool, "message": str}"""
    if not url or not quantity or quantity <= 0:
        return {"ok": False, "message": f"参数无效(url={url}, 数量={quantity})"}
    p = sync_playwright().start()
    ctx = None
    try:
        ctx = _new_context(p)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto("https://imt.tiankongfeiji.cn/customer/order_add.html", timeout=30000)
        time.sleep(5)
        if not ensure_login(page):
            return {"ok": False, "message": "imt 平台未登录,自动登录失败(请检查账号密码配置)"}
        page.goto("https://imt.tiankongfeiji.cn/customer/order_add.html", timeout=30000)
        time.sleep(5)
        body = page.inner_text("body")
        if "提交订单" not in body:
            return {"ok": False, "message": f"未进入 imt 下单页。页面:{body[:100]}"}
        # 填表
        try:
            page.fill('input[name=url]', url)
        except Exception as e:
            return {"ok": False, "message": f"填链接失败:{e}"}
        try:
            page.fill('input[name=title]', title[:80])
        except Exception:
            pass
        try:
            page.fill('textarea[name=taskRequire]', "请截图反馈,谢谢")
        except Exception:
            pass
        try:
            page.fill('input[name=buyNum]', str(quantity))
        except Exception as e:
            return {"ok": False, "message": f"填数量失败:{e}"}
        # 数量校验
        try:
            actual = page.input_value('input[name=buyNum]').strip()
            if actual != str(quantity):
                return {"ok": False, "message": f"数量校验失败!订单={quantity},表单={actual}"}
        except Exception:
            pass
        # 提交
        clicked = False
        for b in page.query_selector_all("button"):
            if _is_visible(b):
                t = (b.inner_text() or "").strip()
                if "提交" in t:
                    b.click(timeout=5000)
                    clicked = True
                    break
        if not clicked:
            return {"ok": False, "message": "找不到提交按钮"}
        time.sleep(4)
        try:
            body2 = page.inner_text("body")
        except Exception:
            body2 = ""
        ok = any(k in body2 for k in ("提交成功", "下单成功", "发布成功", "任务已发布", "审核中", "待审核"))
        if ok:
            return {"ok": True, "message": "imt 提交成功,等待审核"}
        return {"ok": False, "message": f"已点击提交但未确认成功。页面:{body2[:120]}"}
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
