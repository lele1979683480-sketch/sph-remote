# -*- coding: utf-8 -*-
"""视频号数据抓取(无头浏览器,无需登录) —— 已验证在 GitHub Actions 环境可用"""
import time

from playwright.sync_api import sync_playwright


def parse_number(s: str) -> int | None:
    s = (s or "").strip().replace(",", "")
    if not s:
        return None
    try:
        if "万" in s:
            return int(float(s.replace("万", "")) * 10000)
        if "亿" in s:
            return int(float(s.replace("亿", "")) * 100000000)
        return int(float(s))
    except Exception:
        return None


def scrape(url: str) -> dict | None:
    """抓取视频号页面数据(赞/爱心/评论/转发/作者/标题)。
    返回 None 表示失败。
    """
    p = sync_playwright().start()
    ctx = None
    try:
        ctx = p.chromium.launch_persistent_context(
            "", headless=True,
            args=["--disable-gpu", "--no-sandbox"],
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"),
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(url, timeout=30000)
        time.sleep(8)
        data = page.evaluate("""() => {
            const numOf = (sel) => {
                const icon = document.querySelector(sel);
                if (!icon) return null;
                const item = icon.closest('[class*="operate-item"]')
                             || icon.parentElement || icon;
                const t = (item.innerText || '').trim();
                return /^[\\d,.万亿]+$/.test(t) ? t : null;
            };
            const like = numOf('[class*="thumb-regular"]');
            const heart = numOf('[class*="heart-regular"]');
            const comment = numOf('[class*="bubble-regular"]');
            const share = numOf('[class*="share-regular"]');
            const raw = document.body ? document.body.innerText : '';
            const lines = raw.split('\\n').map(s => s.trim()).filter(Boolean);
            let title = '', publish = '', author = '', sawPublish = false;
            for (const line of lines) {
                if (!title && line.length >= 4 && !/^[\\d,.万亿]+$/.test(line)
                    && line !== '视频号' && !/可扫码/.test(line)) {
                    title = line;
                    continue;
                }
                const m = /((?:\\d{4}年)?\\d{1,2}月\\d{1,2}日|\\d+天前|\\d+小时前)/.exec(line);
                if (!publish && m) { publish = m[1]; sawPublish = true; continue; }
                if (sawPublish && !author && line.length >= 2 && line.length <= 30
                    && !/^[\\d,.万亿]+$/.test(line) && !/可扫码/.test(line) && line !== '视频号'
                    && !/(?:\\d{4}年)?\\d{1,2}月\\d{1,2}日/.test(line)
                    && !/\\d+天前/.test(line) && !/\\d+小时前/.test(line)) {
                    author = line;
                }
            }
            return {like, heart, comment, share, title, author};
        }""")
        result = {
            "like": parse_number(data.get("like")),
            "heart": parse_number(data.get("heart")),
            "comment": parse_number(data.get("comment")),
            "share": parse_number(data.get("share")) or 0,
            "title": (data.get("title") or "").strip(),
            "author": (data.get("author") or "").strip(),
        }
        if result["like"] is not None and result["heart"] is not None \
                and result["comment"] is not None and result["title"]:
            return result
        return None
    except Exception:
        return None
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
