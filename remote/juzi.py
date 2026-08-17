# -*- coding: utf-8 -*-
"""橘子平台无头自动下单(账号密码登录) —— 已验证 GitHub Actions 环境可行"""
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


def _close_popups(page):
    try:
        for t in ("取消", "知道了", "关闭", "好的"):
            try:
                btn = page.locator(f"button:has-text('{t}')").first
                if btn.count() and btn.is_visible():
                    btn.click(timeout=1500)
                    time.sleep(1)
                    break
            except Exception:
                continue
    except Exception:
        pass


def ensure_login(page) -> bool:
    """确认已登录,未登录则用账号密码登录。返回是否登录成功。"""
    try:
        body = page.inner_text("body")
    except Exception:
        return False
    if "退出登录" in body or "我的订单" in body:
        return True
    if not (config.JUZI_ACCOUNT and config.JUZI_PASSWORD):
        return False
    try:
        page.goto("https://juzi00.com/", timeout=30000)
        time.sleep(4)
        inputs = page.query_selector_all("input")
        vis = [el for el in inputs if _is_visible(el)]
        if len(vis) < 2:
            return False
        vis[0].fill(config.JUZI_ACCOUNT)
        vis[1].fill(config.JUZI_PASSWORD)
        # 点击登录按钮
        for b in page.query_selector_all("button"):
            if _is_visible(b) and (b.inner_text() or "").strip() == "登录":
                b.click(timeout=3000)
                break
        time.sleep(6)
        body = page.inner_text("body")
        return "退出登录" in body or "我的订单" in body
    except Exception:
        return False


def _is_visible(el) -> bool:
    try:
        return bool(el.is_visible())
    except Exception:
        return False


def _fail_snippet(body: str, kw: str = "失败", limit: int = 60) -> str:
    try:
        body = (body or "").replace("\n", " ").strip()
    except Exception:
        return ""
    i = body.find(kw)
    if i < 0:
        return body[:limit]
    return body[max(0, i - 20): i + limit]


def _new_kw_hit(before: str, after: str, kws: tuple) -> bool:
    for kw in kws:
        if kw in (after or "") and kw not in (before or ""):
            return True
    return False


def order(goods_ref: str, video_name: str, link: str, quantity: int) -> dict:
    """在橘子平台对指定商品下单(无头)。
    返回 {"ok": bool, "message": str}
    """
    if not goods_ref or not quantity or quantity <= 0:
        return {"ok": False, "message": f"商品/数量无效:{goods_ref},{quantity}"}
    p = sync_playwright().start()
    ctx = None
    try:
        ctx = _new_context(p)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        # 登录
        page.goto("https://juzi00.com/", timeout=30000)
        time.sleep(5)
        _close_popups(page)
        if not ensure_login(page):
            return {"ok": False,
                    "message": "橘子平台未登录,且自动登录失败(请检查账号密码配置)"}
        # 打开商品页
        page.goto(f"https://juzi00.com/indexPc.html#/goods/{goods_ref}", timeout=30000)
        time.sleep(6)
        _close_popups(page)
        body = page.inner_text("body")
        if "商品编号" not in body:
            return {"ok": False,
                    "message": f"未进入商品下单页(商品:{goods_ref})。页面:{body[:80]}..."}
        # 填表:第一栏昵称 + 第二栏短链接
        text_inputs = [el for el in page.query_selector_all("input") if _is_visible(el)
                       and (el.get_attribute("type") in (None, "text", ""))]
        num_inputs = [el for el in page.query_selector_all("input") if _is_visible(el)
                      and el.get_attribute("type") == "number"]
        if len(text_inputs) < 2:
            return {"ok": False, "message": "找不到昵称/链接输入框"}
        try:
            text_inputs[0].fill(video_name or "")
            text_inputs[1].fill(link or "")
        except Exception as e:
            return {"ok": False, "message": f"填表失败:{e}"}
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
        num_input.fill(str(quantity))
        time.sleep(0.5)
        actual = num_input.input_value().strip()
        if not actual.isdigit() or int(actual) != int(quantity):
            return {"ok": False,
                    "message": f"数量校验失败!订单={quantity},表单={actual},已中止"}
        # 读取提交按钮金额
        amount_text = ""
        for b in page.query_selector_all("button"):
            if _is_visible(b):
                t = (b.inner_text() or "").strip()
                if "立即" in t or "提交" in t:
                    amount_text = t[:40]
                    break
        # 点立即购买
        body_before = page.inner_text("body")
        clicked = False
        for b in page.query_selector_all("button"):
            if _is_visible(b):
                t = (b.inner_text() or "").strip()
                if "立即" in t or "提交" in t:
                    b.click(timeout=5000)
                    clicked = True
                    break
        if not clicked:
            return {"ok": False, "message": "找不到提交按钮(立即购买)"}
        time.sleep(3)
        # 确认弹窗:点"提交"/"确认支付"等
        confirm_clicked = ""
        for _ in range(3):
            hit = False
            for t in ("确认支付", "确认订单", "去支付", "确认", "确定", "提交订单",
                      "提交", "支付", "立即支付", "知道了", "完成"):
                try:
                    btn = page.locator(f"button:has-text('{t}')").first
                    if btn.count() and btn.is_visible():
                        btn.click(timeout=2000)
                        confirm_clicked += f"[{t}]"
                        time.sleep(2)
                        hit = True
                        break
                except Exception:
                    continue
            if not hit:
                break
        # 提交后验证(对比新出现文本)
        time.sleep(2)
        body_after = ""
        try:
            body_after = page.inner_text("body")
        except Exception:
            pass
        ok = _new_kw_hit(body_before, body_after,
                         ("提交成功", "下单成功", "购买成功", "支付成功", "订单已提交",
                          "成功提交", "已提交订单", "提交订单成功"))
        fail = _new_kw_hit(body_before, body_after,
                           ("提交失败", "下单失败", "购买失败", "操作失败"))
        if ok:
            return {"ok": True, "message": f"提交成功(商品:{goods_ref}){amount_text}{confirm_clicked}"}
        if fail:
            return {"ok": False,
                    "message": f"提交失败(商品:{goods_ref}){amount_text}{confirm_clicked}"
                               f" 平台返回:{_fail_snippet(body_after)}"}
        return {"ok": False,
                "message": f"已点击提交但无法确认是否成功(商品:{goods_ref}),请到平台核实"
                           f"{amount_text}{confirm_clicked}"}
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
