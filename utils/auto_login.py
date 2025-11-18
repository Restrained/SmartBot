#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Playwright 自动登录示例（验证码登录）
针对: https://accounts.ctrip.com/h5Login/login_ctrip?sibling=T
说明:
- 自动输入手机号、点击发送验证码按钮
- 等待验证码发送后，人工输入验证码进行登录
"""

import os
import time

import redis
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError

# 从环境变量读取，或直接在这里写明（不推荐）
USERNAME = os.getenv("Ctrip_USERNAME", "18073623328")  # 手机号
PASSWORD = os.getenv("Ctrip_PASSWORD", "your_password_here")  # 如果需要，放验证码处理
URL = "https://accounts.ctrip.com/h5Login/login_ctrip?sibling=T"

# 本地保存登录态（持久化）目录（可选）
STORAGE_STATE = "ctrip_storage_state.json"

# Redis 连接配置
REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_DB = 0
REDIS_KEY = "ctrip_ck"


def save_cookie_to_redis(cookies, phone_number):
    """保存 cookies 到 Redis 哈希表，field 为手机号"""
    r = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)
    cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
    r.hset("ctrip_ck", phone_number, cookie_str)
    print(f"✅ 已将 cookie 写入 Redis 哈希表 ctrip_ck，field = {phone_number}")
    return cookie_str

def try_fill_input(page, selectors, value):
    """尝试一组选择器，能找到第一个可见输入就填写并返回True"""
    for sel in selectors:
        try:
            el = page.locator(sel)
            if el.count() and el.first.is_visible():
                el.first.fill(value)
                return True
        except Exception:
            continue
    return False


def find_and_click(page, selectors):
    """尝试点击一组选择器中可见的按钮"""
    for sel in selectors:
        try:
            btn = page.locator(sel)
            if btn.count() and btn.first.is_visible():
                btn.first.click()
                return True
        except Exception:
            continue
    return False


def main(headless=True, slow_mo=0):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, slow_mo=slow_mo)
        # 使用持久化上下文可以保存登录态
        context = browser.new_context(storage_state=None)  # 若要加载已有登录态，传 storage_state=STORAGE_STATE
        page = context.new_page()
        page.goto(URL, wait_until="networkidle")

        # 截图（调试用）
        page.screenshot(path="ctrip_login_page.png", full_page=False)

        # 一些可能的手机号输入框选择器
        username_selectors = [
            'input[type="tel"]',
            'input[aria-label*="phone"]',
            'input[placeholder*="输入手机号"]',
        ]

        # 切换到验证码登录
        switch_login_selectors = [
            'button:has-text("手机验证码登录")',
            'button[type="button"]:has-text("手机验证码登录")',
            'button:has-text("手机验证码登录")',
        ]
        # 验证码输入框选择器
        verification_selectors = [
            'input[type="text"][placeholder="输入验证码"]',
            'input[aria-label*="verify-code"]',
        ]

        # 发送验证码按钮选择器
        send_code_button_selectors = [
            'a[class="valid-get-code"]',
            'a:has-text("获取验证码")',
        ]

        # 登录按钮的可能选择器
        login_button_selectors = [
            "button:has-text('登录')",
            "button:has-text('登 录')",
        ]

        # 0. 切换到验证码登录
        clicked_code_login = find_and_click(page, switch_login_selectors)
        if not clicked_code_login:
            print("无法自动定位到验证码输入按钮，请检查选择器或手动输入。页面截图已保存 -> ctrip_login_page.png")
            return
        time.sleep(5)  # 等待10秒，给验证码时间发送（可视化等待）

        # 1. 输入手机号
        ok_user = try_fill_input(page, username_selectors, USERNAME)
        if not ok_user:
            print("无法自动定位手机号输入框，请检查选择器或手动输入。页面截图已保存 -> ctrip_login_page.png")
            return
        time.sleep(5)

        # 2. 点击发送验证码按钮
        clicked_send_code = find_and_click(page, send_code_button_selectors)
        if not clicked_send_code:
            print("无法点击发送验证码按钮，请检查选择器或手动点击。")
            return

        print("已点击发送验证码按钮，等待验证码发送（10秒后开始人工输入验证码）。")
        time.sleep(10)  # 等待10秒，给验证码时间发送（可视化等待）

        # 3. 等待用户手动输入验证码（此步骤需要人工输入）
        verification_code = input("请输入收到的验证码并按 Enter：")
        if not verification_code:
            print("验证码为空，脚本终止。")
            return

        # 4. 输入验证码
        ok_verification = try_fill_input(page, verification_selectors, verification_code)
        if not ok_verification:
            print("无法自动填写验证码输入框，请检查选择器或手动输入验证码。")
            return

        # 5. 点击登录按钮
        clicked_login = find_and_click(page, login_button_selectors)
        if not clicked_login:
            print("无法点击登录按钮，请检查选择器或手动点击。")
            return

        # 👇 新增逻辑：检测并同意隐私弹窗
        try:
            agree_button = page.locator("button:has-text('同意并登录')")
            agree_button.wait_for(state="visible", timeout=5000)
            agree_button.click()
            print("已自动点击“同意并登录”按钮。")
        except Exception:
            print("未检测到隐私协议弹窗（可能不需要确认或已自动同意）。")

        # 等待登录完成或跳转
        try:
            page.wait_for_load_state("networkidle", timeout=10000)
        except PWTimeoutError:
            pass

        # 给页面一点时间完成可能的二次校验/跳转
        time.sleep(3)

        # 检查是否登录成功：简单策略 - 查找“我的携程”“退出登录”等常见字样
        success = False
        success_text_candidates = ["尊敬的会员", "普通会员", "全部订单", "我的钱包", "我的工具"]
        for txt in success_text_candidates:
            if page.locator(f"text={txt}").count() > 0:
                success = True
                break

        # ✅ 获取 cookies 并保存到 Redis
        cookies = context.cookies()
        cookie_str = save_cookie_to_redis(cookies, phone_number=USERNAME)
        print(f"当前 Cookie：\n{cookie_str}\n")

        time.sleep(3)
        # ✅ 若想继续执行接口检测，可监听页面请求
        # 例如检测 GetBrowseHistoryCount 请求
        # def on_request(req):
        #     if "GetBrowseHistoryCount" in req.url:
        #         print(f"捕获目标接口：{req.url}")
        #         ck = req.headers.get("cookie", "")
        #         if ck:
        #             r = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)
        #             r.set(REDIS_KEY, ck)
        #             print("✅ 已将接口 cookie 更新到 Redis")

        # context.on("request", on_request)

        # 保存最后状态截图并持久化 storage_state（可用于后续无头恢复）
        page.screenshot(path="ctrip_after_submit.png", full_page=False)
        context.storage_state(path=STORAGE_STATE)

        if success:
            print("登录成功 ✅。已保存登录状态到：", STORAGE_STATE)
        else:
            print("登录失败，请查看截图：ctrip_after_submit.png 排查问题。")

        # 若想保留浏览器窗口用于人工交互，可以将 headless=False 并移除 browser.close()
        browser.close()


if __name__ == "__main__":
    # 可以设置 headless=False 便于调试
    main(headless=False, slow_mo=0)
